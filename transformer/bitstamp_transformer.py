import csv
from logger import logger
from shared_def import CRYPTOS, FIATS, FIELDS
from .base_transformer import BaseTransformer
from transaction import float_parser, datetime_parser


class BitstampTransformer(BaseTransformer):
    """Transformer for Bitstamp exchange logs"""

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


        transactions.sort(key=lambda x: datetime_parser(x['Datetime']))

        self.autofill_locale_fiat_and_fees(transactions)

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

        rate = row['Rate']
        amount = row['Amount']
        amount_currency = row['Amount currency'].upper()
        value = row['Value']
        float_rate = float_parser(rate)
        float_amount = float_parser(amount)
        if float_rate > 0 and float_amount > 0:
            value = str(float_rate * float_amount)
        value_currency = row['Value currency'].upper()
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

