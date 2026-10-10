"""Read-only ADB capture over USB or paired Wi-Fi. No touch, swipe, keyevent or shell execution."""
import subprocess
import cv2
import numpy as np

class CaptureError(RuntimeError): pass

class ADBCapture:
    def __init__(self,executable="adb",serial=None,timeout=10):
        self.executable,self.serial,self.timeout=executable,serial,timeout
    def _run(self,args):
        try:
            return subprocess.run([self.executable,*args],capture_output=True,check=True,
                                  timeout=self.timeout,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)).stdout
        except FileNotFoundError as exc:
            raise CaptureError("Không tìm thấy adb.exe. Cài Android Platform Tools và chọn đường dẫn ADB.") from exc
        except subprocess.TimeoutExpired as exc:
            raise CaptureError("ADB hết thời gian chờ. Kiểm tra USB hoặc Wi-Fi và cổng kết nối.") from exc
        except subprocess.CalledProcessError as exc:
            raise CaptureError(exc.stderr.decode("utf8","replace").strip() or "ADB capture failed") from exc
    def devices(self):
        lines=self._run(["devices"]).decode("utf8","replace").splitlines()
        return [line.split()[0] for line in lines if len(line.split())==2 and line.split()[1]=="device"]
    def screenshot(self):
        devices=self.devices()
        if self.serial:
            if self.serial not in devices: raise CaptureError("Thiết bị chưa được cấp quyền hoặc đã ngắt kết nối. Kiểm tra adb devices.")
            serial=self.serial
        elif len(devices)==1: serial=devices[0]
        else: raise CaptureError("Cần đúng một thiết bị được cấp quyền; hoặc bấm Thiết bị để chọn.")
        data=self._run(["-s",serial,"exec-out","screencap","-p"])
        if not data.startswith(b"\x89PNG\r\n\x1a\n"): raise CaptureError("Ảnh ADB không phải PNG hợp lệ.")
        frame=cv2.imdecode(np.frombuffer(data,dtype=np.uint8),cv2.IMREAD_COLOR)
        if frame is None: raise CaptureError("Không giải mã được ảnh ADB.")
        return frame
