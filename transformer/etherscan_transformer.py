import csv
from datetime import datetime, timezone
from transformer.base_transformer import BaseTransformer
from shared_def import FIELDS
from logger import logger
from transaction import float_parser


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

    def transform(self):
        """
        Main transformation logic.

        Process files based on type:
        - withdrawal type: Transform directly (like Nexo interest)
        - Other types: Join by Transaction Hash, then transform
        """
        # Separate files by type
        withdrawal_files = []
        joinable_files = []

        for file_path in self.input_files:
            file_type = self._identify_file_type(file_path)
            logger.info(f'Identified {file_path} as type: {file_type}')

            if file_type == self.FILE_TYPE_WITHDRAWAL:
                withdrawal_files.append(file_path)
            else:
                joinable_files.append((file_path, file_type))

        # Process withdrawal files (beacon-withdrawal)
        transactions = []
        for file_path in withdrawal_files:
            transactions.extend(self._transform_withdrawal_file(file_path))

        # Process joinable files (general, erc-20)
        if joinable_files:
            joined_data = self._join_files_by_hash(joinable_files)
            # TODO: Transform joined data (to be discussed with user)
            logger.info(f'Joined {len(joined_data)} transactions from {len(joinable_files)} files')
            transactions.extend(self._transform_joined_data(joined_data))

        # Write output
        self.write_pycgt_csv(transactions)
        logger.info(f'Etherscan transformation complete: {len(transactions)} transactions written')

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

    def _join_files_by_hash(self, joinable_files):
        """
        Join general and erc-20 files by Transaction Hash.

        Args:
            joinable_files: List of (file_path, file_type) tuples

        Returns:
            Dict mapping Transaction Hash to joined data:
            {
                'tx_hash': {
                    'general': {...},
                    'erc-20': [...]  # Can be multiple token transfers
                }
            }
        """
        joined = {}

        for file_path, file_type in joinable_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    tx_hash = row.get('Transaction Hash', '').strip()

                    # Initialize dict for this transaction hash
                    if tx_hash not in joined:
                        joined[tx_hash] = {
                            'general': None,
                            'erc-20': []
                        }

                    # Store data by type
                    if file_type == self.FILE_TYPE_GENERAL:
                        joined[tx_hash]['general'] = row
                    elif file_type == self.FILE_TYPE_ERC20:
                        joined[tx_hash]['erc-20'].append(row)

        return joined

    def _transform_joined_data(self, joined_data):
        """
        Transform joined transaction data to pycgt format.

        TODO: Implement transformation logic based on discussion with user.

        Current placeholder logic:
        - If general data exists, use datetime from there
        - If erc-20 data exists, treat as token transfer

        Args:
            joined_data: Dict from _join_files_by_hash

        Returns:
            List of transaction dicts
        """
        transactions = []

        for tx_hash, data in joined_data.items():
            general = data.get('general')
            erc20_list = data.get('erc-20', [])

            # Get datetime from general
            datetime_str = None
            if general:
                datetime_str = general.get('DateTime (UTC)', '').strip()

            if not datetime_str:
                logger.warning(f'No datetime found for transaction hash: {tx_hash}')
                continue

            # TODO: This is placeholder logic - needs discussion
            # For now, just log what we found
            logger.info(f'Transaction {tx_hash}: general={general is not None}, erc20_count={len(erc20_list)}')

            # Placeholder: Create a basic transaction entry
            tran = self._create_base_transaction('Etherscan', datetime_str, 'deposit', {})
            transactions.append(tran)

        return transactions
