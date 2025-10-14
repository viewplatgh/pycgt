from .forex_data_provider import ForexDataProvider
from .crypto_data_provider import CryptoDataProvider


class MarketDataProviderFactory:
    """
    Factory class for creating market data provider instances.
    Implements singleton pattern for providers.
    """

    _forex_instance = None
    _crypto_instance = None

    @staticmethod
    def create_forex_provider() -> ForexDataProvider:
        """
        Create or return the singleton forex data provider instance.

        Returns:
            ForexDataProvider singleton instance
        """
        if MarketDataProviderFactory._forex_instance is None:
            MarketDataProviderFactory._forex_instance = ForexDataProvider()
        return MarketDataProviderFactory._forex_instance

    @staticmethod
    def create_crypto_provider() -> CryptoDataProvider:
        """
        Create or return the singleton crypto data provider instance.

        Returns:
            CryptoDataProvider singleton instance
        """
        if MarketDataProviderFactory._crypto_instance is None:
            MarketDataProviderFactory._crypto_instance = CryptoDataProvider()
        return MarketDataProviderFactory._crypto_instance
