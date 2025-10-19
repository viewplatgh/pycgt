

import csv
from abc import ABC, abstractmethod
from shared_def import FIELDS, CRYPTOS, LOCALE_FIAT, STABLECOINS
from logger import logger
from market_data_provider import MarketDataProviderFactory
from transaction import float_parser, datetime_parser


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
        self.forex_provider = MarketDataProviderFactory.create_forex_provider()
        self.crypto_provider = MarketDataProviderFactory.create_crypto_provider()

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

    def autofill_locale_fiat_and_fees(self, transactions):
        """
        Auto-fill locale fiat amounts and fees from USD using forex and crypto market data.

        This method:
        1. Sorts transactions by datetime
        2. Queries forex rates for LOCALE_FIAT/USD conversion
        3. Auto-fills locale fiat amounts from USD values
        4. Auto-fills locale fiat fee amounts from USD fee values
        5. Auto-fills locale fiat fee amounts from crypto fee values using market prices

        Args:
            transactions: List of transaction dictionaries with pycgt field names

        Returns:
            The same transactions list (modified in-place) sorted by datetime
        """
        transactions.sort(key=lambda x: datetime_parser(x['Datetime']))
        locale_fiat_upper = LOCALE_FIAT.upper()
        locale_fiat_lower = LOCALE_FIAT.lower()
        forexpair = f'{locale_fiat_lower}usd'
        dayrate = dict()

        if locale_fiat_lower != 'usd':
            # Get date range for forex query
            start_datetime = datetime_parser(transactions[0]['Datetime'])
            end_datetime = datetime_parser(transactions[-1]['Datetime'])
            dayrate = self.forex_provider.query(forexpair, start_datetime.date(), end_datetime.date())

            # Autofill locale fiat amounts from USD
            for tran in transactions:
                tran_datetime = datetime_parser(tran['Datetime'])
                date_key = tran_datetime.date().isoformat()
                rate = dayrate.get(date_key, 0)
                if rate > 0:
                    tran[forexpair.upper()] = str(rate)
                    usd_value = float_parser(tran['USD'])
                    locale_fiat_value = float_parser(tran[locale_fiat_upper])
                    if usd_value > 0 and locale_fiat_value == 0:
                        tran[locale_fiat_upper] = str(usd_value / rate)

                    fee_usd_value = float_parser(tran['Fee(USD)'])
                    fee_locale_fiat_value = float_parser(tran[f'Fee({locale_fiat_upper})'])
                    if fee_usd_value > 0 and fee_locale_fiat_value == 0:
                        tran[f'Fee({locale_fiat_upper})'] = str(fee_usd_value / rate)

                    if 'usdt' in CRYPTOS:
                        # Autofill USDT amounts/fees if applicable
                        usdt_value = float_parser(tran['USDT'])
                        locale_fiat_value = float_parser(tran[locale_fiat_upper])
                        if usdt_value > 0 and locale_fiat_value == 0:
                            tran[locale_fiat_upper] = str(usdt_value / rate)

                        fee_usdt_value = float_parser(tran['Fee(USDT)'])
                        fee_locale_fiat_value = float_parser(tran[f'Fee({locale_fiat_upper})'])
                        if fee_usdt_value > 0 and fee_locale_fiat_value == 0:
                            tran[f'Fee({locale_fiat_upper})'] = str(fee_usdt_value / rate)
                else:
                    logger.warning(f"Missing {forexpair} rate for {date_key}, cannot convert USD to {locale_fiat_upper}")

        # Autofill crypto fee amounts to locale fiat
        # Step 1: Collect cryptos with fees and identify dates needing price queries
        # We only need to query prices for dates where the rate is NOT available in the transaction
        crypto_dates_need_query = {}  # {crypto: set of dates}

        for tran in transactions:
            for crypto in CRYPTOS:
                crypto_upper = crypto.upper()
                fee_field = f'Fee({crypto_upper})'
                fee_value = float_parser(tran.get(fee_field, ''))

                if fee_value > 0:
                    # Check if this transaction already has the crypto/USD rate
                    # Market Buy/Sell transactions have Rate field when Amount currency is the crypto
                    pair_field = f'{crypto_upper}USD'
                    has_rate = pair_field in tran and float_parser(tran.get(pair_field, '')) > 0

                    if not has_rate:
                        # Need to query price for this date
                        tran_datetime = datetime_parser(tran['Datetime'])
                        date_key = tran_datetime.date()

                        if crypto not in crypto_dates_need_query:
                            crypto_dates_need_query[crypto] = set()
                        crypto_dates_need_query[crypto].add(date_key)

        # Step 2: Query crypto/USD prices only for dates that need them
        crypto_usd_prices = {}
        for crypto, dates in crypto_dates_need_query.items():
            if crypto in STABLECOINS:
                continue
            if dates:
                cryptousd_pair = f'{crypto}usd'
                min_date = min(dates)
                max_date = max(dates)
                logger.info(f"Querying {cryptousd_pair} prices for {len(dates)} dates ({min_date} to {max_date})")
                crypto_usd_prices[crypto] = self.crypto_provider.query(cryptousd_pair, min_date, max_date)

        # Step 3: Convert crypto fees to locale fiat (crypto_usd * usd_to_locale_fiat)
        for tran in transactions:
            tran_datetime = datetime_parser(tran['Datetime'])
            date_key = tran_datetime.date().isoformat()

            for crypto in CRYPTOS:
                if crypto in STABLECOINS:
                    continue
                crypto_upper = crypto.upper()
                fee_crypto_field = f'Fee({crypto_upper})'
                fee_locale_fiat_field = f'Fee({locale_fiat_upper})'

                fee_crypto_value = float_parser(tran.get(fee_crypto_field, ''))
                if fee_crypto_value > 0:
                    # Try to get crypto/USD price from transaction first
                    pair_field = f'{crypto_upper}USD'
                    crypto_usd_price = float_parser(tran.get(pair_field, ''))

                    # If not in transaction, get from queried prices
                    if crypto_usd_price == 0 and crypto in crypto_usd_prices:
                        crypto_usd_price = crypto_usd_prices[crypto].get(date_key, 0)
                        # Store the queried price in the transaction for reference
                        if crypto_usd_price > 0:
                            tran[pair_field] = str(crypto_usd_price)

                    if crypto_usd_price > 0:
                        # Calculate fee in USD
                        fee_usd_value = fee_crypto_value * crypto_usd_price

                        # Convert USD to locale fiat
                        if locale_fiat_lower != 'usd':
                            locale_fiat_usd_rate = dayrate.get(date_key, 0)
                            if locale_fiat_usd_rate > 0:
                                fee_locale_fiat_value = fee_usd_value / locale_fiat_usd_rate
                                # Add to existing Fee(locale_fiat) if it exists
                                existing_fee = float_parser(tran.get(fee_locale_fiat_field, ''))
                                if existing_fee == 0:
                                    tran[fee_locale_fiat_field] = str(fee_locale_fiat_value)
                                else:
                                    logger.warning(f"Both {fee_locale_fiat_field} and {fee_crypto_field} having value in transaction on {date_key}, skiped auto-fill for it")
                            else:
                                logger.warning(f"Missing {forexpair} rate for {date_key}, cannot convert {crypto_upper} fee to {locale_fiat_upper}")
                        else:
                            # Locale fiat is USD, use USD value if applicable
                            existing_fee = float_parser(tran.get(fee_locale_fiat_field, ''))
                            if existing_fee == 0:
                                tran[fee_locale_fiat_field] = str(fee_usd_value)
                            else:
                                logger.warning(f"Both {fee_locale_fiat_field} and {fee_crypto_field} having value in transaction on {date_key}, skiped auto-fill for it")
                    else:
                        logger.warning(f"Missing {crypto}usd price for {date_key}, cannot convert {crypto_upper} fee to {locale_fiat_upper}")

        logger.info(f"Converted {len(transactions)} transactions")
        return transactions
