import logging
import time
import os
from datetime import datetime
import cv2
from mv_sdk.MVCamera import Camera


class CameraController:
    """
    Camera controller using MVCamera wrapper with retry logic, transport-layer configuration,
    and image capture functionality.
    """
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def __init__(self, retry_attempts: int = 3, retry_delay: int = 1):
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.log = logging.getLogger(__name__)
        self.camera = Camera()
        self.initialized = False
        self.log.info("Initializing camera controller")
        self._initialize_camera()

    def _initialize_camera(self):
        """Discover, connect, and configure the camera with retries."""
        self.log.info("Starting camera initialization (retries: %s, delay: %ss)", 
                        self.retry_attempts, self.retry_delay)
        for attempt in range(1, self.retry_attempts + 1):
            try:
                self.log.info("Discovering camera (Attempt %d/%d)", attempt, self.retry_attempts)
                self.camera.enumerate()

                self.log.info("Connecting to camera")
                self.camera.open()

                self._configure_transport_layer()

                self.initialized = True
                self.log.info("Camera initialized successfully")
                return

            except Exception as e:
                self.log.warning("Initialization attempt %d failed: %s", attempt, e)
                try:
                    self.camera.close()
                except Exception:
                    self.log.debug("Error closing camera after failed init")

                if attempt < self.retry_attempts:
                    self._countdown(self.retry_delay)
                else:
                    self.log.error("Could not initialize camera after %d attempts", self.retry_attempts)
                    raise RuntimeError("Camera initialization failed") from e

    def _countdown(self, seconds: int):
        """Simple per-second countdown for retry backoff."""
        for remaining in range(seconds, 0, -1):
            self.log.debug("Retrying in %d seconds...", remaining)
            time.sleep(1)

    def _configure_transport_layer(self):
        """Configure packet size and inter-packet delay for reliable streaming."""
        try:
            tlc = self.camera.get_transport_layer_control()
            max_size = tlc.get_max_packet_size()
            tlc.set_packet_size(max_size)
            tlc.set_inter_packet_delay(2000)
            tlc.release()
            self.log.debug("Transport layer configured: packet_size=%d, delay=2000", max_size)
        except Exception as e:
            self.log.warning("Transport layer configuration failed: %s", e)

    def capture_image(self, save_folder: str, layer: int, project_name: str) -> str:
        """
        Capture a single frame, save it as a TIFF with timestamp and return the file path.
        """
        if not self.initialized:
            raise RuntimeError("Camera not initialized")

        try:
            self.log.info("Starting frame capture")
            self.camera.start_grabbing()
            frame = self.camera.get_frame()

            # Build timestamped filename
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
            filename = f"{project_name}_{layer}_{ts}.tiff"
            os.makedirs(save_folder, exist_ok=True)
            filepath = os.path.join(save_folder, filename)

            # Write image to disk
            cv2.imwrite(filepath, frame)
            self.log.info("Image saved to %s", filepath)
            return filepath

        except Exception as e:
            self.log.error("Error capturing image: %s", e)
            raise

        finally:
            try:
                self.camera.stop_grabbing()
                self.log.debug("Stopped grabbing after capture")
            except Exception:
                self.log.exception("Error stopping grab")

    def cleanup(self):
        """Ensure camera stream is stopped and device is closed."""
        try:
            self.camera.close()
            self.log.info("Camera closed successfully")
        except Exception:
            self.log.exception("Error during camera cleanup")
