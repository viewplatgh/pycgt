import csv
from datetime import datetime
from logger import logger
from shared_def import CRYPTOS, FIATS, FIELDS, LOCALE_FIAT
from .base_transformer import BaseTransformer
from market_data_provider import MarketDataProviderFactory

class BitstampTransformer(BaseTransformer):
    """Transformer for Bitstamp exchange logs"""

    def __init__(self, input_files, output_file):
        super().__init__(input_files, output_file)
        self.forex_provider = MarketDataProviderFactory.create_forex_provider()

    def transform(self):
        """Transform Bitstamp CSV format to pycgt format"""
        logger.info(f"Processing Bitstamp logs from {len(self.input_files)} file(s)")

        transactions = []

        for input_file in self.input_files:
            logger.info(f"Reading {input_file}")
            with open(input_file, 'r') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    pycgt_transaction = self._convert_bitstamp_row(row)
                    if pycgt_transaction:
                        transactions.append(pycgt_transaction)

        transactions.sort(key=lambda x: x['Datetime'])
        locale_fiat_upper = LOCALE_FIAT.upper()
        locale_fiat_lower = LOCALE_FIAT.lower()
        forexpair = f'{locale_fiat_lower}usd'

        if locale_fiat_lower != 'usd':
            # Get date range for forex query
            start_datetime = datetime.fromisoformat(transactions[0]['Datetime'])
            end_datetime = datetime.fromisoformat(transactions[-1]['Datetime'])
            dayrate = self.forex_provider.query(forexpair, start_datetime.date(), end_datetime.date())

            # Autofill locale fiat amounts from USD
            for tran in transactions:
                tran_datetime = datetime.fromisoformat(tran['Datetime'])
                date_key = tran_datetime.date().isoformat()
                rate = dayrate.get(date_key, 0)
                if rate > 0:
                    tran[forexpair.upper()] = str(rate)
                    usd_value = float(tran['USD'] or 0)
                    locale_fiat_value = float(tran[locale_fiat_upper] or 0)
                    if usd_value > 0 and locale_fiat_value == 0:
                        tran[locale_fiat_upper] = str(round(usd_value / rate, 2))

                    fee_usd_value = float(tran['Fee(USD)'] or 0)
                    fee_locale_fiat_value = float(tran[f'Fee({locale_fiat_upper})'] or 0)
                    if fee_usd_value > 0 and fee_locale_fiat_value == 0:
                        tran[f'Fee({locale_fiat_upper})'] = str(round(fee_usd_value / rate, 2))
                else:
                    logger.warning(f"Missing {forexpair} rate for {date_key}, cannot convert USD to {locale_fiat_upper}")

        logger.info(f"Converted {len(transactions)} transactions")
        self.write_pycgt_csv(transactions)
        return transactions

    def _convert_bitstamp_row(self, row):
        """
        Convert a single Bitstamp row to pycgt format

        Bitstamp format:
        ID, Account, Type, Subtype, Datetime, Amount, Amount currency,
        Value, Value currency, Rate, Rate currency, Fee, Fee currency, Order ID

        Args:
            row: Dictionary representing a Bitstamp CSV row

        Returns:
            Dictionary with pycgt field names, or None if row should be skipped
        """
        transaction_type = row['Type']
        subtype = row['Subtype']  # Buy/Sell for Market transactions

        # Initialize pycgt transaction with default empty values from FIELDS
        pycgt_row = {field: '' for field in FIELDS.keys()}

        # Set basic transaction info
        pycgt_row['Type'] = transaction_type
        pycgt_row['Exchange'] = 'Bitstamp'
        pycgt_row['Datetime'] = row['Datetime']
        pycgt_row['Comments'] = f"Order ID: {row['Order ID']}" if row['Order ID'] else ''

        amount = row['Amount']
        amount_currency = row['Amount currency'].upper()
        value = row['Value']
        value_currency = row['Value currency'].upper()
        rate = row['Rate']
        fee = row['Fee']
        fee_currency = row['Fee currency'].upper()

        # Handle Market Buy/Sell transactions
        if transaction_type == 'Market' and subtype in ['Buy', 'Sell']:
            pycgt_row['Operation'] = subtype.lower()

            # Create trading pair (e.g., BTCUSD, ETHUSD)
            if value_currency:
                pycgt_row['Pair'] = f"{amount_currency}{value_currency}".lower()

            # Set crypto amount
            if amount_currency.lower() in CRYPTOS:
                pycgt_row[amount_currency] = amount

            # Set fiat value
            if value_currency.lower() in FIATS:
                pycgt_row[value_currency] = value

            # Set exchange rate
            if rate and value_currency:
                rate_pair = f"{amount_currency}{value_currency}".upper()
                if rate_pair in pycgt_row:
                    pycgt_row[rate_pair] = rate

            # Set fee
            if fee and fee_currency:
                fee_field = f"Fee({fee_currency})"
                if fee_field in pycgt_row:
                    pycgt_row[fee_field] = fee

        # Handle Deposit transactions
        elif transaction_type == 'Deposit':
            pycgt_row['Operation'] = 'deposit'

            if amount_currency.lower() in CRYPTOS:
                pycgt_row[amount_currency] = amount
            elif amount_currency.lower() in FIATS:
                pycgt_row[amount_currency] = amount

            # Set fee
            if fee and fee_currency:
                fee_field = f"Fee({fee_currency})"
                if fee_field in pycgt_row:
                    pycgt_row[fee_field] = fee

        # Handle Withdrawal transactions
        elif transaction_type == 'Withdrawal':
            pycgt_row['Operation'] = 'withdrawal'

            if amount_currency.lower() in CRYPTOS:
                pycgt_row[amount_currency] = amount
            elif amount_currency.lower() in FIATS:
                pycgt_row[amount_currency] = amount

            # Set fee
            if fee and fee_currency:
                fee_field = f"Fee({fee_currency})"
                if fee_field in pycgt_row:
                    pycgt_row[fee_field] = fee

        else:
            logger.warning(f"Skipping unsupported transaction type: {transaction_type}/{subtype}")
            return None

        return pycgt_row

