import csv
from datetime import datetime
from collections import defaultdict
from logger import logger
from shared_def import CRYPTOS, FIATS, FIELDS, LOCALE_FIAT
from .base_transformer import BaseTransformer
from transaction import float_parser


class IndependentReserveTransformer(BaseTransformer):
    """Transformer for Independent Reserve exchange logs"""

    def __init__(self, input_files, output_file):
        super().__init__(input_files, output_file)

    def transform(self):
        """Transform Independent Reserve CSV format to pycgt format"""
        logger.info(f"Processing Independent Reserve logs from {len(self.input_files)} file(s)")

        transactions = []

        for input_file in self.input_files:
            logger.info(f"Reading {input_file}")
            with open(input_file, 'r') as csvfile:
                # Check and skip 'sep=,' line if present
                first_line = csvfile.readline()
                if not first_line.strip().startswith('sep='):
                    # Not a sep= line, reset to beginning
                    csvfile.seek(0)

                # Read and strip field names
                header_line = csvfile.readline()
                fieldnames = [field.strip() for field in header_line.strip().split(',')]
                reader = csv.DictReader(csvfile, fieldnames=fieldnames)

                # Detect log type from headers
                if not self._is_rollup_format(reader.fieldnames):
                    raise ValueError(
                        f"Unsupported Independent Reserve log format in {input_file}. "
                        "Only 'rollup' format is supported. Please export using the rollup format."
                    )

                rows = list(reader)
                grouped_transactions = self._group_transactions(rows)

                for group in grouped_transactions:
                    pycgt_transaction = self._convert_ir_group(group)
                    if pycgt_transaction:
                        transactions.append(pycgt_transaction)

        transactions.sort(key=lambda x: x['Datetime'])
        logger.info(f"Converted {len(transactions)} transactions")
        self.write_pycgt_csv(transactions)
        return transactions

    def _is_rollup_format(self, fieldnames):
        """
        Check if the CSV is in rollup format

        Rollup format has: Settlement Date, Date, Type, Currency, Order Guid, Credit, Debit, Comment, BlockchainTransaction
        Breakdown format has: Settled, Date, TransactionGuid, TradeGuid, OrderGuid, Type, Status, Currency, Credit, Debit, Balance, Comment, BlockchainTransaction

        Args:
            fieldnames: List of CSV column names

        Returns:
            True if rollup format, False if breakdown format
        """
        has_settlement_date = 'Settlement Date' in fieldnames
        has_settled = 'Settled' in fieldnames

        if has_settlement_date:
            return True

        if has_settled:
            return False

        raise ValueError("Unable to determine Independent Reserve log format")

    def _group_transactions(self, rows):
        """
        Group transactions by Order Guid or BlockchainTransaction

        Args:
            rows: List of CSV row dictionaries

        Returns:
            List of transaction groups (each group is a list of related rows)
        """
        groups = defaultdict(list)
        standalone_counter = 0

        for row in rows:
            order_guid = row.get('Order Guid', '').strip()
            blockchain_tx = row.get('BlockchainTransaction', '').strip()

            # Group by Order Guid first, then by BlockchainTransaction
            if order_guid:
                groups[('order', order_guid)].append(row)
            elif blockchain_tx:
                groups[('blockchain', blockchain_tx)].append(row)
            else:
                # Standalone transaction with unique key
                groups[('standalone', standalone_counter)].append(row)
                standalone_counter += 1

        return list(groups.values())

    def _convert_ir_group(self, group):
        """
        Convert a group of related IR rows into a single pycgt transaction

        Args:
            group: List of related IR row dictionaries

        Returns:
            Dictionary with pycgt field names, or None if group should be skipped
        """
        if not group:
            return None

        # Analyze the group to determine transaction type
        types = [row['Type'] for row in group]

        # Initialize pycgt transaction with default empty values
        pycgt_row = {field: '' for field in FIELDS.keys()}

        # Use the first row's date and settlement date
        first_row = group[0]
        pycgt_row['Datetime'] = first_row['Date']
        pycgt_row['Exchange'] = 'IndependentReserve'

        # Handle different transaction type combinations
        if 'Trade' in types:
            return self._convert_trade_group(group, pycgt_row)
        elif 'Withdrawal' in types:
            return self._convert_withdrawal_group(group, pycgt_row)
        elif len(group) == 1:
            return self._convert_single_row_group(group, pycgt_row)
        else:
            raise ValueError(f"Unexpected transaction: {group}")

    def _convert_trade_group(self, group, pycgt_row):
        """
        Convert a Trade group (with potential Brokerage and GST fees) to pycgt format

        Trade logic:
        - Credit = target currency (what you bought/received)
        - Debit = source currency (what you spent/sold)
        - If crypto is credited: it's a buy operation
        - If crypto is debited: it's a sell operation
        - Brokerage and GST are combined as fees

        Args:
            group: List of IR row dictionaries
            pycgt_row: Partially filled pycgt transaction dictionary

        Returns:
            Complete pycgt transaction dictionary
        """
        trade_rows = [r for r in group if r['Type'] == 'Trade']
        brokerage_rows = [r for r in group if r['Type'] == 'Brokerage']
        gst_rows = [r for r in group if r['Type'] == 'GST']

        if len(trade_rows) != 2:
            logger.warning(f"Expected 2 Trade rows in group, found {len(trade_rows)}")
            return None

        # Identify credit and debit rows
        credit_row = None
        debit_row = None

        for row in trade_rows:
            credit = float_parser(row['Credit'])
            debit = float_parser(row['Debit'])

            if credit > 0:
                credit_row = row
            if debit > 0:
                debit_row = row

        if not credit_row or not debit_row:
            logger.warning("Could not identify credit and debit rows in Trade group")
            return None

        credit_currency = credit_row['Currency'].upper()
        debit_currency = debit_row['Currency'].upper()
        credit_amount = credit_row['Credit']
        debit_amount = debit_row['Debit']

        credit_currency_lower = credit_currency.lower()
        debit_currency_lower = debit_currency.lower()

        buy_pair = f"{credit_currency}{debit_currency}".lower()
        sell_pair = f"{debit_currency}{credit_currency}".lower()
    
        pycgt_row[debit_currency] = debit_amount
        pycgt_row[credit_currency] = credit_amount
        if credit_currency_lower in CRYPTOS:
            pycgt_row['Pair'] = buy_pair
            pycgt_row['Operation'] = 'buy'
        elif debit_currency_lower in CRYPTOS:
            pycgt_row['Pair'] = sell_pair
            pycgt_row['Operation'] = 'sell'
        else:
            logger.warning(f"Skipping transaction neither credit nor debit currency is crypto in Trade group: {credit_currency}, {debit_currency}")
            return None

        # Aggregate Brokerage and GST fees by currency
        total_fees = defaultdict(float)
        for row in brokerage_rows + gst_rows:
            currency = row['Currency'].upper()
            debit = float_parser(row['Debit'])
            if debit > 0:
                total_fees[currency] += debit

        # Set fees in pycgt format
        for currency, fee_amount in total_fees.items():
            fee_field = f"Fee({currency})"
            if fee_field in pycgt_row:
                pycgt_row[fee_field] = str(fee_amount)

        comments = group[0].get('Comment', '').strip()
        pycgt_row['Comments'] = comments
        order_guid = group[0].get('Order Guid', '').strip()
        if order_guid:
            pycgt_row['Comments'] = f"{comments + ', ' if comments else ''}Order Guid: {order_guid}"

        pycgt_row['Type'] = 'Market'
        return pycgt_row

    def _convert_withdrawal_group(self, group, pycgt_row):
        """
        Convert a Withdrawal group (with potential Withdrawal Fee) to pycgt format

        Args:
            group: List of IR row dictionaries
            pycgt_row: Partially filled pycgt transaction dictionary

        Returns:
            Complete pycgt transaction dictionary
        """        
        if len(group) != 2:
            raise ValueError(f"Expected 2 rows in Withdrawal group, found {len(group)}")
        currency = group[0]['Currency'].upper()
        if not currency or currency != group[1]['Currency'].upper():
            raise ValueError("Bad currency in Withdrawal group")

        withdrawal_row = None
        withdrawal_fee_row = None
        for row in group:
            row_type = row['Type']
            if row_type == 'Withdrawal':
                withdrawal_row = row
            elif row_type == 'Withdrawal Fee':
                withdrawal_fee_row = row
            else:
                raise ValueError(f"Unexpected row type in Withdrawal group: {row_type}")

        pycgt_row['Operation'] = 'withdrawal'
        pycgt_row['Type'] = 'Withdrawal'

        # Set withdrawal amount
        debit_amount = withdrawal_row['Debit']
        pycgt_row[currency] = debit_amount

        # Set withdrawal fee
        fee_field = f"Fee({currency})"
        pycgt_row[fee_field] = withdrawal_fee_row['Debit']

        comments = group[0].get('Comment', '').strip()
        pycgt_row['Comments'] = comments
        blockchain_tx = withdrawal_row.get('BlockchainTransaction', '').strip()
        if blockchain_tx:
            pycgt_row['Comments'] = f"{comments + ', ' if comments else ''}BlockchainTransaction: {blockchain_tx}"

        return pycgt_row

    def _convert_single_row_group(self, group, pycgt_row):
        """
        Convert a single IR row to pycgt format

        Args:
            group: List of IR row dictionaries (should be a single row)
            pycgt_row: Partially filled pycgt transaction dictionary

        Returns:
            Complete pycgt transaction dictionary
        """
        if len(group) != 1:
            raise ValueError(f"Expected 1 row, found {len(group)}")

        single_row = group[0]
        if float_parser(single_row['Debit']) > 0:
            raise ValueError("Unexpected debit value in single row transaction")

        currency = single_row['Currency'].upper()

        pycgt_row['Operation'] = single_row['Type'].lower()
        pycgt_row['Type'] = single_row['Type']
        pycgt_row[currency] = single_row['Credit']

        comments = single_row.get('Comment', '').strip()
        pycgt_row['Comments'] = comments
        blockchain_tx = single_row.get('BlockchainTransaction', '').strip()
        if blockchain_tx:
            pycgt_row['Comments'] = f"{comments + ', ' if comments else ''}BlockchainTransaction: {blockchain_tx}"

        return pycgt_row
