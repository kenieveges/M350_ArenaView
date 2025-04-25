import logging
import logging.handlers
from pathlib import Path
import tomllib

def setup_logging(config_path: str = 'config.toml'):
    """Configure logging system from TOML config"""
    try:
        with open(config_path, 'rb') as f:
            config = tomllib.load(f).get('logging', {})
        
        logger = logging.getLogger()
        logger.setLevel(config.get('level', 'INFO'))

        # File handler with rotation
        log_file = config.get('file', 'app.log')
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=config.get('max_size', 1048576),
            backupCount=config.get('backup_count', 3)
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(levelname)s - %(message)s'
        ))

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
        
    except Exception as e:
        logging.basicConfig(level=logging.INFO)
        logging.error(f"Failed to configure logging: {e}")
        return logging.getLogger()