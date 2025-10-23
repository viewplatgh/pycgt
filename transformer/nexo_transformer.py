import csv
from logger import logger
from shared_def import CRYPTOS, FIATS, FIELDS
from .base_transformer import BaseTransformer
from transaction import float_parser, datetime_parser


class NexoTransformer(BaseTransformer):
    """Transformer for Nexo exchange logs"""

    def transform(self):
        """Transform Nexo CSV format to pycgt format"""
        logger.info(f"Processing Nexo logs from {len(self.input_files)} file(s)")

        if 'usd' not in FIATS:
            raise ValueError("USD must be in fiats configuration for Nexo transformer")

        transactions = []

        for input_file in self.input_files:
            logger.info(f"Reading {input_file}")
            with open(input_file, 'r') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    pycgt_transactions = self._convert_nexo_row(row)
                    if pycgt_transactions:
                        # Can return multiple transactions (e.g., Interest creates 2 logs)
                        if isinstance(pycgt_transactions, list):
                            transactions.extend(pycgt_transactions)
                        else:
                            transactions.append(pycgt_transactions)

        transactions.sort(key=lambda x: datetime_parser(x['Datetime']))

        self.autofill_locale_fiat_and_fees(transactions)

        self.write_pycgt_csv(transactions)
        return transactions

    def _convert_nexo_row(self, row):
        """
        Convert a single Nexo row to pycgt format

        Nexo format:
        Transaction, Type, Input Currency, Input Amount, Output Currency,
        Output Amount, USD Equivalent, Fee, Fee Currency, Details, Date / Time (UTC)

        Args:
            row: Dictionary representing a Nexo CSV row

        Returns:
            Dictionary with pycgt field names, list of dictionaries for Interest type,
            or None if row should be skipped
        """
        transaction_type = row['Type']
        transaction_id = row['Transaction']
        details = row['Details']
        datetime = row['Date / Time (UTC)']

        input_currency = row['Input Currency'].upper()
        output_currency = row['Output Currency'].upper()
        output_amount = row['Output Amount']

        input_currency_lower = input_currency.lower()
        output_currency_lower = output_currency.lower()

        if input_currency_lower not in CRYPTOS + FIATS or output_currency_lower not in CRYPTOS + FIATS:
            raise ValueError(f"Missing configuration for currency: input={input_currency}, output={output_currency}")

        # Parse USD Equivalent (remove $ and ,)
        usd_equivalent = row['USD Equivalent'].replace('$', '').replace(',', '')

        fee = row['Fee']
        fee_currency = row['Fee Currency'].upper() if row['Fee Currency'] != '-' else ''

        # Build comments field
        comments = f"Transaction: {transaction_id} | {details}"

        # Handle Interest transactions - create TWO pycgt logs
        if transaction_type == 'Interest' or transaction_type == 'Fixed Term Interest':
            return self._create_interest_logs(
                datetime, output_currency, output_amount, usd_equivalent, comments
            )

        # Initialize pycgt transaction with default empty values from FIELDS
        pycgt_row = {field: '' for field in FIELDS.keys()}

        # Set basic transaction info
        pycgt_row['Type'] = transaction_type
        pycgt_row['Exchange'] = 'Nexo'
        pycgt_row['Datetime'] = datetime
        pycgt_row['Comments'] = comments

        # Handle Top up Crypto (deposits)
        if transaction_type == 'Top up Crypto' or transaction_type == 'Withdrawal':
            _operationMap = {
                'Top up Crypto': 'deposit',
                'Withdrawal': 'withdrawal'
            }
            pycgt_row['Operation'] = _operationMap[transaction_type]
            pycgt_row[output_currency] = output_amount
            # Set fee
            if fee and fee != '-' and fee_currency:
                fee_field = f"Fee({fee_currency})"
                if fee_field in pycgt_row:
                    pycgt_row[fee_field] = fee

        # Skip Locking/Unlocking Term Deposit (internal transfers)
        elif transaction_type in ['Locking Term Deposit', 'Unlocking Term Deposit']:
            logger.info(f"Skipping internal transfer: {transaction_type} for {transaction_id}")
            return None

        else:
            raise ValueError(f"Unsupported transaction type: {transaction_type}")

        return pycgt_row

    def _create_interest_logs(self, datetime, currency, amount, usd_equivalent, comments):
        """
        Create two pycgt logs for Interest transactions per ATO rules:
        1. "gain" operation - Record taxable income immediately (no CGT discount)
        2. "buy" operation - Establish cost base for future disposal

        Args:
            datetime: Transaction datetime
            currency: Crypto currency earned
            amount: Amount of crypto earned
            usd_equivalent: USD value at time of earning
            comments: Transaction details

        Returns:
            List of two pycgt transaction dictionaries
        """
        logs = []

        # Calculate buy price from amount and USD equivalent
        float_amount = float_parser(amount)
        if float_amount <= 0:
            raise ValueError(f"Interest amount must be greater than zero: {comments}")       
        float_usd = float_parser(usd_equivalent)
        if float_usd <= 0:
            logger.warning(f"Skipping invalid USD equivalent for interest: {comments}")
            return None

        price_per_unit = float_usd / float_amount
        rate_pair = f"{currency}USD"

        # Log 1: "gain" operation for taxable income
        gain_log = {field: '' for field in FIELDS.keys()}
        gain_log['Operation'] = 'gain'
        gain_log['Exchange'] = 'Nexo'
        gain_log['Datetime'] = datetime
        gain_log['Type'] = 'Interest'
        gain_log['Comments'] = f"{comments} [GAIN]"
        gain_log[currency] = amount
        gain_log['USD'] = usd_equivalent
        gain_log[rate_pair] = str(price_per_unit)

        logs.append(gain_log)

        # Log 2: "buy" operation to establish cost base
        buy_log = {field: '' for field in FIELDS.keys()}
        buy_log['Operation'] = 'buy'
        buy_log['Exchange'] = 'Nexo'
        buy_log['Datetime'] = datetime
        buy_log['Type'] = 'Interest'
        buy_log['Pair'] = f"{currency.lower()}usd"
        buy_log['Comments'] = f"{comments} [BUY]"
        buy_log[currency] = amount
        buy_log['USD'] = usd_equivalent
        buy_log[rate_pair] = str(price_per_unit)

        logs.append(buy_log)

        return logs
