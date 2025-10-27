import csv
from datetime import datetime, timezone
from transformer.base_transformer import BaseTransformer
from shared_def import CRYPTOS, FIATS, FIELDS
from logger import logger


class ExodusTransformer(BaseTransformer):
    """
    Transformer for Exodus wallet CSV exports.

    Exodus CSV format:
    - DATE: ISO 8601 datetime with timezone (e.g., 2024-12-03T14:04:35.033Z)
    - TYPE: deposit, withdrawal, exchange
    - FROMPORTFOLIO: Source wallet name (e.g., exodus_0)
    - TOPORTFOLIO: Destination wallet name (e.g., exodus_0)
    - OUTAMOUNT: Amount sent out
    - OUTCURRENCY: Currency sent out
    - FEEAMOUNT: Fee amount
    - FEECURRENCY: Fee currency
    - FROMADDRESS: Source blockchain address
    - TOADDRESS: Destination blockchain address
    - OUTTXID: Outgoing transaction hash
    - OUTTXURL: Etherscan/block explorer URL for outgoing tx
    - INAMOUNT: Amount received
    - INCURRENCY: Currency received
    - INTXID: Incoming transaction hash
    - INTXURL: Block explorer URL for incoming tx
    - ORDERID: Order ID (for exchanges)
    - PERSONALNOTE: User's personal note
    """

    def transform(self):
        """Transform Exodus CSV to pycgt format"""
        logger.info(f"Processing Exodus logs from {len(self.input_files)} file(s)")

        transactions = []

        for input_file in self.input_files:
            logger.info(f"Reading {input_file}")
            with open(input_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self._convert_exodus_row(row, transactions)

        # Sort by datetime ascending
        transactions.sort(key=lambda x: x['Datetime'])

        # Auto-fill locale fiat and fees
        self.autofill_locale_fiat_and_fees(transactions)

        logger.info(f"Converted {len(transactions)} transactions")
        self.write_pycgt_csv(transactions)
        logger.info(f"Wrote {len(transactions)} transactions to {self.output_file}")

    def _convert_exodus_row(self, row, transactions):
        """Convert a single Exodus row to pycgt format transaction(s)"""
        transaction_type = row['TYPE'].strip().lower()
        datetime_str = row['DATE'].strip()

        if transaction_type == 'deposit':
            self._handle_deposit(row, datetime_str, transactions)
        elif transaction_type == 'withdrawal':
            self._handle_withdrawal(row, datetime_str, transactions)
        else:
            logger.warning(f"Unknown transaction type: {transaction_type}")

    def _handle_deposit(self, row, datetime_str, transactions):
        """Handle deposit transactions (incoming crypto)"""
        in_amount = row['INAMOUNT'].strip()
        in_currency = row['INCURRENCY'].strip().lower()

        if not in_amount or not in_currency:
            logger.warning(f"Skipping deposit with missing amount or currency: {row}")
            return

        # Validate currency
        if in_currency not in [c.lower() for c in CRYPTOS] and in_currency not in [f.lower() for f in FIATS]:
            logger.warning(f"Currency '{in_currency}' not in CRYPTOS or FIATS, skipping deposit")
            return

        # Create deposit transaction
        tran = self._create_base_transaction(datetime_str, 'deposit', row)
        tran['Type'] = 'Deposit'
        tran[in_currency.upper()] = in_amount

        # Build comments with additional fields
        comment_parts = [f"Exodus deposit: {in_amount} {in_currency.upper()}"]
        comment_parts.extend(self._build_additional_comments(row))
        tran['Comments'] = '; '.join(comment_parts)

        transactions.append(tran)

    def _handle_withdrawal(self, row, datetime_str, transactions):
        """Handle withdrawal transactions (outgoing crypto)"""
        out_amount = row['OUTAMOUNT'].strip()
        out_currency = row['OUTCURRENCY'].strip().lower()
        fee_amount = row['FEEAMOUNT'].strip()
        fee_currency = row['FEECURRENCY'].strip().lower()

        if not out_amount or not out_currency:
            logger.warning(f"Skipping withdrawal with missing amount or currency: {row}")
            return

        # Validate currency
        if out_currency not in [c.lower() for c in CRYPTOS] and out_currency not in [f.lower() for f in FIATS]:
            logger.warning(f"Currency '{out_currency}' not in CRYPTOS or FIATS, skipping withdrawal")
            return

        # Create withdrawal transaction
        tran = self._create_base_transaction(datetime_str, 'withdrawal', row)
        tran['Type'] = 'Withdrawal'
        # Make amount positive (Exodus uses negative amounts)
        tran[out_currency.upper()] = out_amount.lstrip('-')

        # Add fee if present
        if fee_amount and fee_currency:
            if fee_currency not in [c.lower() for c in CRYPTOS] and fee_currency not in [f.lower() for f in FIATS]:
                logger.warning(f"Fee currency '{fee_currency}' not in CRYPTOS or FIATS")
            else:
                fee_field = f'Fee({fee_currency.upper()})'
                tran[fee_field] = fee_amount.lstrip('-')

        # Build comments with additional fields
        comment_parts = [f"Exodus withdrawal: {out_amount} {out_currency.upper()}"]
        comment_parts.extend(self._build_additional_comments(row))
        tran['Comments'] = '; '.join(comment_parts)

        transactions.append(tran)

    def _build_additional_comments(self, row):
        """Build additional comment fields from Exodus row data"""
        comment_parts = []

        # Add portfolio information
        from_portfolio = row.get('FROMPORTFOLIO', '').strip()
        to_portfolio = row.get('TOPORTFOLIO', '').strip()
        if from_portfolio:
            comment_parts.append(f"From: {from_portfolio}")
        if to_portfolio:
            comment_parts.append(f"To: {to_portfolio}")

        # Add address information
        from_address = row.get('FROMADDRESS', '').strip()
        to_address = row.get('TOADDRESS', '').strip()
        if from_address:
            comment_parts.append(f"FromAddr: {from_address}")
        if to_address:
            comment_parts.append(f"ToAddr: {to_address}")

        # Add transaction URLs
        out_tx_url = row.get('OUTTXURL', '').strip()
        in_tx_url = row.get('INTXURL', '').strip()
        if out_tx_url:
            comment_parts.append(f"OutTx: {out_tx_url}")
        if in_tx_url:
            comment_parts.append(f"InTx: {in_tx_url}")

        # Add order ID
        order_id = row.get('ORDERID', '').strip()
        if order_id:
            comment_parts.append(f"OrderID: {order_id}")

        # Add personal note
        personal_note = row.get('PERSONALNOTE', '').strip()
        if personal_note:
            comment_parts.append(f"Note: {personal_note}")

        return comment_parts

    def _create_base_transaction(self, datetime_str, operation, row):
        """Create a base transaction dict with common fields"""
        tran = {field: '' for field in FIELDS.keys()}
        tran['Exchange'] = 'Exodus'
        tran['Datetime'] = datetime_str
        tran['Operation'] = operation

        return tran
