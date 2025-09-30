import os
import sys

try:
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import toml as tomllib
        tomllib.loads = tomllib.loads if hasattr(tomllib, 'loads') else tomllib.load
except ImportError:
    import toml as tomllib


def load_config(config_path='config.toml'):
    """Load configuration from TOML file"""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    try:
        if sys.version_info >= (3, 11):
            with open(config_path, 'rb') as f:
                return tomllib.load(f)
        else:
            with open(config_path, 'r') as f:
                return tomllib.load(f)
    except Exception as e:
        raise Exception(f"Failed to parse config file {config_path}: {e}")


# Global config instance
_config = None

def get_config():
    """Get the loaded configuration"""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config(config_path='config.toml'):
    """Reload configuration from file"""
    global _config
    _config = load_config(config_path)
    return _config