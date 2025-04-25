import tomllib
from pathlib import Path

def load_config(config_path: str = 'config.toml') -> dict:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    
    with open(path, 'rb') as f:
        return tomllib.load(f)