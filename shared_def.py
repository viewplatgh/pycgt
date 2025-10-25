from config_loader import get_config

config = get_config()

FIATS = config['data']['fiats']
CRYPTOS = config['data']['cryptos']
STABLECOINS = config['data']['stablecoins']
OPERATIONS = config['data']['operations']
PARSE_DATETIME_FORMATS = config['data']['parse_datetime_formats']
PAIR_SPLIT_MAP = config['data']['pair_split_map']

POSITION_ACCOUNTING = config['options']['position_accounting']
SORT_BY_DATETIME_ASC = config['options']['sort_by_datetime_asc']
PRECISION_THRESHOLD = config['options']['precision_threshold']
REQUESTS_TIMEOUT = config['options']['requests_timeout']
FOREX_QUERY_CHUNK_DAYS = config['options']['forex_query_chunk_days']

LOCALE_FIAT = config['locale']['fiat']
FY_START_MONTH = config['locale']['fy_start_month']


def _build_fields():
    """
    Build complete FIELDS dict by combining config fields with dynamically generated
    crypto/fiat fields based on CRYPTOS and FIATS lists.
    """
    # Start with fields from config (non-crypto/fiat fields)
    fields = dict(config['data']['fields'])

    for crypto in CRYPTOS:
        crypto_upper = crypto.upper()
        crypto_lower = crypto.lower()
        fields[crypto_upper] = crypto_lower
        fields[f'Fee({crypto_upper})'] = f'fee_{crypto_lower}'

    for fiat in FIATS:
        fiat_upper = fiat.upper()
        fiat_lower = fiat.lower()
        fields[fiat_upper] = fiat_lower
        fields[f'Fee({fiat_upper})'] = f'fee_{fiat_lower}'

    for pair_value in PAIR_SPLIT_MAP.values():
        pair_upper = ''.join([currency.upper() for currency in pair_value])
        pair_lower = ''.join([currency.lower() for currency in pair_value])
        fields[pair_upper] = pair_lower

    # Fiat-Fiat pairs (forex rates)
    for fiat in FIATS:
        fiat_upper = fiat.upper()
        fiat_lower = fiat.lower()
        for other_fiat in FIATS:
            if fiat != other_fiat:
                other_fiat_upper = other_fiat.upper()
                other_fiat_lower = other_fiat.lower()
                fields[f'{fiat_upper}{other_fiat_upper}'] = f'{fiat_lower}{other_fiat_lower}'

    return fields

FIELDS = _build_fields()
