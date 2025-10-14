from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import Dict, Optional
from logger import logger


class MarketDataProvider(ABC):
    """
    Base class for market data providers.
    Provides a unified interface for querying forex and crypto exchange rates.
    """

    @abstractmethod
    def query(self, pair: str, start_date: date, end_date: Optional[date] = None) -> Dict[str, float]:
        """
        Query market data for a given pair and date/date range.

        Args:
            pair: Trading pair (e.g., 'btcusd', 'audusd')
            start_date: Start date for query
            end_date: End date for query (optional). If None, queries single date.

        Returns:
            Dictionary with date strings as keys and rates as values:
            {
                '2024-03-14': 65432.10,
                '2024-03-15': 65890.50,
                ...
            }
            Returns one entry per day in the date range.
        """
        pass
