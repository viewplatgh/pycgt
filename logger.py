import logging
from config_loader import get_config

config = get_config()

logging.basicConfig(
    level=config['logging'].get('level', logging.INFO),
    format=config['logging'].get('format', '%(asctime)s - %(levelname)s - %(message)s'),
    datefmt=config['logging'].get('datefmt', '%Y-%m-%d %H:%M:%S')
)

logger = logging.getLogger(__name__)