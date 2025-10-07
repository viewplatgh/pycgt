from config_loader import get_config

config = get_config()

FIATS = config['data']['fiats']
CRYPTOS = config['data']['cryptos']
OPERATIONS = config['data']['operations']
PARSE_DATETIME_FORMATS = config['data']['parse_datetime_formats']
FIELDS = config['data']['fields']
PAIR_SPLIT_MAP = config['data']['pair_split_map']

POSITION_ACCOUNTING = config['options']['position_accounting']
SORT_BY_DATETIME_ASC = config['options']['sort_by_datetime_asc']
PRECISION_THRESHOLD = config['options']['precision_threshold']
DEFAULT_FIAT = config['locale']['fiat']
FY_START_MONTH = config['locale']['fy_start_month']
