import csv
from datetime import datetime
from logger import logger
from shared_def import CRYPTOS, FIATS, FIELDS, LOCALE_FIAT
from .base_transformer import BaseTransformer
from market_data_provider import MarketDataProviderFactory
from transaction import float_parser

class BitstampTransformer(BaseTransformer):
    """Transformer for Bitstamp exchange logs"""

    def __init__(self, input_files, output_file):
        super().__init__(input_files, output_file)
        self.forex_provider = MarketDataProviderFactory.create_forex_provider()
        self.crypto_provider = MarketDataProviderFactory.create_crypto_provider()

    def transform(self):
        """Transform Bitstamp CSV format to pycgt format"""
        logger.info(f"Processing Bitstamp logs from {len(self.input_files)} file(s)")

        transactions = []

        for input_file in self.input_files:
            logger.info(f"Reading {input_file}")
            with open(input_file, 'r') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    pycgt_transaction = self._convert_bitstamp_row(row)
                    if pycgt_transaction:
                        transactions.append(pycgt_transaction)

        transactions.sort(key=lambda x: x['Datetime'])
        locale_fiat_upper = LOCALE_FIAT.upper()
        locale_fiat_lower = LOCALE_FIAT.lower()
        forexpair = f'{locale_fiat_lower}usd'
        dayrate = dict()

        if locale_fiat_lower != 'usd':
            # Get date range for forex query
            start_datetime = datetime.fromisoformat(transactions[0]['Datetime'])
            end_datetime = datetime.fromisoformat(transactions[-1]['Datetime'])
            dayrate = self.forex_provider.query(forexpair, start_datetime.date(), end_datetime.date())

            # Autofill locale fiat amounts from USD
            for tran in transactions:
                tran_datetime = datetime.fromisoformat(tran['Datetime'])
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
                        tran_datetime = datetime.fromisoformat(tran['Datetime'])
                        date_key = tran_datetime.date()

                        if crypto not in crypto_dates_need_query:
                            crypto_dates_need_query[crypto] = set()
                        crypto_dates_need_query[crypto].add(date_key)

        # Step 2: Query crypto/USD prices only for dates that need them
        crypto_usd_prices = {}
        for crypto, dates in crypto_dates_need_query.items():
            if dates:
                cryptousd_pair = f'{crypto}usd'
                min_date = min(dates)
                max_date = max(dates)
                logger.info(f"Querying {cryptousd_pair} prices for {len(dates)} dates ({min_date} to {max_date})")
                crypto_usd_prices[crypto] = self.crypto_provider.query(cryptousd_pair, min_date, max_date)

        # Step 3: Convert crypto fees to locale fiat (crypto_usd * usd_to_locale_fiat)
        for tran in transactions:
            tran_datetime = datetime.fromisoformat(tran['Datetime'])
            date_key = tran_datetime.date().isoformat()

            for crypto in CRYPTOS:
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
        self.write_pycgt_csv(transactions)
        return transactions

    def _convert_bitstamp_row(self, row):
        """
        Convert a single Bitstamp row to pycgt format

        Bitstamp format:
        ID, Account, Type, Subtype, Datetime, Amount, Amount currency,
        Value, Value currency, Rate, Rate currency, Fee, Fee currency, Order ID

        Args:
            row: Dictionary representing a Bitstamp CSV row

        Returns:
            Dictionary with pycgt field names, or None if row should be skipped
        """
        transaction_type = row['Type']
        subtype = row['Subtype']  # Buy/Sell for Market transactions

        # Initialize pycgt transaction with default empty values from FIELDS
        pycgt_row = {field: '' for field in FIELDS.keys()}

        # Set basic transaction info
        pycgt_row['Type'] = transaction_type
        pycgt_row['Exchange'] = 'Bitstamp'
        pycgt_row['Datetime'] = row['Datetime']
        pycgt_row['Comments'] = f"Order ID: {row['Order ID']}" if row['Order ID'] else ''

        rate = row['Rate']
        amount = row['Amount']
        amount_currency = row['Amount currency'].upper()
        value = row['Value']
        float_rate = float_parser(rate)
        float_amount = float_parser(amount)
        if float_rate > 0 and float_amount > 0:
            value = str(float_rate * float_amount)
        value_currency = row['Value currency'].upper()
        fee = row['Fee']
        fee_currency = row['Fee currency'].upper()

        # Handle Market Buy/Sell transactions
        if transaction_type == 'Market' and subtype in ['Buy', 'Sell']:
            pycgt_row['Operation'] = subtype.lower()

            # Create trading pair (e.g., BTCUSD, ETHUSD)
            if value_currency:
                pycgt_row['Pair'] = f"{amount_currency}{value_currency}".lower()

            # Set crypto amount
            if amount_currency.lower() in CRYPTOS:
                pycgt_row[amount_currency] = amount

            # Set fiat value
            if value_currency.lower() in FIATS:
                pycgt_row[value_currency] = value

            # Set exchange rate
            if rate and value_currency:
                rate_pair = f"{amount_currency}{value_currency}".upper()
                if rate_pair in pycgt_row:
                    pycgt_row[rate_pair] = rate

            # Set fee
            if fee and fee_currency:
                fee_field = f"Fee({fee_currency})"
                if fee_field in pycgt_row:
                    pycgt_row[fee_field] = fee

        # Handle Deposit transactions
        elif transaction_type == 'Deposit':
            pycgt_row['Operation'] = 'deposit'

            if amount_currency.lower() in CRYPTOS:
                pycgt_row[amount_currency] = amount
            elif amount_currency.lower() in FIATS:
                pycgt_row[amount_currency] = amount

            # Set fee
            if fee and fee_currency:
                fee_field = f"Fee({fee_currency})"
                if fee_field in pycgt_row:
                    pycgt_row[fee_field] = fee

        # Handle Withdrawal transactions
        elif transaction_type == 'Withdrawal':
            pycgt_row['Operation'] = 'withdrawal'

            if amount_currency.lower() in CRYPTOS:
                pycgt_row[amount_currency] = amount
            elif amount_currency.lower() in FIATS:
                pycgt_row[amount_currency] = amount

            # Set fee
            if fee and fee_currency:
                fee_field = f"Fee({fee_currency})"
                if fee_field in pycgt_row:
                    pycgt_row[fee_field] = fee

        else:
            logger.warning(f"Skipping unsupported transaction type: {transaction_type}/{subtype}")
            return None

        return pycgt_row

