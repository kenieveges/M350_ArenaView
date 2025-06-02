# Usage Example (for your own script, not inside this file):
import cv2
import numpy as np
from MVCamera import Camera

def resize_image(image: np.ndarray, size: list[float, float] = None, scale: int = None):
    """
    Resize image either by target size or integer scale factor.
    :param image: input image (NumPy array).
    :param size: tuple (new_height, new_width) or None.
    :param scale: integer scale factor or None.
    :return: resized image.
    """
    if size is not None:
        # Size: (height, width)
        return cv2.resize(image, (size[1], size[0]), interpolation=cv2.INTER_AREA)
    elif scale is not None:
        if not isinstance(scale, int) or scale < -1:
            raise ValueError("Scale must be a positive integer.")
        new_height = image.shape[0] * scale
        new_width = image.shape[1] * scale
        return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
    else:
        raise ValueError("Either size or scale must be specified.")

with Camera() as cam:
    cam.set_exposure_time(10000)
    cam.set_frame_rate(32)
    cam.set_gain(1.0)
    cam.set_gamma(1.0)
    cam.set_brightness(100)
    cam.set_white_balance(red=1.86, green=1.0, blue=4.90)
    img, height, width, pixfmt = cam.get_frame()

    scale = 0.25  # 25% of original size
    rimg = cv2.resize(img, None, fx=scale,\
                             fy=scale, interpolation=cv2.INTER_AREA)
    cv2.imshow("Camera Frame", rimg)
    cv2.waitKey(0)
    cv2.destroyAllWindows()