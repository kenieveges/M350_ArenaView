import re
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
                 project_name: str, encoding="utf-8"):
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
        self.log_path = Path(log_path).absolute()
        self.save_root = Path(save_root).absolute()
        self.encoding = encoding
        self.camera = camera
        self.part_name = part_name
        self.capture_delay = capture_delay
        self.project_name = project_name
        self.layer_number = None
        self.last_position = None
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

    def _process_existing_log(self):
        try:
            with open(self.log_path, 'r', encoding=self.encoding) as f:
                for line in f:
                    self._process_line(line)
                self.last_position = f.tell()
            self.logger.debug("Processed %d bytes of log", self.last_position)
        except Exception as e:
            self.logger.exception("Log init read failed: %s", e)
            raise

    def check_for_updates(self):
        try:
            with open(self.log_path, 'r', encoding=self.encoding) as f:
                f.seek(self.last_position)
                for line in f:
                    self._process_line(line)
                self.last_position = f.tell()
        except Exception as e:
            self.logger.error("Log read update failed: %s", e)


    def _process_line(self, line: str):
        """Process a single log line for events."""
        try:
            if "Прожиг" in line:
                self.last_laser_line = line
                self._handle_event(line, kind="Прожиг")
            elif "Отсыпка" in line:
                self._handle_event(line, kind="Отсыпка")
        except Exception as e:
            self.logger.error("Error processing line '%s': %s", line.strip(), e)

    def _handle_event(self, line: str, kind: str):
        try:
            if kind == "Прожиг":
                match = re.search(r"\s(\d+)\s+Прожиг", line)
                if not match:
                    self.logger.warning("Could not extract layer number from Прожиг line: %s", line.strip())
                    return
                self.layer_number = int(match.group(1))
                self._capture_image(kind, self.layer_number)
            elif kind == "Отсыпка":
                if self.layer_number is None:
                    self.logger.warning("Skipping Отсыпка capture — no valid Прожиг seen yet.")
                    return
                self.logger.info("Waiting %.2f seconds before Отсыпка capture...", self.capture_delay)
                time.sleep(self.capture_delay)
                self._capture_image(kind, self.layer_number)
        except Exception as e:
            self.logger.error("Failed to handle %s event: %s", kind, e)


    def _capture_image(self, kind: str, layer: int):
        """Capture image with correct metadata."""
        folder = self.save_root / self.part_name / kind
        folder.mkdir(parents=True, exist_ok=True)

        self.logger.info("Capturing %s image for layer %d", kind, layer)
        if not self.camera.capture_image(str(folder), layer, self.project_name):
            self.logger.error("Capture failed for %s, layer %d", kind, layer)
