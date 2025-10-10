

import csv
from abc import ABC, abstractmethod
from shared_def import FIELDS
from logger import logger


class BaseTransformer(ABC):
    """Base class for exchange log transformers"""

    def __init__(self, input_files, output_file):
        """
        Initialize transformer

        Args:
            input_files: List of input CSV file paths
            output_file: Output CSV file path
        """
        self.input_files = input_files
        self.output_file = output_file

    @abstractmethod
    def transform(self):
        """
        Transform exchange logs to pycgt format

        This method should be implemented by each exchange-specific transformer.
        """
        pass

    def write_pycgt_csv(self, transactions):
        """
        Write transactions to pycgt-formatted CSV file

        Args:
            transactions: List of transaction dictionaries with pycgt field names
        """
        # Define pycgt CSV header
        fieldnames = FIELDS.keys()

        with open(self.output_file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            for transaction in transactions:
                writer.writerow(transaction)

        logger.info(f"Wrote {len(transactions)} transactions to {self.output_file}")
