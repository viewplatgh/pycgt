import csv
from transformer.base_transformer import BaseTransformer
from shared_def import LOCALE_FIAT
from logger import logger
from transaction import float_parser, datetime_parser

SATOSHIS_PER_BTC = 100000000
MILLISATOSHIS_PER_BTC = 100000000000


class PhoenixTransformer(BaseTransformer):
    """
    Transforms Phoenix wallet payment-history exports to pycgt format.

    Phoenix rows move BTC between wallets the taxpayer controls, so no
    acquisition or disposal is recorded for the BTC itself. Phoenix charges two
    fees, both paid in BTC and both disposals:
      - mining_fee_sat: on-chain fee for swaps/channel management
      - service_fee_msat: Phoenix's own liquidity/service fee
    They are summed into Fee(BTC).

    The export already carries locale-fiat amounts (e.g. "109.0987 AUD"), so
    Fee(<fiat>) and the BTC/<fiat> rate are taken straight from the export
    rather than re-derived from market data.
    """

    EXCHANGE = 'Phoenix'

    # Phoenix payment types, mapped to the direction BTC moved
    INCOMING_TYPES = {'swap_in', 'lightning_received', 'channel_open', 'legacy_pay_to_open'}
    OUTGOING_TYPES = {'swap_out', 'lightning_sent', 'channel_close'}

    def _parse_fiat(self, value):
        """
        Parse a Phoenix fiat cell such as "109.0987 AUD".

        Returns 0 when the cell is empty or denominated in some other currency,
        so a mismatched export falls back to market-data autofill rather than
        silently booking foreign-currency numbers as locale fiat.
        """
        value = (value or '').strip()
        if not value:
            return 0

        parts = value.split()
        amount = float_parser(parts[0])
        currency = parts[1].upper() if len(parts) > 1 else ''

        if currency and currency != LOCALE_FIAT.upper():
            logger.warning(
                f"Phoenix export reports fiat in {currency}, not {LOCALE_FIAT.upper()}; "
                f"ignoring '{value}' and falling back to market data")
            return 0
        return amount

    def transform(self):
        """Transform Phoenix wallet CSV format to pycgt format"""
        logger.info(f"Processing Phoenix logs from {len(self.input_files)} file(s)")

        transactions = []
        skipped = 0

        for input_file in self.input_files:
            logger.info(f"Reading {input_file}")
            with open(input_file, 'r', newline='') as csvfile:
                for row in csv.DictReader(csvfile):
                    tran_datetime = datetime_parser(row['date'])
                    if not self.in_timeframe(tran_datetime):
                        skipped += 1
                        continue
                    transactions.append(self._convert_row(row))

        if skipped:
            logger.info(f"Skipped {skipped} row(s) outside the requested timeframe")

        if not transactions:
            raise ValueError('No Phoenix rows to transform')

        transactions.sort(key=lambda x: datetime_parser(x['Datetime']))

        self.autofill_locale_fiat_and_fees(transactions)

        self.write_pycgt_csv(transactions)
        return transactions

    def _convert_row(self, row):
        """Convert a single Phoenix payment row to a pycgt transaction"""
        payment_type = (row.get('type') or '').strip().lower()

        if payment_type in self.INCOMING_TYPES:
            operation = 'deposit'
        elif payment_type in self.OUTGOING_TYPES:
            operation = 'withdrawal'
        else:
            raise ValueError(
                f"Unsupported Phoenix payment type: '{payment_type}'. Add it to "
                f"INCOMING_TYPES or OUTGOING_TYPES once its direction is confirmed.")

        locale_fiat_upper = LOCALE_FIAT.upper()

        amount_btc = float_parser(row.get('amount_msat', '')) / MILLISATOSHIS_PER_BTC
        mining_fee_btc = float_parser(row.get('mining_fee_sat', '')) / SATOSHIS_PER_BTC
        service_fee_btc = float_parser(row.get('service_fee_msat', '')) / MILLISATOSHIS_PER_BTC
        fee_btc = mining_fee_btc + service_fee_btc

        amount_fiat = self._parse_fiat(row.get('amount_fiat'))
        fee_fiat = self._parse_fiat(row.get('mining_fee_fiat')) + self._parse_fiat(row.get('service_fee_fiat'))

        tran = self._create_base_transaction(self.EXCHANGE, row['date'], operation)
        tran['Type'] = payment_type

        if amount_btc > 0:
            tran['BTC'] = str(amount_btc)
        if amount_fiat > 0:
            tran[locale_fiat_upper] = str(amount_fiat)
        if fee_btc > 0:
            tran[f'Fee(BTC)'] = str(fee_btc)
        if fee_fiat > 0:
            tran[f'Fee({locale_fiat_upper})'] = str(fee_fiat)

        # Phoenix prices every row itself; publishing the implied BTC/<fiat> rate
        # lets the fee disposal be valued from the export rather than market data.
        if amount_btc > 0 and amount_fiat > 0:
            rate_field = f'BTC{locale_fiat_upper}'
            tran[rate_field] = str(amount_fiat / amount_btc)

        description = (row.get('description') or '').strip()
        reference = (row.get('tx_id') or row.get('payment_hash') or '').strip()
        tran['Comments'] = (
            f'Phoenix {payment_type}: {amount_btc} BTC; '
            f'Mining fee: {mining_fee_btc} BTC; Service fee: {service_fee_btc} BTC; '
            f'{description}; Ref: {reference}')

        return tran
