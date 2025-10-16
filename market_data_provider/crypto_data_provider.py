from datetime import date, timedelta, datetime
from typing import Dict, Optional
import requests
from logger import logger
from .market_data_provider import MarketDataProvider
from transaction import float_parser


class CryptoDataProvider(MarketDataProvider):
    """
    Cryptocurrency market data provider using Bitstamp API.
    Queries crypto exchange rates (e.g., BTCUSD, ETHUSD).

    API: https://www.bitstamp.net/api/
    Note: Bitstamp only provides USD pairs, not AUD.
    Caller should convert USD to AUD using forex rates.
    """

    BASE_URL = "https://www.bitstamp.net/api/v2"
    MAX_LIMIT = 1000  # Bitstamp allows up to 1000 candles per request

    def __init__(self):
        """Initialize crypto data provider."""
        logger.info("Initialized CryptoDataProvider (Bitstamp API)")

    def _query_chunked(self, pair: str, start_date: date, end_date: date) -> Dict[str, float]:
        """
        Query crypto prices in chunks to handle date ranges > 1000 days.

        Args:
            pair: Crypto pair (lowercase, e.g., 'btcusd')
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary with date strings as keys and rates as values
        """
        all_results = {}
        current_start = start_date
        chunk_count = 0

        while current_start <= end_date:
            # Calculate chunk end (999 days from start, or end_date if sooner)
            chunk_end = current_start + timedelta(days=999)
            if chunk_end > end_date:
                chunk_end = end_date

            chunk_count += 1
            logger.info(f"Querying chunk {chunk_count}: {current_start} to {chunk_end}")

            # Query this chunk
            chunk_results = self._query_single_range(pair, current_start, chunk_end)
            all_results.update(chunk_results)

            # Move to next chunk
            current_start = chunk_end + timedelta(days=1)

        logger.info(f"Retrieved {len(all_results)} total prices from {chunk_count} chunk(s) for {pair}")
        return all_results

    def _query_single_range(self, pair: str, start_date: date, end_date: date) -> Dict[str, float]:
        """
        Query a single date range from Bitstamp API.

        Args:
            pair: Crypto pair (lowercase, e.g., 'btcusd')
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary with date strings as keys and rates as values
        """
        try:
            # Convert dates to Unix timestamps
            start_timestamp = int(datetime.combine(start_date, datetime.min.time()).timestamp())
            end_timestamp = int(datetime.combine(end_date, datetime.max.time()).timestamp())

            # Build URL - Bitstamp uses format like "btcusd" (no separator)
            url = f"{self.BASE_URL}/ohlc/{pair}/"
            params = {
                'step': 86400,  # Daily candles (24h in seconds)
                'limit': self.MAX_LIMIT,
                'start': start_timestamp,
                'end': end_timestamp
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Extract OHLC data
            if 'data' not in data or 'ohlc' not in data['data']:
                raise ValueError(f"Unexpected response format from Bitstamp API: {data}")

            ohlc_data = data['data']['ohlc']
            if not ohlc_data:
                raise ValueError(f"No price data found for {pair} from {start_date} to {end_date}")

            # Convert to date-keyed dictionary using close prices
            results = {}
            for candle in ohlc_data:
                candle_date = datetime.fromtimestamp(int(candle['timestamp'])).date()
                date_str = candle_date.isoformat()
                # Use close price for the day
                results[date_str] = float_parser(candle['close'])

            # Fill in any missing dates with last known price
            last_price = None
            current_date = start_date
            last_price_reusing_count = 0
            filled_results = {}

            while current_date <= end_date:
                date_str = current_date.isoformat()
                if date_str in results:
                    filled_results[date_str] = results[date_str]
                    last_price = results[date_str]
                    last_price_reusing_count = 0
                elif last_price is not None:
                    filled_results[date_str] = last_price
                    last_price_reusing_count += 1

                    if last_price_reusing_count > 4:
                        raise ValueError(f"{last_price_reusing_count} consecutive days without {pair} price data (up to {date_str}). Check data source.")
                    if last_price_reusing_count > 3:
                        logger.warning(f"Reusing last known {pair} price for {last_price_reusing_count} consecutive days up to {date_str}.")

                current_date += timedelta(days=1)

            return filled_results

        except requests.RequestException as e:
            logger.error(f"Failed to fetch crypto data from Bitstamp API: {e}")
            raise
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse crypto data response: {e}")
            raise

    def query(self, pair: str, start_date: date, end_date: Optional[date] = None) -> Dict[str, float]:
        """
        Query crypto exchange rates for a given pair and date/date range.

        Note: Only USD pairs are supported (e.g., 'btcusd', 'ethusd').
        For AUD values, convert using forex rates separately.

        Args:
            pair: Crypto pair (e.g., 'btcusd', 'ethusd', 'linkusd')
            start_date: Start date for query
            end_date: End date for query (optional). If None, queries single date.

        Returns:
            Dictionary with date strings as keys and rates as values

        Raises:
            ValueError: If pair format is invalid
            requests.RequestException: If API request fails
        """
        if end_date is None:
            end_date = start_date

        pair = pair.lower()

        # Validate pair ends with 'usd'
        if not pair.endswith('usd'):
            raise ValueError(f"Bitstamp CryptoDataProvider only supports USD pairs. Got: {pair}")

        crypto_symbol = pair[:-3]

        logger.info(f"Querying crypto data for {pair} ({crypto_symbol.upper()}/USD) from {start_date} to {end_date}")

        results = self._query_chunked(pair, start_date, end_date)
        return results
