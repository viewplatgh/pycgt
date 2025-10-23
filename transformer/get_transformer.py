"""
Log transformation module for converting exchange-specific CSV formats to pycgt format.

This module provides transformers for different cryptocurrency exchanges.
Each transformer knows how to read the exchange's export format and convert it
to the standard pycgt CSV format.
"""
from .bitstamp_transformer import BitstampTransformer
from .independent_reserve_transformer import IndependentReserveTransformer
from .nexo_transformer import NexoTransformer

# Registry of available transformers
TRANSFORMERS = {
    'bitstamp': BitstampTransformer,
    'independentreserve': IndependentReserveTransformer,
    'nexo': NexoTransformer,
}

def get_transformer(exchange_type, input_files, output_file):
    """
    Get transformer instance for the specified exchange

    Args:
        exchange_type: Name of the exchange (e.g., 'bitstamp')
        input_files: List of input CSV file paths
        output_file: Output CSV file path

    Returns:
        Transformer instance

    Raises:
        ValueError: If exchange type is not supported
    """
    exchange_type = exchange_type.lower()

    if exchange_type not in TRANSFORMERS:
        supported = ', '.join(TRANSFORMERS.keys())
        raise ValueError(f"Unsupported exchange type: {exchange_type}. Supported: {supported}")

    transformer_class = TRANSFORMERS[exchange_type]
    return transformer_class(input_files, output_file)
