from config_loader import get_config

config = get_config()

CRYPTOS = config['data']['cryptos']
OPERATIONS = config['data']['operations']
FIELDS = config['data']['fields']
PAIR_SPLIT_MAP = config['data']['pair_split_map']

POSITION_ACCOUNTING = config['options']['position_accounting']
DEFAULT_FIAT = config['locale']['fiat']
FY_START_MONTH = config['locale']['fy_start_month']
