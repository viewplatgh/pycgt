from datetime import date, timedelta
from typing import Dict, Optional
import requests
from logger import logger
from .market_data_provider import MarketDataProvider

class ForexDataProvider(MarketDataProvider):
    """
    Forex market data provider using Frankfurter API.
    Queries foreign exchange rates (e.g., AUDUSD, EURUSD).

    API: https://www.frankfurter.app/
    Data source: European Central Bank
    """

    BASE_URL = "https://api.frankfurter.app"

    def __init__(self):
        """Initialize forex data provider."""
        logger.info("Initialized ForexDataProvider (Frankfurter API)")

    def _query_single_range(self, pair: str, base_currency: str, target_currency: str, start_date: date, end_date: date) -> Dict[str, float]:
        """
        Query a single date range from Frankfurter API.

        Args:
            pair: Forex pair (lowercase)
            base_currency: Base currency (uppercase)
            target_currency: Target currency (uppercase)
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary with date strings as keys and rates as values
        """
        try:
            if start_date == end_date:
                url = f"{self.BASE_URL}/{start_date.isoformat()}"
            else:
                url = f"{self.BASE_URL}/{start_date.isoformat()}..{end_date.isoformat()}"

            params = {
                'from': base_currency,
                'to': target_currency
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            results = {}

            if start_date == end_date:
                rate = data.get('rates', {}).get(target_currency)
                if rate:
                    results[start_date.isoformat()] = float(rate)
                else:
                    raise ValueError(f"No rate found for {pair} on {start_date}")
            else:
                res_start_date = date.fromisoformat(data.get('start_date', start_date.isoformat()))
                rates_by_date = data.get('rates', {})

                last_rate = rates_by_date.get(res_start_date.isoformat(), {}).get(target_currency, 0)
                if last_rate == 0:
                    raise ValueError(f"No rate found for {pair} on the start date: {res_start_date}")
                current_date = res_start_date
                last_rate_reusing_count = 0
                while current_date <= end_date:
                    date_str = current_date.isoformat()
                    if date_str in rates_by_date:
                        last_rate = rates_by_date[date_str].get(target_currency, last_rate)
                        results[date_str] = float(last_rate)
                        last_rate_reusing_count = 0
                    else:
                        results[date_str] = float(last_rate)
                        last_rate_reusing_count += 1
                    if last_rate_reusing_count > 4:
                        raise ValueError(f"{last_rate_reusing_count} consecutive days without {pair} rate data (up to {date_str}). Check date source.")
                    if last_rate_reusing_count > 3:
                        logger.warning(f"Reusing last known {pair} rate for {last_rate_reusing_count} consecutive days up to {date_str}.")
                    current_date += timedelta(days=1)

            return results

        except requests.RequestException as e:
            logger.error(f"Failed to fetch forex data from Frankfurter API: {e}")
            raise
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse forex data response: {e}")
            raise

    def _query_chunked(self, pair: str, base_currency: str, target_currency: str, start_date: date, end_date: date) -> Dict[str, float]:
        """
        Query forex rates in yearly chunks to avoid Frankfurter API weekly sampling.

        Args:
            pair: Forex pair (lowercase)
            base_currency: Base currency (uppercase)
            target_currency: Target currency (uppercase)
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary with all dates' rates combined from chunks
        """
        all_results = {}
        current_start = start_date
        chunk_count = 0

        while current_start <= end_date:
            # Calculate chunk end date (1 year from current_start, or end_date if sooner)
            chunk_end = date(current_start.year + 1, current_start.month, current_start.day) - timedelta(days=1)
            if chunk_end > end_date:
                chunk_end = end_date

            chunk_count += 1
            logger.info(f"Querying chunk {chunk_count}: {current_start} to {chunk_end}")

            # Query this chunk
            chunk_results = self._query_single_range(pair, base_currency, target_currency, current_start, chunk_end)
            all_results.update(chunk_results)

            # Move to next chunk
            current_start = chunk_end + timedelta(days=1)

        logger.info(f"Retrieved {len(all_results)} total rates from {chunk_count} chunk(s) for {pair}")
        return all_results

    def query(self, pair: str, start_date: date, end_date: Optional[date] = None) -> Dict[str, float]:
        """
        Query forex rates for a given pair and date/date range.

        Args:
            pair: Forex pair (e.g., 'audusd', 'eurusd')
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
        if len(pair) != 6:
            raise ValueError(f"Invalid forex pair format: {pair}. Expected 6 characters (e.g., 'audusd')")

        base_currency = pair[:3].upper()
        target_currency = pair[3:6].upper()

        logger.info(f"Querying forex data for {pair} ({base_currency} -> {target_currency}) from {start_date} to {end_date}")

        results = self._query_chunked(pair, base_currency, target_currency, start_date, end_date)
        return results
