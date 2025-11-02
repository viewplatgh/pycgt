import csv
from datetime import datetime, timezone
from transformer.base_transformer import BaseTransformer
from shared_def import FIELDS
from logger import logger
from transaction import float_parser, datetime_parser


class EtherscanTransformer(BaseTransformer):
    """
    Transforms Etherscan CSV exports to pycgt format.

    Handles 3 types of Etherscan exports:
    1. withdrawal (beacon-withdrawal): Staking rewards, no Transaction Hash
    2. general (transactions): Regular ETH transfers
    3. erc-20 (token-transfers): ERC-20 token transfers

    Types 2 and 3 have Transaction Hash and are joined together before transformation.
    """

    FILE_TYPE_WITHDRAWAL = 'withdrawal'
    FILE_TYPE_GENERAL = 'general'
    FILE_TYPE_ERC20 = 'erc-20'

    def __init__(self, input_files, output_file=None):
        """
        Initialize with list of input files (can be 1-4 files).

        Args:
            input_files: List of CSV file paths
            output_file: Optional output file path
        """
        super().__init__(input_files[0] if len(input_files) == 1 else input_files, output_file)
        self.input_files = input_files if isinstance(input_files, list) else [input_files]

    def _identify_file_type(self, csv_file_path):
        """
        Identify the type of Etherscan CSV file by examining its columns.

        Returns:
            One of: FILE_TYPE_WITHDRAWAL, FILE_TYPE_GENERAL, FILE_TYPE_ERC20
        """
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames

            # Withdrawal type
            if set(['Index', 'Blockno', 'UnixTimestamp', 'DateTime (UTC)', 'Validator Index', 'Recipient', 'Value']).issubset(headers):
                return self.FILE_TYPE_WITHDRAWAL

            # ERC-20 type
            if set(['Transaction Hash', 'Blockno', 'UnixTimestamp', 'DateTime (UTC)', 'From', 'To', 'TokenValue', 'USDValueDayOfTx', 'ContractAddress', 'TokenName', 'TokenSymbol']).issubset(headers):
                return self.FILE_TYPE_ERC20

            # General type
            if set(['Transaction Hash', 'Blockno', 'UnixTimestamp', 'DateTime (UTC)', 'From', 'To', 'ContractAddress', 'Value_IN(ETH)', 'Value_OUT(ETH)', 'TxnFee(ETH)', 'TxnFee(USD)', 'Historical $Price/Eth', 'Status', 'ErrCode', 'Method']).issubset(headers):
                return self.FILE_TYPE_GENERAL
            
            raise ValueError(f'Unrecognized Etherscan CSV format in file: {csv_file_path}')

    def _transform_withdrawal_file(self, file_path):
        """
        Transform beacon-withdrawal file (staking rewards).

        Treats each row as "Interest":
        - One "gain" transaction (taxable income)
        - One "buy" transaction (establishes cost base)

        Returns:
            List of transaction dicts
        """
        transactions = []

        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Extract data
                blockno = row.get('Blockno', '').strip()
                datetime_utc = row.get('DateTime (UTC)', '').strip()
                eth_value = row.get('Value', '').strip().replace(' ETH', '').strip()

                eth_amount = float_parser(eth_value)

                # Transaction 1: "gain" operation (taxable income)
                gain_tran = self._create_base_transaction('Etherscan', datetime_utc, 'gain', row)
                gain_tran['Type'] = 'Interest'
                gain_tran['ETH'] = str(eth_amount)
                gain_tran['Comments'] = f'Etherscan beacon withdrawal: {eth_amount} ETH; Blockno: {blockno}'
                transactions.append(gain_tran)

                # Transaction 2: "buy" operation (establishes cost base)
                buy_tran = self._create_base_transaction('Etherscan', datetime_utc, 'buy', row)
                buy_tran['Type'] = 'Interest'
                buy_tran['Pair'] = 'ethusd'
                buy_tran['ETH'] = str(eth_amount)
                buy_tran['Comments'] = f'Etherscan beacon withdrawal (cost base): {eth_amount} ETH; Blockno: {blockno}'
                transactions.append(buy_tran)

        return transactions

    def _group_erc20_transactions_by_hash(self, erc20_files):
        """
        Group ERC-20 transactions by Transaction Hash.

        Args:
            erc20_files: List of ERC-20 CSV file paths
        Returns:
            Dict mapping Transaction Hash to list of ERC-20 rows
        """
        grouped = {}
        for file_path in erc20_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    tx_hash = row.get('Transaction Hash', '').strip()
                    if tx_hash not in grouped:
                        grouped[tx_hash] = []
                    grouped[tx_hash].append(row)
        return grouped
    
    def _prepare_transaction(self, general_row, operation):
        datetime_str = general_row.get('DateTime (UTC)', '').strip()
        return super()._create_base_transaction('Etherscan', datetime_str, operation)

    def _transform_trading_transaction(self, general_row, erc20_rows):
        """
        Transform a trading transaction (buy/sell/swap) using general and ERC-20 rows.

        Args:
            general_row: Dict representing the general transaction row
            erc20_rows: List of dicts representing associated ERC-20 rows

        Returns:
            one pycgt transaction
        """
        # TODO: combine into one transaction, it's to buy erc20_rows[1]['TokenSymbol'] & sell erc20_rows[0]['TokenSymbol']
        # TODO: figure out PAIR, transaction fees, ETHUSD rate, etc.
        tran = self._prepare_transaction(general_row, 'buy')
        return tran

    def _transform_one_general_transaction(self, general_row):
        """
        Transform a single general transaction (without associated ERC-20).

        Args:
            general_row: Dict representing the general transaction row

        Returns:
            one pycgt transaction
        """
        tran = self._prepare_transaction(general_row, 'deposit') # regard any kind of money moving as 'deposit'
        # TODO: figure out transaction fees, ETHUSD rate, Comments etc.
        return tran

    def _transform_joinable_transfer_transaction(self, general_row, erc20_row):
        """
        Transform a transfer transaction (deposit/withdrawal, money moving) using linked one general and one ERC-20 row.

        Args:
            general_row: Dict representing the general transaction row
            erc20_row: Dict representing the associated ERC-20 row

        Returns:
            pycgt transaction dict
        """
        tran = self._prepare_transaction(general_row, 'deposit') # regard any kind of money moving as 'deposit'
        # TODO: figure out transaction fees, ETHUSD rate, Comments etc. may call _transform_one_general_transaction to avoid duplication
        return tran
    
    def _join_transform_general_and_erc20_by_hash(self, general_files, erc20_grouped):
        """
        Join general files and grouped erc-20 by Transaction Hash.

        Args:
            general_files: List of general type transaction CSV file paths
            erc20_grouped: Dict from _group_erc20_transactions_by_hash

        Returns:
            List of transactions in pycgt format
        """
        transactions = []

        for general_file in general_files:
            with open(general_file, 'r', encoding='utf-8') as gf:
                reader = csv.DictReader(gf)
                for row in reader:
                    tran = None
                    tx_hash = row.get('Transaction Hash', '').strip()
                    grouped_erc20_transactions = erc20_grouped.get(tx_hash, [])
                    if len(grouped_erc20_transactions) > 2:
                        raise ValueError(f'Unexpected more than 2 associated ERC-20 transfers, transaction hash {tx_hash}')
                    elif len(grouped_erc20_transactions) == 2:
                        tran = self._transform_trading_transaction(row, grouped_erc20_transactions)
                    elif len(grouped_erc20_transactions) == 1:
                        tran = self._transform_joinable_transfer_transaction(row, grouped_erc20_transactions[0])
                    else:
                        tran = self._transform_one_general_transaction(row)

                    if tran:
                        transactions.append(tran)
                    else:
                        raise ValueError(f'Unexpected missing transformed transaction for hash {tx_hash}')

        return transactions

    def transform(self):
        """
        Main transformation logic.

        Process files based on type:
        - withdrawal type: Transform directly (like Nexo interest)
        - Other types: Join by Transaction Hash, then transform
        """
        # Separate files by type
        withdrawal_files = []
        general_files = []
        erc20_files = []

        for file_path in self.input_files:
            file_type = self._identify_file_type(file_path)
            logger.info(f'Identified {file_path} as type: {file_type}')

            if file_type == self.FILE_TYPE_WITHDRAWAL:
                withdrawal_files.append(file_path)
            elif file_type == self.FILE_TYPE_GENERAL:
                general_files.append(file_path)
            elif file_type == self.FILE_TYPE_ERC20:
                erc20_files.append(file_path)
            else:
                raise ValueError(f'Unknown file type for Etherscan transformer: {file_type}')
            
        # Process withdrawal files (beacon-withdrawal)
        transactions = []
        for file_path in withdrawal_files:
            transactions.extend(self._transform_withdrawal_file(file_path))

        grouped_erc20 = self._group_erc20_transactions_by_hash(erc20_files)

        transactions.extend(self._join_transform_general_and_erc20_by_hash(general_files, grouped_erc20))

        transactions.sort(key=lambda x: datetime_parser(x['Datetime']))

        self.autofill_locale_fiat_and_fees(transactions)
        
        self.write_pycgt_csv(transactions)
        return transactions

