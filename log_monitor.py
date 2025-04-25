import os
import sys
import time
from datetime import datetime
from typing import Optional, List
from camera_controller import CameraController
from arena_api import enums as arena_enums
from arena_api.enums import PixelFormat
from arena_api.__future__.save import Writer
from arena_api.system import system
from arena_api.buffer import BufferFactory

class LogMonitor:
    """Monitor SLM printer log files for specific events and trigger camera captures."""
    
    def __init__(self, log_path: str, camera: CameraController, 
                 save_root: str, part_name: str, capture_delay: float):
        """
        Initialize log monitor.
        
        Args:
            log_path: Path to the log file to monitor
            camera: CameraController instance
            save_root: Root directory for saving images
            part_name: Name of the part being printed
            capture_delay: Delay between capture events in seconds
        """
        self.log_path = log_path
        self.camera = camera
        self.save_root = save_root
        self.part_name = part_name
        self.capture_delay = capture_delay
        self.last_layer = -1

    def monitor(self):
        """Start monitoring the log file for events."""
        print(f"Starting log monitor for {self.log_path}")
        
        try:
            with open(self.log_path, 'r') as log_file:
                log_file.seek(0, 2)  # Seek to end of file
                
                while True:
                    line = log_file.readline()
                    if not line:
                        time.sleep(0.1)  # Small delay when no new lines
                        continue
                        
                    self._process_line(line)
        except FileNotFoundError:
            print(f"Log file not found: {self.log_path}")
        except Exception as e:
            print(f"Error monitoring log file: {e}")
        finally:
            self.camera.cleanup()

    def _process_line(self, line: str):
        """Process a single log line for events."""
        if "Прожиг" in line:
            self.last_layer = int(line.split(" ")[2])
            
        if 'Отсыпка' in line:
            self._handle_powder_event()

    def _handle_powder_event(self):
        """Handle powder deposition event by capturing images."""
        if self.last_layer < 0:
            print("Warning: Powder  detected but no layer information available")
            return
            
        current_layer = self.last_layer + 1
        timestamp = datetime.now().strftime("%Y.%m.%d_%H:%M:%S_%f")
        
        print(f"Powder event detected at {timestamp} for layer {current_layer}")
        
        # Capture powder deposition image
        powder_folder = os.path.join(self.save_root, self.part_name, "Отсыпка")
        self.camera.capture_image(powder_folder, current_layer)
        
        # Wait and capture start image
        print(f"Waiting {self.capture_delay} seconds before next capture...")
        time.sleep(self.capture_delay)
        
        start_folder = os.path.join(self.save_root, self.part_name, "Старт")
        self.camera.capture_image(start_folder, current_layer)


def main():
    # Configuration - could be moved to config file or command line args
    config = {
        'save_root': "D:\\Camera_reader\\Результаты",
        'part_name': "test",
        'log_path': r'C:\\M350\\LaserStudio\\x64\\Release\\Logs\\23.04.2025.log',
        'capture_delay': 11.25  # seconds
    }
    
    try:
        with CameraController() as camera:
            monitor = LogMonitor(
                log_path=config['log_path'],
                camera=camera,
                save_root=config['save_root'],
                part_name=config['part_name'],
                capture_delay=config['capture_delay']
            )
            monitor.monitor()
    except Exception as e:
        print(f"Fatal error: {e}")
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())