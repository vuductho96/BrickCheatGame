"""scrcpy 5.0.1 raw H.264 stream and persistent touch control, loopback only."""
import socket
import struct
import subprocess
import threading
import time
import secrets
from pathlib import Path
import av
import cv2
cv2.setNumThreads(1)

class LiveMirror:
    def __init__(self, adb):
        self.adb = adb
        self.condition = threading.Condition()
        self.input_lock = threading.Lock()
        self.frame = self.jpeg = None
        self.sequence = 0
        self.updated = 0
        self.error = "Đang kết nối luồng trực tiếp"
        self.control = self.video = self.process = None
        self.closed = False
        self.pressed = False
        self.touch_at = 0
        self.touch_position = (0, 0)
        self.touch_size = None
        self.thread = None

    def start(self, ensure_device):
        if self.thread and self.thread.is_alive(): return
        self.thread = threading.Thread(target=self._run, args=(ensure_device,), daemon=True)
        self.thread.start()
        threading.Thread(target=self._watchdog, daemon=True).start()

    def _adb(self, *args):
        return subprocess.check_output([self.adb.executable, "-s", self.adb.serial, *args],
            stderr=subprocess.STDOUT, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def _connect(self, port):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            sock = socket.create_connection(("127.0.0.1", port), timeout=2)
            try:
                if sock.recv(1) == b"\x00":
                    sock.settimeout(None)
                    return sock
            except (OSError, TimeoutError): pass
            sock.close()
            time.sleep(.2)
        raise RuntimeError("scrcpy chưa mở được luồng video")

    def _run(self, ensure_device):
        while not self.closed:
            port = None
            try:
                ensure_device()
                server = Path(__file__).parent / "tools" / "scrcpy-server-v5.0.1"
                self._adb("push", str(server), "/data/local/tmp/shopee-live-server.jar")
                scid = secrets.randbelow(0x7fffffff)
                port = int(self._adb("forward", "tcp:0", f"localabstract:scrcpy_{scid:08x}").strip())
                log = open(Path(__file__).parent / "artifacts" / "scrcpy-live.log", "ab")
                args = ["CLASSPATH=/data/local/tmp/shopee-live-server.jar", "app_process", "/",
                    "com.genymobile.scrcpy.Server", "5.0.1", f"scid={scid:08x}",
                    "tunnel_forward=true", "audio=false", "control=true",
                    "video_codec=h264", "max_fps=20", "max_size=1170", "video_bit_rate=2500000",
                    "send_device_meta=false", "send_stream_meta=false",
                    "send_frame_meta=false", "send_dummy_byte=true", "clipboard_autosync=false"]
                self.process = subprocess.Popen([self.adb.executable, "-s", self.adb.serial, "shell", *args],
                    stdout=log, stderr=log, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                log.close()
                self.video = self._connect(port)
                self.control = socket.create_connection(("127.0.0.1", port), timeout=3)
                self.control.settimeout(3)
                self.control.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
                threading.Thread(target=self._drain_control, args=(self.control,), daemon=True).start()
                codec = av.CodecContext.create("h264", "r")
                codec.thread_count = 1
                while not self.closed:
                    chunk = self.video.recv(65536)
                    if not chunk: raise RuntimeError("Luồng điện thoại đã ngắt")
                    for packet in codec.parse(chunk):
                        for decoded in codec.decode(packet):
                            frame = decoded.to_ndarray(format="bgr24")
                            # Recognition uses full resolution; browser receives a smaller live video.
                            display = frame
                            self.touch_size=(frame.shape[1],frame.shape[0])
                            frame=cv2.resize(frame,(1080,2340),interpolation=cv2.INTER_NEAREST) if self.touch_size==(540,1170) else frame
                            ok, jpeg = cv2.imencode(".jpg", display, [cv2.IMWRITE_JPEG_QUALITY, 78])
                            if not ok: continue
                            with self.condition:
                                self.frame, self.jpeg = frame, jpeg.tobytes()
                                self.sequence += 1
                                self.updated = time.monotonic()
                                self.error = None
                                self.condition.notify_all()
            except Exception as exc:
                with self.condition:
                    self.error = str(exc)
                    self.condition.notify_all()
            finally:
                with self.input_lock:
                    self.pressed = False
                    for sock in (self.control, self.video):
                        if sock:
                            try: sock.close()
                            except OSError: pass
                    self.control = self.video = None
                if self.process and self.process.poll() is None:
                    self.process.terminate()
                    try: self.process.wait(timeout=3)
                    except subprocess.TimeoutExpired: self.process.kill()
                if port:
                    try: self._adb("forward", "--remove", f"tcp:{port}")
                    except Exception: pass
            time.sleep(2)

    def _drain_control(self, sock):
        try:
            while sock.recv(4096): pass
        except OSError: pass

    def screenshot(self):
        with self.condition:
            deadline = time.monotonic() + 4
            while self.frame is None or self.error:
                remaining = deadline - time.monotonic()
                if remaining <= 0: raise RuntimeError(self.error or "Luồng trực tiếp đang chờ điện thoại")
                self.condition.wait(min(remaining, .5))
            return self.frame.copy()

    def status(self):
        with self.condition:
            return {"live": self.error is None and self.frame is not None,
                "error": self.error, "frames": self.sequence,
                "width": self.touch_size[0] if self.touch_size else (self.frame.shape[1] if self.frame is not None else 1080),
                "height": self.touch_size[1] if self.touch_size else (self.frame.shape[0] if self.frame is not None else 2340)}

    def touch(self, action, x, y):
        if type(action) is not int or action not in (0, 1, 2, 3):
            raise ValueError("Thao tác không hợp lệ")
        with self.input_lock:
            if not self.control or self.error: raise RuntimeError(self.error or "Chưa có luồng trực tiếp")
            if self.frame is None: raise RuntimeError("Chưa có video")
            height, width = (self.touch_size[1],self.touch_size[0]) if self.touch_size else self.frame.shape[:2]
            if type(x) is not int or type(y) is not int or not 0<=x<width or not 0<=y<height:
                raise ValueError("Tọa độ không hợp lệ")
            if action != 0 and not self.pressed: return
            if action == 0 and self.pressed: raise ValueError("Đang có thao tác kéo")
            self.control.sendall(struct.pack(">BBQiiHHHII", 2, action, 0xfffffffffffffffe,
                x, y, width, height, 0 if action in (1,3) else 0xffff, 1, 0 if action in (1,3) else 1))
            self.pressed = action in (0, 2)
            self.touch_at = time.monotonic()
            self.touch_position = (x,y)

    def _watchdog(self):
        while not self.closed:
            time.sleep(.5)
            if self.pressed and time.monotonic()-self.touch_at>5:
                try: self.touch(1, *self.touch_position)
                except Exception: pass

    def stop(self):
        self.closed = True
        try:
            if self.pressed: self.touch(1, *self.touch_position)
        except Exception: pass
        for sock in (self.control, self.video):
            if sock:
                try: sock.shutdown(socket.SHUT_RDWR)
                except OSError: pass
