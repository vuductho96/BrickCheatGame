import subprocess
from unittest.mock import patch
import cv2
import numpy as np
import pytest
from capture.adb_capture import ADBCapture,CaptureError

def test_usb_and_wireless_devices_are_available():
    capture=ADBCapture()
    with patch.object(capture,"_run",return_value=b"List of devices attached\nUSB123\tdevice\n192.168.1.8:39817\tdevice\nadb-abc._adb-tls-connect._tcp\tdevice\nlocked\tunauthorized\nlost\toffline\n"):
        assert capture.devices()==["USB123","192.168.1.8:39817","adb-abc._adb-tls-connect._tcp"]

def test_capture_only_runs_device_list_and_screencap():
    frame=np.zeros((32,32,3),dtype=np.uint8)
    png=cv2.imencode(".png",frame)[1].tobytes()
    capture=ADBCapture(serial="192.168.1.8:39817")
    with patch.object(capture,"_run",side_effect=[b"List of devices attached\n192.168.1.8:39817\tdevice\n",png]) as run:
        assert np.array_equal(capture.screenshot(),frame)
        assert run.call_args_list[1].args[0]==["-s","192.168.1.8:39817","exec-out","screencap","-p"]

def test_multiple_devices_requires_selection():
    capture=ADBCapture()
    with patch.object(capture,"devices",return_value=["usb","wifi"]):
        with pytest.raises(CaptureError): capture.screenshot()

@pytest.mark.parametrize("error",[FileNotFoundError(),subprocess.TimeoutExpired("adb",10),subprocess.CalledProcessError(1,"adb",stderr=b"offline")])
def test_actionable_errors(error):
    with patch("capture.adb_capture.subprocess.run",side_effect=error):
        with pytest.raises(CaptureError): ADBCapture().devices()
