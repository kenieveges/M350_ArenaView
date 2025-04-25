import os
import sys
import time
import logging
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
                 save_root: str, part_name: str, capture_delay: float,
                 project_name: str):
        """
        Initialize log monitor.
        
        Args:
            log_path: Path to the log file to monitor
            camera: CameraController instance
            save_root: Root directory for saving images
            part_name: Name of the part being printed
            capture_delay: Delay between capture events in seconds
        """
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing log monitor for %s", log_path)
        
        self.log_path = log_path
        self.camera = camera
        self.save_root = save_root
        self.part_name = part_name
        self.capture_delay = capture_delay
        self.project_name = project_name
        self.last_layer = -1
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing log monitor for %s", log_path)

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
        try:
            if self.last_layer < 0:
                self.logger.warning("Powder event detected but no layer information available")
                return
                
            current_layer = self.last_layer + 1
            timestamp = datetime.now().strftime("%Y.%m.%d_%H:%M:%S_%f")
            
            self.logger.info("Powder event detected at %s for layer %s", timestamp, current_layer)
            
            # Capture powder deposition image
            powder_folder = os.path.join(self.save_root, self.part_name, "Отсыпка")
            self.camera.capture_image(powder_folder, current_layer, self.project_name)
            
            # Wait and capture start image
            self.logger.debug("Waiting %s seconds before next capture...", self.capture_delay)
            time.sleep(self.capture_delay)
            
            start_folder = os.path.join(self.save_root, self.part_name, "Старт")
            self.camera.capture_image(start_folder, current_layer, self.project_name)
            
        except Exception as e:
            self.logger.exception("Error handling powder event: %s", e)
            raise