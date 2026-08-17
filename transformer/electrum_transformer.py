import csv
from datetime import datetime, timezone
from transformer.base_transformer import BaseTransformer
from shared_def import LOCALE_FIAT
from logger import logger
from transaction import float_parser

SATOSHIS_PER_BTC = 100000000


class ElectrumTransformer(BaseTransformer):
    """
    Transforms Electrum wallet history exports to pycgt format.

    Electrum rows are movements between wallets the taxpayer controls, so the
    BTC itself is neither acquired nor disposed. The on-chain network fee is
    paid in BTC and IS a disposal, so it is carried in Fee(BTC), where
    Portfolio.process_fees_incurred_transactions turns it into a disposal plus
    an incidental loss.

    Timezone: Electrum writes `timestamp` in the exporting machine's LOCAL time
    with no offset. Left as-is, datetime_parser would read it as UTC and shift
    every row by the local offset - enough to move a 30 June transaction into
    the wrong financial year. Naive values are therefore interpreted as local
    time and converted to UTC, which also handles daylight saving correctly.
    """

    EXCHANGE = 'Electrum'
    ELECTRUM_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

    def _to_utc(self, timestamp_str):
        """Interpret an Electrum local-time timestamp and return it as UTC."""
        naive = datetime.strptime(timestamp_str.strip(), self.ELECTRUM_DATETIME_FORMAT)
        # astimezone() on a naive datetime treats it as local wall-clock time
        return naive.astimezone(timezone.utc)

    def transform(self):
        """Transform Electrum history CSV format to pycgt format"""
        logger.info(f"Processing Electrum logs from {len(self.input_files)} file(s)")

        transactions = []
        skipped = 0

        for input_file in self.input_files:
            logger.info(f"Reading {input_file}")
            with open(input_file, 'r', newline='') as csvfile:
                for row in csv.DictReader(csvfile):
                    tran_datetime = self._to_utc(row['timestamp'])
                    if not self.in_timeframe(tran_datetime):
                        skipped += 1
                        continue

                    tran = self._convert_row(row, tran_datetime)
                    if tran:
                        transactions.append(tran)

        if skipped:
            logger.info(f"Skipped {skipped} row(s) outside the requested timeframe")

        if not transactions:
            raise ValueError('No Electrum rows to transform')

        transactions.sort(key=lambda x: x['Datetime'])

        self.autofill_locale_fiat_and_fees(transactions)

        self.write_pycgt_csv(transactions)
        return transactions

    def _convert_row(self, row, tran_datetime):
        """Convert a single Electrum history row to a pycgt transaction"""
        chain_amount = float_parser(row.get('amount_chain_bc', ''))
        lightning_amount = float_parser(row.get('amount_lightning_bc', ''))
        fee_satoshi = float_parser(row.get('network_fee_satoshi', ''))
        label = (row.get('label') or '').strip()
        tx_hash = (row.get('oc_transaction_hash') or '').strip()
        payment_hash = (row.get('ln_payment_hash') or '').strip()

        if lightning_amount != 0:
            logger.warning(
                f"Electrum row {tx_hash or payment_hash} carries a Lightning amount "
                f"({lightning_amount}); only the on-chain amount is transformed")

        amount = chain_amount if chain_amount != 0 else lightning_amount
        if amount == 0 and fee_satoshi == 0:
            logger.info(f"Skipping empty Electrum row: {tx_hash or payment_hash}")
            return None

        tran = self._create_base_transaction(
            self.EXCHANGE,
            tran_datetime.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'withdrawal' if amount < 0 else 'deposit')

        tran['Type'] = 'Transfer'
        if amount != 0:
            # Electrum's amount is the net effect on the wallet, fee included
            tran['BTC'] = str(abs(amount))
        if fee_satoshi > 0:
            tran['Fee(BTC)'] = str(fee_satoshi / SATOSHIS_PER_BTC)

        # The export carries a fiat column but this wallet's rows leave it empty;
        # only trust it when it is actually populated, otherwise let autofill run.
        fiat_fee = float_parser(row.get('fiat_fee', ''))
        if fiat_fee > 0:
            tran[f'Fee({LOCALE_FIAT.upper()})'] = str(fiat_fee)

        tran['Comments'] = (
            f'Electrum {"send" if amount < 0 else "receive"}: {abs(amount)} BTC; '
            f'Fee: {fee_satoshi:.0f} sat; Label: {label}; Hash: {tx_hash}')

        return tran
