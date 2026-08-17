"""
Log transformation module for converting exchange-specific CSV formats to pycgt format.

This module provides transformers for different cryptocurrency exchanges.
Each transformer knows how to read the exchange's export format and convert it
to the standard pycgt CSV format.
"""
from .bitstamp_transformer import BitstampTransformer
from .independent_reserve_transformer import IndependentReserveTransformer
from .nexo_transformer import NexoTransformer
from .exodus_transformer import ExodusTransformer
from .etherscan_transformer import EtherscanTransformer
from .electrum_transformer import ElectrumTransformer
from .kraken_transformer import KrakenTransformer
from .phoenix_transformer import PhoenixTransformer
from .umbrel_transformer import UmbrelTransformer

# Registry of available transformers
TRANSFORMERS = {
    'bitstamp': BitstampTransformer,
    'independentreserve': IndependentReserveTransformer,
    'nexo': NexoTransformer,
    'exodus': ExodusTransformer,
    'etherscan': EtherscanTransformer,
    'electrum': ElectrumTransformer,
    'kraken': KrakenTransformer,
    'phoenix': PhoenixTransformer,
    'umbrel': UmbrelTransformer,
}

def get_transformer(exchange_type, input_files, output_file, start_date=None, end_date=None):
    """
    Get transformer instance for the specified exchange

    Args:
        exchange_type: Name of the exchange (e.g., 'bitstamp')
        input_files: List of input CSV file paths
        output_file: Output CSV file path
        start_date: Optional inclusive date lower bound for rows to keep
        end_date: Optional inclusive date upper bound for rows to keep

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
    return transformer_class(input_files, output_file, start_date=start_date, end_date=end_date)
