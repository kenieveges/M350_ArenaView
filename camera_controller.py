import os
import sys
import time
import logging
from datetime import datetime
from typing import Optional, List

from arena_api import enums as arena_enums
from arena_api.enums import PixelFormat
from arena_api.__future__.save import Writer
from arena_api.system import system
from arena_api.buffer import BufferFactory


class CameraController:
    """Controller for managing camera operations including initialization, capture, and cleanup."""
    
    def __init__(self, retry_attempts: int = 6, retry_delay: int = 10):
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.devices = None
        self.device = None
        self.buffer = None
        self.tl_stream_nodemap = None
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing camera controller")
        
        
        self._initialize_camera()

    def _initialize_camera(self):
        """Initialize camera with retry logic."""
        self.logger.info("Starting camera initialization (retries: %s, delay: %ss)", 
                        self.retry_attempts, self.retry_delay)
        try:
            self.logger.debug("Attempting camera initialization")
            self.devices = self._create_device_with_retries()
            if not self.devices:
                self.logger.error("No camera devices found after %s attempts", self.retry_attempts)
                raise RuntimeError("Failed to initialize camera - no devices found")

            self.device = system.select_device(self.devices)
            self._configure_stream_settings()
            self.logger.info("Camera initialized successfully")
        except Exception as e:
            self.logger.exception("Camera initialization failed %s", e)
            raise

    def _configure_stream_settings(self):
        """Configure the stream settings for the camera."""
        self.tl_stream_nodemap = self.device.tl_stream_nodemap
        self.tl_stream_nodemap['StreamAutoNegotiatePacketSize'].value = True
        self.tl_stream_nodemap['StreamPacketResendEnable'].value = True

    def _create_device_with_retries(self) -> Optional[List]:
        """
        Attempt to create a camera device with retries.
        
        Returns:
            List of devices if successful, None otherwise
        """
        for attempt in range(self.retry_attempts):
            current_attempt = attempt + 1
            self.logger.debug("Connection attempt %s/%s", current_attempt, self.retry_attempts)
            devices = system.create_device()
            
            if devices:
                self.logger.info("Camera connection established on attempt %s", current_attempt)
                return devices
                
            if current_attempt < self.retry_attempts:  # Only log if there are more attempts
                self.logger.warning("Connection failed, retrying in %s seconds...", self.retry_delay)
                self._countdown(self.retry_delay)
                
        self.logger.error("No camera devices found after %s attempts", self.retry_attempts)
        return None

    def _countdown(self, seconds: int):
        """Display a countdown timer with logging."""
        self.logger.debug("Starting %s second countdown", seconds)
        for remaining in range(seconds, 0, -1):
            self.logger.debug("%s seconds remaining...", remaining)
            time.sleep(1)

    def capture_image(self, save_folder: str, layer: int, project_name: str) -> bool:
        """
        Capture and save an image from the camera.
        
        Args:
            save_folder: Directory to save the image
            layer: Current layer number for filename
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.device.start_stream()
            self.buffer = self.device.get_buffer()
            self._save_image(save_folder, layer, project_name)
            return True
        except Exception as e:
            print(f"Error capturing image: {e}")
            return False
        finally:
            self._cleanup_capture()

    def _save_image(self, save_folder: str, layer: int, project_name: str):
        """Save the captured image to disk."""
        pixel_format = PixelFormat.BGR8
        converted_buffer = None
        
        try:
            converted_buffer = BufferFactory.convert(self.buffer, pixel_format)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
            
            os.makedirs(save_folder, exist_ok=True)
            filename = f'{project_name}_{timestamp}_layer_{layer}.tiff'
            output_path = os.path.join(save_folder, filename)

            writer = Writer()
            writer.pattern = output_path
            writer.save(converted_buffer, 
                       compression=arena_enums.SC_TIFF_COMPRESSION_LIST.SC_NO_TIFF_COMPRESSION, 
                       cmykTags=False)
            
            print(f'Image saved to {output_path}')
        except Exception as e:
            print(f"Error saving image: {e}")
        finally:
            if converted_buffer:
                BufferFactory.destroy(converted_buffer)

    def _cleanup_capture(self):
        """Clean up resources after capture attempt."""
        try:
            if hasattr(self, 'buffer') and self.buffer:
                self.device.requeue_buffer(self.buffer)
            if hasattr(self, 'device') and self.device:
                self.device.stop_stream()
        except Exception as e:
            print(f"Error during cleanup: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def cleanup(self):
        """Clean up all camera resources."""
        try:
            if hasattr(self, 'device') and self.device:
                self.device.stop_stream()
                system.destroy_device()
                print('Camera resources released')
        except Exception as e:
            print(f"Error cleaning up camera: {e}")
