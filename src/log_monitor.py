import os
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from watchdog.observers import Observer
from file_monitor import LogFileHandler
from camera_controller import CameraController

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
            project_name: Project name for image file prefixes
        """
        self.logger = logging.getLogger(__name__)
        self.log_path = Path(log_path)
        self.camera = camera
        self.save_root = save_root
        self.part_name = part_name
        self.capture_delay = capture_delay
        self.project_name = project_name
        self.last_position = 0
        self.last_layer = -1
        self.observer = None
        self.logger.info("Initialized log monitor for %s", log_path)

    def monitor(self):
        """Start monitoring the log file using watchdog.
        
        Initializes file monitoring by:
        1. Processing all existing log content
        2. Setting up filesystem watcher for new changes
        3. Ensuring proper cleanup on exit
        """
        self.logger.info("Starting watchdog monitoring for %s", self.log_path)
        
        try:
            self._process_existing_log()
            self._start_watchdog()
            self._keep_alive()
        except Exception as e:
            self.logger.exception("Critical monitoring error occurred: %s", e)
        finally:
            self._shutdown()

    def _process_existing_log(self):
        """Process all existing content in the log file."""
        try:
            with open(self.log_path, 'r', encoding='cp1252') as f:
                for line in f:
                    self._process_line(line)
                self.last_position = f.tell()
                self.logger.debug("Processed %d bytes of existing log", self.last_position)
        except FileNotFoundError:
            self.logger.error("Log file not found: %s", self.log_path)
            raise
        except Exception as e:
            self.logger.exception("Failed to process existing log content: %s", e)
            raise

    def _start_watchdog(self):
        """Initialize and start the watchdog observer."""
        event_handler = LogFileHandler(self.check_for_updates)
        self.observer = Observer()
        self.observer.schedule(event_handler, path=str(self.log_path.parent), recursive=False)
        self.observer.start()
        self.logger.info("Watchdog started successfully")

    def _keep_alive(self):
        """Keep the monitoring thread alive."""
        while True:
            time.sleep(1)

    def _shutdown(self):
        """Clean up resources."""
        self.logger.info("Shutting down monitor")
        if self.observer:
            self.observer.stop()
            self.observer.join()
        self.camera.cleanup()

    def check_for_updates(self):
        """Handle file change events detected by watchdog."""
        try:
            with open(self.log_path, 'r', encoding='cp1252') as f:
                f.seek(self.last_position)
                for line in f:
                    self._process_line(line)
                self.last_position = f.tell()
        except Exception as e:
            self.logger.error("Error reading log updates: %s", e)

    def _process_line(self, line: str):
        """Process a single log line for events."""
        try:
            if "Прожиг" in line:
                self._handle_layer_change(line)
            elif 'Отсыпка' in line:
                self._handle_powder_event()
        except Exception as e:
            self.logger.error("Error processing log line '%s': %s", line.strip(), e)

    def _handle_layer_change(self, line: str):
        """Update current layer number from log event."""
        try:
            self.last_layer = int(line.split(" ")[2])
            self.logger.debug("Layer changed to %d", self.last_layer)
        except (IndexError, ValueError):
            self.logger.error("Failed to parse layer number from line: %s", line.strip())
            raise

    def _handle_powder_event(self):
        """Handle powder deposition event by capturing images."""
        if self.last_layer < 0:
            self.logger.warning("Powder event detected with invalid layer number")
            return

        current_layer = self.last_layer + 1
        timestamp = datetime.now().strftime("%Y.%m.%d_%H:%M:%S_%f")
        self.logger.info("Powder event detected at %s for layer %d", timestamp, current_layer)
        
        try:
            # First capture: powder deposition
            powder_folder = os.path.join(self.save_root, self.part_name, "Отсыпка")
            self._capture_image(powder_folder, current_layer)
            
            # Second capture: after delay
            self.logger.debug("Waiting %.2f seconds before next capture", self.capture_delay)
            time.sleep(self.capture_delay)
            
            start_folder = os.path.join(self.save_root, self.part_name, "Старт")
            self._capture_image(start_folder, current_layer)
        except Exception:
            self.logger.exception("Failed to complete powder event capture")
            raise

    def _capture_image(self, folder: str, layer: int):
        """Wrapper for camera capture with logging."""
        self.logger.debug("Capturing image to %s for layer %d", folder, layer)
        try:
            self.camera.capture_image(folder, layer, self.project_name)
        except Exception as e:
            self.logger.error("Image capture failed for %s: %s", folder, e)
            raise