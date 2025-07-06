from ImageConvert import *
from MVSDK import *
import numpy
import cv2
import gc

class Camera:
    def __init__(self):
        self.camera = None
        self.streamSource = None

    def enumerate(self):
        """Enumerate connected cameras, return the first camera found."""
        system = pointer(GENICAM_System())
        nRet = GENICAM_getSystemInstance(byref(system))
        if nRet != 0:
            raise RuntimeError("Failed to get system instance.")
        cameraList = pointer(GENICAM_Camera())
        cameraCnt = c_uint()
        nRet = system.contents.discovery(system, byref(cameraList), byref(cameraCnt), c_int(GENICAM_EProtocolType.typeAll))
        if nRet != 0 or cameraCnt.value < 1:
            raise RuntimeError("No camera found or discovery failed.")
        self.camera = cameraList[0]

    def open(self):
        """Open the first enumerated camera and prepare stream source."""
        if self.camera is None:
            self.enumerate()
        nRet = self.camera.connect(self.camera, c_int(GENICAM_ECameraAccessPermission.accessPermissionControl))
        if nRet != 0:
            raise RuntimeError("Failed to connect to camera.")

        # Prepare stream source
        streamSourceInfo = GENICAM_StreamSourceInfo()
        streamSourceInfo.channelId = 0
        streamSourceInfo.pCamera = pointer(self.camera)
        self.streamSource = pointer(GENICAM_StreamSource())
        nRet = GENICAM_createStreamSource(pointer(streamSourceInfo), byref(self.streamSource))
        if nRet != 0:
            raise RuntimeError("Failed to create stream source.")

        # Set trigger mode to Off for free-run acquisition
        trigModeEnumNode = pointer(GENICAM_EnumNode())
        trigModeEnumNodeInfo = GENICAM_EnumNodeInfo()
        trigModeEnumNodeInfo.pCamera = pointer(self.camera)
        trigModeEnumNodeInfo.attrName = b"TriggerMode"
        nRet = GENICAM_createEnumNode(byref(trigModeEnumNodeInfo), byref(trigModeEnumNode))
        if nRet != 0:
            raise RuntimeError("Failed to create TriggerMode node.")
        nRet = trigModeEnumNode.contents.setValueBySymbol(trigModeEnumNode, b"Off")
        trigModeEnumNode.contents.release(trigModeEnumNode)
        if nRet != 0:
            raise RuntimeError("Failed to set TriggerMode to Off.")

        # Start grabbing
        nRet = self.streamSource.contents.startGrabbing(
            self.streamSource,
            c_ulonglong(0),
            c_int(GENICAM_EGrabStrategy.grabStrartegySequential)
        )
        if nRet != 0:
            raise RuntimeError("Failed to start grabbing.")

    def get_frame(self, timeout=1000):
        """Retrieve one frame from the camera. Returns (cvImage, height, width, pixel_format)."""
        if self.streamSource is None:
            raise RuntimeError("Camera is not opened or stream source not initialized.")

        frame = pointer(GENICAM_Frame())
        nRet = self.streamSource.contents.getFrame(self.streamSource, byref(frame), c_uint(timeout))
        if nRet != 0:
            raise RuntimeError("Failed to get frame.")

        nRet = frame.contents.valid(frame)
        if nRet != 0:
            frame.contents.release(frame)
            raise RuntimeError("Frame is invalid.")

        imageParams = IMGCNV_SOpenParam()
        imageParams.dataSize = frame.contents.getImageSize(frame)
        imageParams.height = frame.contents.getImageHeight(frame)
        imageParams.width = frame.contents.getImageWidth(frame)
        imageParams.paddingX = frame.contents.getImagePaddingX(frame)
        imageParams.paddingY = frame.contents.getImagePaddingY(frame)
        imageParams.pixelForamt = frame.contents.getImagePixelFormat(frame)

        imageBuff = frame.contents.getImage(frame)
        userBuff = c_buffer(b'\0', imageParams.dataSize)
        memmove(userBuff, c_char_p(imageBuff), imageParams.dataSize)
        frame.contents.release(frame)

        if imageParams.pixelForamt == EPixelType.gvspPixelMono8:
            grayByteArray = bytearray(userBuff)
            cvImage = numpy.array(grayByteArray).reshape(imageParams.height, imageParams.width)
        else:
            rgbSize = c_int()
            rgbBuff = c_buffer(b'\0', imageParams.height * imageParams.width * 3)
            nRet = IMGCNV_ConvertToBGR24(
                cast(userBuff, c_void_p),
                byref(imageParams),
                cast(rgbBuff, c_void_p),
                byref(rgbSize)
            )
            colorByteArray = bytearray(rgbBuff)
            cvImage = numpy.array(colorByteArray).reshape(imageParams.height, imageParams.width, 3)

        gc.collect()
        return cvImage, imageParams.height, imageParams.width, imageParams.pixelForamt
    
    def set_exposure_time(self, exposure_us: float):
        """Set exposure time in microseconds."""
        from MVSDK import GENICAM_AcquisitionControlInfo, GENICAM_AcquisitionControl,\
            GENICAM_createAcquisitionControl, c_double, byref, pointer
        acq_ctrl_info = GENICAM_AcquisitionControlInfo()
        acq_ctrl_info.pCamera = pointer(self.camera)
        acq_ctrl = pointer(GENICAM_AcquisitionControl())
        nRet = GENICAM_createAcquisitionControl(pointer(acq_ctrl_info), byref(acq_ctrl))
        if nRet != 0:
            raise RuntimeError("Failed to create AcquisitionControl node.")
        double_node = acq_ctrl.contents.exposureTime(acq_ctrl)
        nRet = double_node.setValue(double_node, c_double(exposure_us))
        acq_ctrl.contents.release(acq_ctrl)
        if nRet != 0:
            raise RuntimeError("Failed to set exposure time.")


    def set_frame_rate(self, fps: float):
        """Set frame rate in Hz."""
        acq_ctrl_info = GENICAM_AcquisitionControlInfo()
        acq_ctrl_info.pCamera = pointer(self.camera)
        acq_ctrl = pointer(GENICAM_AcquisitionControl())
        nRet = GENICAM_createAcquisitionControl(pointer(acq_ctrl_info), byref(acq_ctrl))
        if nRet != 0:
            raise RuntimeError("Failed to create AcquisitionControl node.")
        # Some cameras require enabling frame rate control
        acq_ctrl.contents.acquisitionFrameRateEnable(acq_ctrl).setValue(acq_ctrl.contents.acquisitionFrameRateEnable(acq_ctrl), 1)
        nRet = acq_ctrl.contents.acquisitionFrameRate(acq_ctrl).setValue(acq_ctrl.contents.acquisitionFrameRate(acq_ctrl), c_double(fps))
        acq_ctrl.contents.release(acq_ctrl)
        if nRet != 0:
            raise RuntimeError("Failed to set frame rate.")

    def set_gain(self, gain: float):
        """Set analog gain (usually in dB or linear, see your SDK)."""
        analog_ctrl_info = GENICAM_AnalogControlInfo()
        analog_ctrl_info.pCamera = pointer(self.camera)
        analog_ctrl = pointer(GENICAM_AnalogControl())
        nRet = GENICAM_createAnalogControl(pointer(analog_ctrl_info), byref(analog_ctrl))
        if nRet != 0:
            raise RuntimeError("Failed to create AnalogControl node.")
        nRet = analog_ctrl.contents.gainRaw(analog_ctrl).setValue(analog_ctrl.contents.gainRaw(analog_ctrl), c_double(gain))
        analog_ctrl.contents.release(analog_ctrl)
        if nRet != 0:
            raise RuntimeError("Failed to set gain.")

    def set_gamma(self, gamma: float):
        """Set gamma value."""
        analog_ctrl_info = GENICAM_AnalogControlInfo()
        analog_ctrl_info.pCamera = pointer(self.camera)
        analog_ctrl = pointer(GENICAM_AnalogControl())
        nRet = GENICAM_createAnalogControl(pointer(analog_ctrl_info), byref(analog_ctrl))
        if nRet != 0:
            raise RuntimeError("Failed to create AnalogControl node.")
        nRet = analog_ctrl.contents.gamma(analog_ctrl).setValue(analog_ctrl.contents.gamma(analog_ctrl), c_double(gamma))
        analog_ctrl.contents.release(analog_ctrl)
        if nRet != 0:
            raise RuntimeError("Failed to set gamma.")

    def set_brightness(self, brightness: int):
        """Set brightness (integer, range depends on camera)."""
        isp_ctrl_info = GENICAM_ISPControlInfo()
        isp_ctrl_info.pCamera = pointer(self.camera)
        isp_ctrl = pointer(GENICAM_ISPControl())
        nRet = GENICAM_createISPControl(pointer(isp_ctrl_info), byref(isp_ctrl))
        if nRet != 0:
            raise RuntimeError("Failed to create ISPControl node.")
        nRet = isp_ctrl.contents.brightness(isp_ctrl).setValue(isp_ctrl.contents.brightness(isp_ctrl), c_longlong(brightness))
        isp_ctrl.contents.release(isp_ctrl)
        if nRet != 0:
            raise RuntimeError("Failed to set brightness.")

    def set_white_balance(self, red: float, green: float, blue: float):
        """Set white balance by channel ratios (if supported)."""
        analog_ctrl_info = GENICAM_AnalogControlInfo()
        analog_ctrl_info.pCamera = pointer(self.camera)
        analog_ctrl = pointer(GENICAM_AnalogControl())
        nRet = GENICAM_createAnalogControl(pointer(analog_ctrl_info), byref(analog_ctrl))
        if nRet != 0:
            raise RuntimeError("Failed to create AnalogControl node.")

        # Set balance ratio selector and ratio for each channel
        for color, value in [('Red', red), ('Green', green), ('Blue', blue)]:
            # Select channel
            enum_node = analog_ctrl.contents.balanceRatioSelector(analog_ctrl)
            nRet = enum_node.setValueBySymbol(byref(enum_node), color.encode())
            enum_node.release(byref(enum_node))
            if nRet != 0:
                analog_ctrl.contents.release(analog_ctrl)
                raise RuntimeError(f"Failed to select white balance channel {color}.")
            # Set channel value
            nRet = analog_ctrl.contents.balanceRatio(analog_ctrl).setValue(analog_ctrl.contents.balanceRatio(analog_ctrl), c_double(value))
            if nRet != 0:
                analog_ctrl.contents.release(analog_ctrl)
                raise RuntimeError(f"Failed to set white balance value for {color}.")
        analog_ctrl.contents.release(analog_ctrl)

    def close(self):
        """Stop grabbing, release stream source and disconnect camera."""
        if self.streamSource is not None:
            self.streamSource.contents.stopGrabbing(self.streamSource)
            self.streamSource.contents.release(self.streamSource)
            self.streamSource = None
        if self.camera is not None:
            self.camera.disConnect(byref(self.camera))
            self.camera = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
