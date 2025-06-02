import dearpygui.dearpygui as dpg
import numpy as np
import cv2
from MVCamera import Camera

dpg.create_context()
dpg.create_viewport(title="Camera Control UI", width=1100, height=700)
dpg.setup_dearpygui()

cam = Camera()
cam.open()
frame, height, width, pixfmt = cam.get_frame()

# Downscale factor state
downscale_factors = ["0.05", "0.1", "0.2", "0.25", "0.33", "0.4", "0.5"]
DEFAULT_DOWNSCALE = 0.25

def get_downscale_factor():
    val = dpg.get_value("downscale_radio")
    if val is None:
        print("[DPG] Downscale radio not yet initialized, using default value")
        return DEFAULT_DOWNSCALE
    return float(val)

def frame_to_dpg_texture(frame):
    scale = get_downscale_factor()
    small_frame = cv2.resize(frame, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    if len(small_frame.shape) == 2:  # grayscale
        small_frame = np.stack([small_frame]*3, axis=-1)
    data = np.flip(small_frame, 2)
    data = data.ravel()
    data = np.asfarray(data, dtype='f')
    texture_data = np.true_divide(data, 255.0)
    return texture_data, small_frame.shape[1], small_frame.shape[0]


texture_data, tex_width, tex_height = frame_to_dpg_texture(frame)

with dpg.texture_registry(show=False):
    dpg.add_raw_texture(tex_width, tex_height, texture_data, tag="cam_texture", format=dpg.mvFormat_Float_rgb)

def update_texture_size(sender, app_data, user_data):
    # Called when user changes downscale factor, to re-allocate the texture size for DPG
    frame, _, _, _ = cam.get_frame()
    texture_data, new_width, new_height = frame_to_dpg_texture(frame)
    # Delete previous texture and image widget if they exist
    if dpg.does_item_exist("cam_texture"):
        dpg.delete_item("cam_texture")
    if dpg.does_item_exist("cam_image"):
        dpg.delete_item("cam_image")
    # Create new texture and image widget with new size
    with dpg.texture_registry(show=False):
        dpg.add_raw_texture(new_width, new_height, texture_data, tag="cam_texture", format=dpg.mvFormat_Float_rgb)
    with dpg.window(label="Camera Feed", width=new_width, height=new_height, pos=(420,0), tag="feed_window"):
        dpg.add_image("cam_texture", tag="cam_image")

with dpg.window(label="Camera Controls", width=400, height=500, pos=(0,0)):
    dpg.add_text("Scale factors")
    dpg.add_radio_button(downscale_factors, default_value="0.25", horizontal=True, tag="downscale_radio", callback=update_texture_size)
    dpg.add_text("Downscale Factor", color=(150,150,150))
    dpg.add_slider_float(label="Exposure (us)", min_value=20.0, max_value=100000.0, default_value=20000, callback=lambda s,a,u: cam.set_exposure_time(a))
    dpg.add_slider_float(label="Frame Rate (Hz)", min_value=1.0, max_value=32.0, default_value=24, callback=lambda s,a,u: cam.set_frame_rate(a))
    dpg.add_slider_float(label="Gain", min_value=1.0, max_value=32.0, default_value=1.0, callback=lambda s,a,u: cam.set_gain(a))
    dpg.add_slider_float(label="Gamma", min_value=0.0, max_value=4.0, default_value=0.78, callback=lambda s,a,u: cam.set_gamma(a))
    dpg.add_slider_int(label="Brightness", min_value=0, max_value=100, default_value=100, callback=lambda s,a,u: cam.set_brightness(int(a)))
    dpg.add_separator()
    dpg.add_text("White Balance (R/G/B):")
    dpg.add_slider_float(label="Red", min_value=0.0, max_value=15.0, default_value=2.13, tag="wb_r", callback=lambda s,a,u: cam.set_white_balance(dpg.get_value("wb_r"), dpg.get_value("wb_g"), dpg.get_value("wb_b")))
    dpg.add_slider_float(label="Green", min_value=0.0, max_value=15.0, default_value=1.0, tag="wb_g", callback=lambda s,a,u: cam.set_white_balance(dpg.get_value("wb_r"), dpg.get_value("wb_g"), dpg.get_value("wb_b")))
    dpg.add_slider_float(label="Blue", min_value=0.0, max_value=15.0, default_value=4.04, tag="wb_b", callback=lambda s,a,u: cam.set_white_balance(dpg.get_value("wb_r"), dpg.get_value("wb_g"), dpg.get_value("wb_b")))
    dpg.add_separator()
    dpg.add_text("", tag="status_text")

with dpg.window(label="Camera Feed", width=tex_width, height=tex_height, pos=(420,0)):
    dpg.add_image("cam_texture")

dpg.show_viewport()

try:
    while dpg.is_dearpygui_running():
        frame, _, _, _ = cam.get_frame()
        texture_data, tex_width, tex_height = frame_to_dpg_texture(frame)
        # Only update if the texture still exists
        if dpg.does_item_exist("cam_texture"):
            dpg.set_value("cam_texture", texture_data)
        dpg.render_dearpygui_frame()
finally:
    cam.close()
    dpg.destroy_context()
