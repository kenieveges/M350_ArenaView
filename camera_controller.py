import os
import sys
import time
from datetime import datetime
from typing import Optional, List

from arena_api import enums as arena_enums
from arena_api.enums import PixelFormat
from arena_api.__future__.save import Writer
from arena_api.system import system
from arena_api.buffer import BufferFactory


class CameraController:
    """Controller for managing camera operations including initialization, capture, and cleanup."""
    
    DEFAULT_RETRY_ATTEMPTS = 6
    DEFAULT_RETRY_DELAY = 10  # seconds
    
    def __init__(self):
        self.devices = None
        self.device = None
        self.tl_stream_nodemap = None
        self.buffer = None
        
        self._initialize_camera()

    def _initialize_camera(self):
        """Initialize camera with retry logic."""
        self.devices = self._create_device_with_retries()
        if not self.devices:
            raise RuntimeError("Failed to initialize camera - no devices found")
            
        self.device = system.select_device(self.devices)
        self._configure_stream_settings()
        print("Camera initialized successfully")

    def _configure_stream_settings(self):
        """Configure the stream settings for the camera."""
        self.tl_stream_nodemap = self.device.tl_stream_nodemap
        self.tl_stream_nodemap['StreamAutoNegotiatePacketSize'].value = True
        self.tl_stream_nodemap['StreamPacketResendEnable'].value = True

    def _create_device_with_retries(self, max_attempts: int = DEFAULT_RETRY_ATTEMPTS, 
                                  retry_delay: int = DEFAULT_RETRY_DELAY) -> Optional[List]:
        """
        Attempt to create a camera device with retries.
        
        Args:
            max_attempts: Maximum number of connection attempts
            retry_delay: Delay between attempts in seconds
            
        Returns:
            List of devices if successful, None otherwise
        """
        for attempt in range(max_attempts):
            devices = system.create_device()
            if devices:
                return devices
                
            print(f'Attempt {attempt + 1} of {max_attempts}: '
                  f'waiting {retry_delay} seconds for device...')
            self._countdown(retry_delay)
            
        print('No device found! Please connect a device and try again.')
        return None

    def _countdown(self, seconds: int):
        """Display a countdown timer."""
        for remaining in range(seconds, 0, -1):
            print(f'{remaining} seconds remaining...', end='\r')
            time.sleep(1)
        print(' ' * 20, end='\r')  # Clear line

    def capture_image(self, save_folder: str, layer: int) -> bool:
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
            self._save_image(save_folder, layer)
            return True
        except Exception as e:
            print(f"Error capturing image: {e}")
            return False
        finally:
            self._cleanup_capture()

    def _save_image(self, save_folder: str, layer: int):
        """Save the captured image to disk."""
        pixel_format = PixelFormat.BGR8
        converted_buffer = None
        
        try:
            converted_buffer = BufferFactory.convert(self.buffer, pixel_format)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
            
            os.makedirs(save_folder, exist_ok=True)
            filename = f'image_{timestamp}_layer_{layer}.tiff'
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
