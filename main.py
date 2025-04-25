from config_loader import load_config
from camera_controller import CameraController
from log_monitor import LogMonitor

def main():
    try:
        # Load configuration first as it might fail
        config = load_config()
        
        # Validate essential configuration
        if not all(key in config['save'] for key in ['root', 'part_name', 'project_name']):
            raise ValueError("Missing required save configuration")
        
        with CameraController(
            retry_attempts=config['camera']['retry_attempts'],
            retry_delay=config['camera']['retry_delay']
        ) as camera:
            monitor = LogMonitor(
                log_path=config['log']['path'],
                camera=camera,
                save_root=config['save']['root'],
                part_name=config['save']['part_name'],
                capture_delay=config['capture']['delay'],
                project_name=config['save']['project_name']
            )
            monitor.monitor()
            
    except FileNotFoundError as e:
        print(f"Configuration error: {e}")
        return 1
    except KeyError as e:
        print(f"Missing required configuration key: {e}")
        return 1
    except ValueError as e:
        print(f"Configuration error: {e}")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1
    return 0