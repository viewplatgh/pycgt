import csv
from transformer.base_transformer import BaseTransformer
from shared_def import CRYPTOS, FIATS
from logger import logger
from transaction import float_parser, datetime_parser


class KrakenTransformer(BaseTransformer):
    """
    Transforms Kraken spot ledger exports to pycgt format.

    Ledger rows are per-asset balance movements. Handled types:
      - deposit / withdrawal: transfers in and out. The asset itself is neither
        acquired nor disposed; any fee is paid in crypto and IS a disposal.
      - earn / reward: staking income. Recorded the same way the Etherscan and
        Nexo transformers record interest - a "gain" row for assessable income
        plus a "buy" row establishing the cost base of the crypto received.

    Kraken deducts its commission from the reward before it lands, so the
    balance moves by (amount - fee). That net figure is the amount actually
    received, and it is what gets booked as income; the gross and the
    commission are both recorded in Comments.
    """

    EXCHANGE = 'Kraken'

    # Kraken prefixes legacy assets (X = crypto, Z = fiat) and suffixes staked
    # variants (.S / .M / .F / .B). Normalise both to plain pycgt symbols.
    ASSET_ALIASES = {
        'XBT': 'BTC',
        'XXBT': 'BTC',
        'XETH': 'ETH',
        'XLTC': 'LTC',
        'XETC': 'ETC',
        'ZUSD': 'USD',
        'ZAUD': 'AUD',
        'ZEUR': 'EUR',
    }
    STAKED_SUFFIXES = ('.S', '.M', '.F', '.B')

    INTERNAL_TYPES = {'transfer', 'spend', 'receive', 'adjustment', 'rollover'}

    def _normalise_asset(self, asset):
        """Map a Kraken asset code onto a configured pycgt symbol"""
        asset = (asset or '').strip().upper()
        for suffix in self.STAKED_SUFFIXES:
            if asset.endswith(suffix):
                asset = asset[:-len(suffix)]
                break

        asset = self.ASSET_ALIASES.get(asset, asset)

        if asset.lower() not in [c.lower() for c in CRYPTOS] + [f.lower() for f in FIATS]:
            raise ValueError(
                f"Kraken asset '{asset}' is not configured in config.toml "
                f"([data].cryptos / [data].fiats)")
        return asset

    def transform(self):
        """Transform Kraken ledger CSV format to pycgt format"""
        logger.info(f"Processing Kraken ledgers from {len(self.input_files)} file(s)")

        rows = []
        skipped = 0
        for input_file in self.input_files:
            logger.info(f"Reading {input_file}")
            with open(input_file, 'r', newline='') as csvfile:
                for row in csv.DictReader(csvfile):
                    if not (row.get('time') or '').strip():
                        continue
                    tran_datetime = datetime_parser(row['time'])
                    if not self.in_timeframe(tran_datetime):
                        skipped += 1
                        continue
                    rows.append((row, tran_datetime))

        if skipped:
            logger.info(f"Skipped {skipped} row(s) outside the requested timeframe")

        if not rows:
            raise ValueError('No Kraken ledger rows to transform')

        reward_prices = self._query_reward_prices(rows)

        transactions = []
        for row, tran_datetime in rows:
            transactions.extend(self._convert_row(row, tran_datetime, reward_prices))

        transactions.sort(key=lambda x: datetime_parser(x['Datetime']))

        self.autofill_locale_fiat_and_fees(transactions)

        self.write_pycgt_csv(transactions)
        return transactions

    def _query_reward_prices(self, rows):
        """
        Bulk-query <asset>/USD prices for the dates carrying earn rewards.

        The ledger has no price column, so income rows need market data to be
        valued. Only reward dates are queried, one range per asset.
        """
        dates_by_asset = {}
        for row, tran_datetime in rows:
            if (row.get('type') or '').strip().lower() != 'earn':
                continue
            asset = self._normalise_asset(row.get('asset'))
            if asset.lower() in [f.lower() for f in FIATS]:
                continue
            dates_by_asset.setdefault(asset, set()).add(tran_datetime.date())

        prices = {}
        for asset, dates in dates_by_asset.items():
            pair = f'{asset.lower()}usd'
            min_date, max_date = min(dates), max(dates)
            logger.info(f"Querying {pair} prices for {len(dates)} reward date(s) ({min_date} to {max_date})")
            prices[asset] = self.crypto_provider.query(pair, min_date, max_date)
        return prices

    def _convert_row(self, row, tran_datetime, reward_prices):
        """Convert one Kraken ledger row into zero or more pycgt transactions"""
        ledger_type = (row.get('type') or '').strip().lower()
        subtype = (row.get('subtype') or '').strip().lower()
        asset = self._normalise_asset(row.get('asset'))
        amount = float_parser(row.get('amount', ''))
        fee = float_parser(row.get('fee', ''))
        txid = (row.get('txid') or '').strip()
        refid = (row.get('refid') or '').strip()
        datetime_str = row['time']

        if ledger_type in self.INTERNAL_TYPES:
            logger.info(f"Skipping internal Kraken movement: {ledger_type} {txid}")
            return []

        if ledger_type == 'earn':
            return self._create_reward_logs(
                datetime_str, tran_datetime, asset, amount, fee, subtype, refid, reward_prices)

        if ledger_type in ('deposit', 'withdrawal'):
            tran = self._create_base_transaction(self.EXCHANGE, datetime_str, ledger_type)
            tran['Type'] = ledger_type.capitalize()
            if amount != 0:
                tran[asset] = str(abs(amount))
            if fee > 0:
                tran[f'Fee({asset})'] = str(fee)
            tran['Comments'] = (
                f'Kraken {ledger_type}: {abs(amount)} {asset}; '
                f'Fee: {fee} {asset}; Ledger: {txid}; Ref: {refid}')
            return [tran]

        raise ValueError(
            f"Unsupported Kraken ledger type: '{ledger_type}' (subtype '{subtype}', "
            f"ledger id {txid}). Trades need refid pairing and are not handled yet.")

    def _create_reward_logs(self, datetime_str, tran_datetime, asset, amount, fee,
                            subtype, refid, reward_prices):
        """
        Create the "gain" + "buy" pair for a staking reward.

        Args:
            amount: gross reward credited by Kraken
            fee: Kraken's commission, deducted before the reward lands
        """
        net_amount = amount - fee
        if net_amount <= 0:
            logger.warning(f"Kraken reward {refid} nets to {net_amount} {asset}, skipped")
            return []

        date_key = tran_datetime.date().isoformat()
        rate = reward_prices.get(asset, {}).get(date_key, 0)
        if rate <= 0:
            raise ValueError(
                f"Missing {asset}USD price for {date_key}; cannot value Kraken reward {refid}")

        usd_value = net_amount * rate
        comments = (
            f'Kraken earn {subtype}: {net_amount} {asset} net '
            f'(gross {amount}, commission {fee}); Ref: {refid}')

        logs = []
        for operation, tag in (('gain', 'GAIN'), ('buy', 'BUY')):
            log = self._create_base_transaction(self.EXCHANGE, datetime_str, operation)
            log['Type'] = 'Interest'
            if operation == 'buy':
                log['Pair'] = f'{asset.lower()}usd'
            log[asset] = str(net_amount)
            log['USD'] = str(usd_value)
            log[f'{asset}USD'] = str(rate)
            log['Comments'] = f'{comments} [{tag}]'
            logs.append(log)

        return logs
