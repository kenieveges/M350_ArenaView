import sys
from pathlib import Path
from config_loader import load_config
from camera_controller import CameraController
from log_monitor import LogMonitor
from logger import setup_logging

PROJECT_ROOT = Path(__file__).parent.parent

def get_config_path():
    """Resolve config file path relative to project root"""
    return PROJECT_ROOT / "config" / "config.toml"

def main():
    """
    Main entry point for the SLM printer monitoring application.
    
    Initializes the system, monitors the printer log for powder deposition events,
    and captures images using a connected camera when events occur.

    Workflow:
        1. Loads configuration from TOML file
        2. Validates required configuration parameters
        3. Initializes camera with specified retry behavior
        4. Starts monitoring the printer log file
        5. Captures images on powder deposition events

    Returns:
        int: Return code indicating success or failure:
            - 0: Successful execution
            - 1: Error occurred (configuration, camera, or monitoring failure)

    Raises:
        FileNotFoundError: If configuration file is missing
        KeyError: If required configuration keys are missing
        ValueError: If configuration values are invalid
        RuntimeError: If camera initialization fails
        Exception: For unexpected errors during monitoring

    Example:
        To run from command line:
        >>> python main.py
        or with custom config:
        >>> python main.py --config alternative_config.toml

    Notes:
        - Requires properly formatted config.toml in working directory
        - Camera must be connected before startup
        - Log file must be accessible
    """
    try:
        config_path = get_config_path()
        logger = setup_logging(config_path)
        # Load configuration first as it might fail
        config = load_config(config_path)
        logger.info("Application starting with config:\n%s", config)
        
        # Validate essential configuration
        if not all(key in config['save'] for key in ['root', 'part_name', 'project_name']):
            raise ValueError("Missing required save configuration")
        # Resolve all paths relative to project root
        log_path = PROJECT_ROOT / config['log']['path']
        save_root = PROJECT_ROOT / config['save']['root']
        with CameraController(
            retry_attempts=config['camera']['retry_attempts'],
            retry_delay=config['camera']['retry_delay'],
        ) as camera:
            encoding = config['log'].get('encoding', 'utf-8')
            monitor = LogMonitor(
                log_path=str(log_path),
                camera=camera,
                save_root=str(save_root),
                part_name=config['save']['part_name'],
                capture_delay=config['capture']['delay'],
                project_name=config['save']['project_name'],
                encoding=encoding
            )
            monitor.monitor()
    except FileNotFoundError as e:
        logger.exception("Configuration file not found at specified path: %s", str(e))
        return 1
    except KeyError as e:
        logger.error("Missing required configuration key: %s", str(e))
        logger.debug("Full configuration dump: %s", config)
        return 1
    except ValueError as e:
        logger.error("Invalid configuration value: %s", str(e))
        return 1
    except Exception as e:
        logger.exception("Unexpected error occurred during execution: %s", str(e))
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
