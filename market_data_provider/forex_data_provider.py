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

        # Parse pair into base and target currencies
        pair = pair.lower()
        if len(pair) != 6:
            raise ValueError(f"Invalid forex pair format: {pair}. Expected 6 characters (e.g., 'audusd')")

        base_currency = pair[:3].upper()
        target_currency = pair[3:6].upper()

        logger.info(f"Querying forex data for {pair} ({base_currency} -> {target_currency}) from {start_date} to {end_date}")

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
                res_end_date = date.fromisoformat(data.get('end_date', end_date.isoformat()))
                rates_by_date = data.get('rates', {})

                last_rate = rates_by_date.get(res_start_date.isoformat(), {}).get(target_currency, 0)
                if last_rate == 0:
                    raise ValueError(f"No rate found for {pair} on the start date: {res_start_date}")
                current_date = res_start_date
                while current_date <= res_end_date:
                    date_str = current_date.isoformat()
                    if date_str in rates_by_date:
                        last_rate = rates_by_date[date_str].get(target_currency, last_rate)
                        results[date_str] = float(last_rate)
                    else:
                        results[date_str] = float(last_rate)

                    current_date += timedelta(days=1) 

            logger.info(f"Retrieved {len(results)} forex rates for {pair} (including filled weekend/holiday dates)")
            return results

        except requests.RequestException as e:
            logger.error(f"Failed to fetch forex data from Frankfurter API: {e}")
            raise
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse forex data response: {e}")
            raise
