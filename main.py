from config_loader import load_config
from camera_controller import CameraController
from log_monitor import LogMonitor

def main():
    config = load_config()  # Load configuration
    
    with CameraController(
        retry_attempts=config['camera']['retry_attempts'],
        retry_delay=config['camera']['retry_delay']
    ) as camera:
        monitor = LogMonitor(
            log_path=config['log']['path'],
            camera=camera,
            save_root=config['save']['root'],
            part_name=config['save']['part_name'],
            capture_delay=config['capture']['delay']
        )
        monitor.monitor()