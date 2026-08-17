import json
from collections import defaultdict
from datetime import datetime, timezone
from transformer.base_transformer import BaseTransformer
from logger import logger
from transaction import float_parser

SATOSHIS_PER_BTC = 100000000

# A cooperative close fee well above this is not a fee - it means channel funds
# moved to the peer during the channel's life, so capacity - settled_balance no
# longer isolates the closing cost. Flagged for review rather than booked.
MAX_PLAUSIBLE_CLOSE_FEE_SATOSHI = 100000


class UmbrelTransformer(BaseTransformer):
    """
    Transforms Umbrel/LND node exports to pycgt format.

    Consumes the JSON files produced by:
        lncli listchaintxns    > onchain.json
        lncli closedchannels   > closedchannels.json
        lncli fwdinghistory    > forwards.json
        lncli listpayments     > payments.json

    All of them contain the node's entire history, so a timeframe must be
    applied (see -f/--from and -u/--until).

    Tax treatment:
      - On-chain transactions move BTC between the taxpayer's own wallets and
        channels, so the BTC is neither acquired nor disposed. The miner fee is
        paid in BTC and IS a disposal, carried in Fee(BTC).
      - Opening a channel funds a 2-of-2 multisig the taxpayer still controls;
        closing returns the balance. Neither is a disposal of the BTC itself.
      - Channel closes report total_fees of 0 on-chain because the closing fee
        is deducted from the channel balance instead. The fee is recovered from
        closedchannels.json and merged onto the matching closing transaction,
        but only when this node initiated the close - otherwise the peer paid it
        and the taxpayer has no disposal.
      - Routing fees earned (fwdinghistory) are income: a "gain" row plus a
        "buy" row establishing cost base, matching how interest is handled
        elsewhere. These are fees collected for forwarding other nodes'
        payments, unrelated to the fees paid in listpayments.
      - Outgoing Lightning payments (listpayments) are treated as transfers to
        the taxpayer's other wallets, so only the routing fee paid is a
        disposal. Any payment that was actually a purchase from a third party
        IS a disposal of the amount sent; the export cannot distinguish the two,
        so every payment is logged for review.
    """

    EXCHANGE = 'Umbrel'

    FILE_TYPE_ONCHAIN = 'onchain'
    FILE_TYPE_CLOSEDCHANNELS = 'closedchannels'
    FILE_TYPE_FORWARDS = 'forwards'
    FILE_TYPE_PAYMENTS = 'payments'

    INITIATOR_LOCAL = 'INITIATOR_LOCAL'
    PAYMENT_STATUS_SUCCEEDED = 'SUCCEEDED'

    def _identify_file_type(self, payload, file_path):
        """Identify an LND export by its top-level key"""
        if isinstance(payload, dict):
            if 'transactions' in payload:
                return self.FILE_TYPE_ONCHAIN
            if 'channels' in payload:
                return self.FILE_TYPE_CLOSEDCHANNELS
            if 'forwarding_events' in payload:
                return self.FILE_TYPE_FORWARDS
            if 'payments' in payload:
                return self.FILE_TYPE_PAYMENTS
        raise ValueError(f'Unrecognized Umbrel/LND JSON format in file: {file_path}')

    def transform(self):
        """Transform Umbrel/LND JSON exports to pycgt format"""
        logger.info(f"Processing Umbrel logs from {len(self.input_files)} file(s)")

        chain_txs = []
        closed_channels = []
        forwards = []
        payments = []

        for file_path in self.input_files:
            with open(file_path, 'r') as jsonfile:
                payload = json.load(jsonfile)

            file_type = self._identify_file_type(payload, file_path)
            logger.info(f'Identified {file_path} as type: {file_type}')

            if file_type == self.FILE_TYPE_ONCHAIN:
                chain_txs.extend(payload['transactions'])
            elif file_type == self.FILE_TYPE_CLOSEDCHANNELS:
                closed_channels.extend(payload['channels'])
            elif file_type == self.FILE_TYPE_FORWARDS:
                forwards.extend(payload['forwarding_events'])
            else:
                payments.extend(payload['payments'])

        closing_fees = self._collect_closing_fees(closed_channels)
        transactions = self._transform_chain_transactions(chain_txs, closing_fees)
        transactions.extend(self._transform_forwards(forwards))
        transactions.extend(self._transform_payments(payments))

        if not transactions:
            raise ValueError('No Umbrel rows to transform within the requested timeframe')

        transactions.sort(key=lambda x: x['Datetime'])

        self.autofill_locale_fiat_and_fees(transactions)

        self.write_pycgt_csv(transactions)
        return transactions

    def _collect_closing_fees(self, channels):
        """
        Map closing transaction hash -> closing fee in satoshi, for channels
        this node both funded and closed.

        Returns an empty mapping when closedchannels.json was not supplied, in
        which case closing transactions simply carry no fee.
        """
        fees = {}
        for channel in channels:
            closing_tx = (channel.get('closing_tx_hash') or '').strip()
            channel_point = (channel.get('channel_point') or '').strip()
            if not closing_tx:
                continue

            if channel.get('close_initiator') != self.INITIATOR_LOCAL:
                logger.info(
                    f'Channel {channel_point}: closed by the peer, so the peer paid the '
                    f'closing fee - no disposal recorded')
                continue

            if channel.get('open_initiator') != self.INITIATOR_LOCAL:
                logger.warning(
                    f'Channel {channel_point}: closed locally but funded by the peer; '
                    f'cannot derive the closing fee from capacity - skipped, review manually')
                continue

            capacity = float_parser(str(channel.get('capacity', 0)))
            settled = float_parser(str(channel.get('settled_balance', 0)))
            time_locked = float_parser(str(channel.get('time_locked_balance', 0)))
            fee = capacity - settled - time_locked

            if fee <= 0:
                logger.warning(
                    f'Channel {channel_point}: derived closing fee is {fee:.0f} sat - skipped')
                continue

            if fee > MAX_PLAUSIBLE_CLOSE_FEE_SATOSHI:
                logger.warning(
                    f'Channel {channel_point}: capacity - settled_balance is {fee:.0f} sat, '
                    f'above the {MAX_PLAUSIBLE_CLOSE_FEE_SATOSHI} sat sanity limit. Channel '
                    f'funds moved to the peer, so this is not purely a fee - no fee recorded, '
                    f'review manually')
                continue

            fees[closing_tx] = fee
            logger.info(f'Channel {channel_point}: closing fee {fee:.0f} sat paid locally')

        return fees

    def _describe_label(self, label):
        """Turn an LND transaction label into a readable Type"""
        label = (label or '').strip()
        if 'openchannel' in label:
            return 'Channel open'
        if 'closechannel' in label:
            return 'Channel close'
        if label:
            return label
        return 'Transfer'

    def _transform_chain_transactions(self, chain_txs, closing_fees):
        """Transform on-chain transactions, merging in locally-paid closing fees"""
        transactions = []
        skipped = 0
        merged = set()

        for chain_tx in chain_txs:
            tran_datetime = datetime.fromtimestamp(
                int(chain_tx['time_stamp']), tz=timezone.utc)
            if not self.in_timeframe(tran_datetime):
                skipped += 1
                continue

            tx_hash = (chain_tx.get('tx_hash') or '').strip()
            amount_satoshi = float_parser(str(chain_tx.get('amount', 0)))
            fee_satoshi = float_parser(str(chain_tx.get('total_fees', 0)))
            label = (chain_tx.get('label') or '').strip()

            # A channel close reports no on-chain fee; recover it from the
            # closed-channel record when this node paid it.
            if tx_hash in closing_fees:
                if fee_satoshi > 0:
                    logger.warning(
                        f'Closing transaction {tx_hash[:12]} already reports a fee of '
                        f'{fee_satoshi:.0f} sat; keeping it and ignoring the derived '
                        f'{closing_fees[tx_hash]:.0f} sat')
                else:
                    fee_satoshi = closing_fees[tx_hash]
                merged.add(tx_hash)

            tran = self._create_base_transaction(
                self.EXCHANGE,
                tran_datetime.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'withdrawal' if amount_satoshi < 0 else 'deposit')

            tran['Type'] = self._describe_label(label)
            if amount_satoshi != 0:
                tran['BTC'] = str(abs(amount_satoshi) / SATOSHIS_PER_BTC)
            if fee_satoshi > 0:
                tran['Fee(BTC)'] = str(fee_satoshi / SATOSHIS_PER_BTC)

            tran['Comments'] = (
                f'Umbrel on-chain {"send" if amount_satoshi < 0 else "receive"}: '
                f'{abs(amount_satoshi):.0f} sat; Fee: {fee_satoshi:.0f} sat; '
                f'Label: {label}; Hash: {tx_hash}')

            transactions.append(tran)

        if skipped:
            logger.info(f'Skipped {skipped} on-chain transaction(s) outside the requested timeframe')

        unmatched = set(closing_fees) - merged
        if unmatched:
            logger.warning(
                f'{len(unmatched)} closed channel(s) had a locally-paid closing fee whose '
                f'closing transaction is not in the on-chain export within the timeframe; '
                f'those fees were NOT recorded: {sorted(h[:12] for h in unmatched)}')

        return transactions

    def _transform_payments(self, payments):
        """
        Transform outgoing Lightning payments.

        The amount sent is recorded as a transfer, not a disposal: these
        payments fund the taxpayer's other Lightning wallets. The routing fee
        is paid in BTC and IS a disposal.

        Only SUCCEEDED payments are kept - a failed payment moves no value and
        costs no fee. Note LND may report a failure_reason on a payment that
        ultimately succeeded (an earlier attempt timed out), so status is the
        only field that decides.
        """
        if not payments:
            return []

        transactions = []
        skipped_status = 0
        skipped_timeframe = 0
        reviewable = []

        for payment in payments:
            if payment.get('status') != self.PAYMENT_STATUS_SUCCEEDED:
                skipped_status += 1
                continue

            payment_datetime = datetime.fromtimestamp(
                int(payment['creation_date']), tz=timezone.utc)
            if not self.in_timeframe(payment_datetime):
                skipped_timeframe += 1
                continue

            value_satoshi = float_parser(str(payment.get('value_msat', 0))) / 1000
            fee_satoshi = float_parser(str(payment.get('fee_msat', 0))) / 1000
            payment_hash = (payment.get('payment_hash') or '').strip()

            tran = self._create_base_transaction(
                self.EXCHANGE,
                payment_datetime.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'withdrawal')

            tran['Type'] = 'Lightning payment'
            if value_satoshi > 0:
                tran['BTC'] = str(value_satoshi / SATOSHIS_PER_BTC)
            if fee_satoshi > 0:
                tran['Fee(BTC)'] = str(fee_satoshi / SATOSHIS_PER_BTC)

            tran['Comments'] = (
                f'Umbrel Lightning payment sent: {value_satoshi:.3f} sat; '
                f'Routing fee: {fee_satoshi:.3f} sat; Hash: {payment_hash}')

            transactions.append(tran)
            reviewable.append((payment_datetime.date(), value_satoshi, fee_satoshi, payment_hash))

        if skipped_status:
            logger.info(f'Skipped {skipped_status} Lightning payment(s) that did not succeed')
        if skipped_timeframe:
            logger.info(f'Skipped {skipped_timeframe} Lightning payment(s) outside the requested timeframe')

        if reviewable:
            logger.warning(
                f'{len(reviewable)} outgoing Lightning payment(s) recorded as transfers - only '
                f'the routing fee is treated as a disposal. Confirm none of these was a purchase '
                f'from a third party, which would make the amount sent a disposal too:')
            for payment_date, value_satoshi, fee_satoshi, payment_hash in reviewable:
                logger.warning(
                    f'  {payment_date}  {value_satoshi:>12.3f} sat  '
                    f'(fee {fee_satoshi:.3f} sat)  {payment_hash[:16]}')

        return transactions

    def _transform_forwards(self, forwards):
        """
        Transform routing income into daily "gain" + "buy" pairs.

        Individual forwards are worth a few satoshi each, so they are summed per
        UTC day. Market prices are daily, so aggregating loses no precision
        while keeping the output readable.
        """
        if not forwards:
            return []

        daily_fees = defaultdict(float)
        daily_counts = defaultdict(int)
        skipped = 0

        for event in forwards:
            event_datetime = datetime.fromtimestamp(int(event['timestamp']), tz=timezone.utc)
            if not self.in_timeframe(event_datetime):
                skipped += 1
                continue
            event_date = event_datetime.date()
            daily_fees[event_date] += float_parser(str(event.get('fee_msat', 0))) / 1000
            daily_counts[event_date] += 1

        if skipped:
            logger.info(f'Skipped {skipped} forwarding event(s) outside the requested timeframe')

        if not daily_fees:
            return []

        min_date, max_date = min(daily_fees), max(daily_fees)
        logger.info(
            f'Querying btcusd prices to value routing income on {len(daily_fees)} day(s) '
            f'({min_date} to {max_date})')
        btcusd_prices = self.crypto_provider.query('btcusd', min_date, max_date)

        transactions = []
        for event_date in sorted(daily_fees):
            fee_satoshi = daily_fees[event_date]
            btc_amount = fee_satoshi / SATOSHIS_PER_BTC
            rate = btcusd_prices.get(event_date.isoformat(), 0)
            if rate <= 0:
                raise ValueError(
                    f'Missing btcusd price for {event_date}; cannot value routing income')

            usd_value = btc_amount * rate
            datetime_str = f'{event_date.isoformat()}T23:59:59Z'
            comments = (
                f'Umbrel routing fees earned: {fee_satoshi:.3f} sat over '
                f'{daily_counts[event_date]} forward(s) on {event_date}')

            for operation, tag in (('gain', 'GAIN'), ('buy', 'BUY')):
                log = self._create_base_transaction(self.EXCHANGE, datetime_str, operation)
                log['Type'] = 'Routing'
                if operation == 'buy':
                    log['Pair'] = 'btcusd'
                log['BTC'] = str(btc_amount)
                log['USD'] = str(usd_value)
                log['BTCUSD'] = str(rate)
                log['Comments'] = f'{comments} [{tag}]'
                transactions.append(log)

        return transactions
