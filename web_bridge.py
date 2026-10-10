"""Local-only HTML companion. User-originated drag requests drive the paired phone."""
import hashlib
import json
import mimetypes
import secrets
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import cv2
import numpy as np
from capture.adb_capture import ADBCapture
from capture.frame_stabilizer import FrameStabilizer
from engine.game_state import GameState
from engine.simulator import Move,apply_move
from solver.heuristics import SURVIVAL_WEIGHTS
from solver.stochastic import StochasticSolver
from vision.board_detector import Rect
from vision.cell_classifier import classify_cells
from vision.piece_detector import detect_piece,detect_tray_piece
from config.settings import load_settings

ROOT=Path(__file__).resolve().parent
WEB=ROOT/"web"
CAPTURES=ROOT/"captures"
if not (CAPTURES/"win-template.png").exists():CAPTURES=ROOT/"tests"/"fixtures"/"captures"
# Read each complete tray third, rather than a tight box around common shapes.
# A five-cell bar is ~290 px wide and was clipped by the old 260 px box.
# Keep the tray border outside the mask, since its color resembles a block.
# Five-cell vertical bars protrude above and below the tray decoration.
# Include their whole footprint; the dim blue frame is excluded by brightness.
SLOTS=((46,1645,329,325),(375,1645,330,325),(705,1645,329,325))
BOARD=Rect(46,640,988,990)
EMPTY=(8,61,56)
PITCH=58

class BridgeError(RuntimeError): pass

class PhoneBridge:
    def __init__(self):
        settings=load_settings()
        self.adb=ADBCapture(settings["adb_path"],settings.get("serial"))
        self.device_identity=settings.get("device_identity")
        self.solver=StochasticSolver(width=120,time_limit=0.8,weights=SURVIVAL_WEIGHTS,commit_tray=True)
        self.lock=threading.Lock()
        self.current=None
        self.frame=None
        self.png=None
        self.receipt=None
        self.input_y_offset=0  # Can be calibrated against observed touch-to-block offset.
        self.stabilizer=FrameStabilizer(required=3)
        self.closed=False
        self.live=None
        self.auto=None
        self.observer=None
        self.state_lock=threading.Lock()
        self.observation_error=None
        self.win_template=cv2.imread(str(CAPTURES/"win-template.png"))
        reference=cv2.imread(str(CAPTURES/"shopee-game-over.png"))
        self.over_template=reference[430:575,175:910] if reference is not None else None
        self.classic_over_title=cv2.imread(str(CAPTURES/"classic-over-title.png"))
        self.classic_loss_title=cv2.imread(str(CAPTURES/"classic-loss-title.png"))
        self.classic_over_replay=cv2.imread(str(CAPTURES/"classic-over-replay.png"))
    def ensure_device(self):
        devices=self.adb.devices()
        if self.adb.serial in devices: return
        if not self.adb.serial and len(devices)==1:
            self.adb.serial=devices[0]
            return
        # Reconnect only the user's known S23+ hardware identity, never another LAN device.
        known=self.device_identity or (self.adb.serial or "").split("._adb-")[0]
        if not known.startswith("adb-"):
            raise BridgeError("Chọn serial thiết bị trong config/settings.json; không tự kết nối thiết bị LAN khác.")
        matching=next((d for d in devices if d.startswith(known)),None)
        if matching:
            self.adb.serial=matching
            return
        discovered=self.adb._run(["mdns","services"]).decode("utf8","replace")
        for line in discovered.splitlines():
            row=line.split()
            if len(row)>=3 and row[0].startswith(known) and row[1]=="_adb-tls-connect._tcp":
                self.adb._run(["connect",row[2]])
                if row[2] in self.adb.devices():
                    self.adb.serial=row[2]
                    return
                alias=next((d for d in self.adb.devices() if d.startswith(known)),None)
                if alias:
                    self.adb.serial=alias
                    return
        raise BridgeError("S23+ đang ngắt ADB. Mở khóa, bật Gỡ lỗi không dây và để PC/điện thoại cùng Wi-Fi, rồi đợi kết nối lại.")
    def command(self,*args,timeout=12):
        try:
            result=subprocess.run([self.adb.executable,"-s",self.adb.serial,"shell","input",*map(str,args)],
                capture_output=True,check=True,timeout=timeout,
                creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            return result
        except subprocess.CalledProcessError as exc:
            raise BridgeError(exc.stderr.decode("utf8","replace") or "Không gửi được thao tác ADB.") from exc
        except subprocess.TimeoutExpired as exc:
            raise BridgeError("Thao tác ADB hết thời gian chờ.") from exc
    def is_over(self,frame):
        if frame.shape[:2]!=(2340,1080): return False
        if self.over_template is not None:
            patch=frame[430:575,175:910]
            if float(cv2.matchTemplate(patch,self.over_template,cv2.TM_CCOEFF_NORMED)[0,0])>0.82:return True
        # Match two fixed labels, never the changing numeric score or board.
        if self.classic_over_title is None or self.classic_over_replay is None:return False
        title=frame[420:700,170:920];replay=frame[1720:1920,220:860]
        title_score=max(cv2.minMaxLoc(cv2.matchTemplate(title,template,cv2.TM_CCOEFF_NORMED))[1]
                        for template in (self.classic_over_title,self.classic_loss_title) if template is not None)
        replay_score=cv2.minMaxLoc(cv2.matchTemplate(replay,self.classic_over_replay,cv2.TM_CCOEFF_NORMED))[1]
        return min(title_score,replay_score)>.85
    def is_win(self,frame):
        if self.win_template is None or frame.shape[:2]!=(2340,1080): return False
        area=frame[400:930,100:980]
        score=float(cv2.minMaxLoc(cv2.matchTemplate(area,self.win_template,cv2.TM_CCOEFF_NORMED))[1])
        yellow=cv2.inRange(cv2.cvtColor(frame[1760:1980,170:920],cv2.COLOR_BGR2HSV),
            np.array([15,100,130]),np.array([40,255,255]))
        return score>.78 and np.count_nonzero(yellow)>35000
    def parse(self,frame):
        if frame.shape[:2]!=(2340,1080):
            raise BridgeError("Độ phân giải điện thoại đã đổi. Bản hiện tại đã hiệu chỉnh cho 1080×2340.")
        if self.is_over(frame):
            return {"phase":"game_over","state":None,"pieces":[],"colors":[],"board":[],"state_id":"over"}
        if self.is_win(frame):
            return {"phase":"level_complete","state":None,"pieces":[],"colors":[],"board":[],"state_id":"win"}
        # A hidden/dimmed board must not become a falsely occupied matrix.
        hsv=cv2.cvtColor(frame,cv2.COLOR_BGR2HSV)
        green=cv2.inRange(hsv,np.array([65,120,100]),np.array([90,255,255]))
        contours,_=cv2.findContours(green,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        has_board=any(w>950 and h>950 and abs(w-h)<25 for x,y,w,h in map(cv2.boundingRect,contours))
        if not has_board: raise BridgeError("Bàn cờ đang bị che hoặc chưa mở. Mở game trên điện thoại rồi đợi kết nối lại.")
        recognition=classify_cells(frame,BOARD,8,EMPTY,tolerance=48,margin=5)
        if recognition.ambiguous:
            raise BridgeError("Có ô chưa nhận diện chắc chắn. Đợi hiệu ứng kết thúc rồi đợi kết nối lại.")
        crop=BOARD.crop(frame)
        colors=[]
        for r in range(8):
            row=[]
            for c in range(8):
                if recognition.board & (1 << (r*8+c)):
                    rgb=np.median(crop[int((r+.4)*990/8):int((r+.6)*990/8),
                                       int((c+.4)*988/8):int((c+.6)*988/8)].reshape(-1,3),axis=0)[::-1]
                    row.append("#"+"".join(f"{int(v):02x}" for v in rgb))
                else: row.append(None)
            colors.append(row)
        pieces=[]
        descriptors=[]
        for slot,roi in enumerate(SLOTS):
            patch=Rect(*roi).crop(frame)
            hsv=cv2.cvtColor(patch,cv2.COLOR_BGR2HSV)
            mask=cv2.inRange(hsv,np.array([0,70,150]),np.array([179,255,255]))
            ys,xs=np.where(mask>0)
            if len(xs)<PITCH*PITCH*.12: continue  # Used slot stays empty.
            piece,cell_pitch=detect_tray_piece(frame,Rect(*roi),chr(65+slot),PITCH,max_size=8,min_value=150)
            pieces.append(piece)
            rgb=np.median(patch[mask>0],axis=0)[::-1]
            color="#"+"".join(f"{int(v):02x}" for v in rgb)
            descriptors.append({"id":piece.id,"slot":slot,"cells":[list(c) for c in piece.cells],
                "width":piece.width,"height":piece.height,"color":color,"pitch":cell_pitch,
                "bounds":[roi[0]+int(xs.min()),roi[1]+int(ys.min()),int(xs.max()-xs.min()+1),int(ys.max()-ys.min()+1)]})
        state=GameState(8,recognition.board,tuple(pieces))
        signature=json.dumps(state.to_dict(),sort_keys=True)
        return {"phase":"playing" if pieces else "waiting_for_pieces","state":state,"board":state.matrix(),
                "colors":colors,"pieces":descriptors,"state_id":hashlib.sha256(signature.encode()).hexdigest()[:20]}
    def snapshot(self):
        return self.live.screenshot() if self.live else self.adb.screenshot()
    def save_frame(self,frame):
        self.frame=frame
        ok,png=cv2.imencode(".png",frame)
        if not ok: raise BridgeError("Không mã hóa được ảnh.")
        self.png=png.tobytes()
        captures=ROOT/"captures"
        captures.mkdir(exist_ok=True)
        # Live frames stay in memory; no screenshot polling or per-frame disk writes.
    def capture_stable(self):
        stabilizer=FrameStabilizer(required=3)
        regions=(BOARD.tuple(),*SLOTS)
        for attempt in range(7):
            frame=self.snapshot()
            self.save_frame(frame)
            if stabilizer.update(frame,regions): return frame
            time.sleep(.12)
        raise BridgeError("Ảnh còn animation. Đợi một chút rồi đợi kết nối lại.")
    def publish(self,parsed):
        with self.state_lock:
            fresh=dict(parsed)
            fresh["observed_at"]=time.time()
            fresh["source_frame"]=self.live.sequence if self.live else 0
            self.current=fresh
            self.observation_error=None
    def serialize(self,parsed):
        result={k:v for k,v in parsed.items() if k not in ("state",)}
        result.update({"connected":True,"serial":self.adb.serial,"device":"Samsung S23+",
                       "image":"/api/screen.png","captured_at":parsed.get("observed_at",time.time()),"receipt":self.receipt})
        auto_status=self.auto.status() if self.auto else {}
        result["sync"]="moving" if auto_status.get("stage") in ("moving","settling") else "stable"
        result["pending_move"]=auto_status.get("pending_move")
        result["execution"]=auto_status.get("execution")
        result["last_check"]=auto_status.get("last_check")
        result["plan_state_id"]=parsed["state_id"]
        state=parsed.get("state")
        if result["sync"]=="moving":
            result["plans"]=[]
            return result
        if state and state.pieces:
            if self.auto and self.auto.active:
                search=self.auto.result if self.auto.result_state==state else None
            else:search=(self.auto.solvers[self.auto.mode] if self.auto else self.solver).solve(state)
            if search is None:
                result["plans"]=[]
                return result
            result["plans"]=[{"value":p.value,"depth":p.depth,"cleared":p.cleared,
                "moves":[{"piece_id":m.piece_id,"row":m.row,"col":m.col} for m in p.moves]} for p in search.plans]
            result["search"]={"ms":round(search.elapsed_ms),"explored":search.explored,"timed_out":search.timed_out,"cached":search.cached,
                              "future_samples":search.future_samples,"future_survived":search.future_survived,
                              "future_horizon":search.future_horizon}
        else: result["plans"]=[]
        return result
    def refresh(self):
        # Read current video even when Auto is armed. No long input lock or frozen cache.
        if self.live:
            if not self.live.status()["live"]:raise BridgeError(self.live.error or "Đang kết nối lại điện thoại")
            moving=self.auto and self.auto.active and self.auto.stage in ("moving","settling")
            manual=self.live.pressed
            with self.state_lock:
                parsed=self.current
            if moving or manual:
                if parsed is None:raise BridgeError("Đợi bàn ổn định")
                data=self.serialize(parsed)
                data["sync"]="moving"
                data["plans"]=[]
                return data
            if parsed and self.observer:
                age=time.time()-parsed.get("observed_at",0)
                if age>2:
                    raise BridgeError(self.observation_error or "Đợi bàn ổn định từ video mới nhất")
                return self.serialize(parsed)
        with self.lock:
            self.ensure_device()
            parsed=self.parse(self.capture_stable())
            self.publish(parsed)
            return self.serialize(self.current)
    def drag(self,data):
        with self.lock:
            self.ensure_device()
            # Refresh immediately before input; another phone action invalidates a stale PC drag.
            observed=self.parse(self.snapshot())
            self.current=observed
            if observed["phase"]!="playing": raise BridgeError("Điện thoại chưa ở bàn chơi có khối.")
            if data.get("state_id")!=observed["state_id"]:
                self.save_frame(self.snapshot())
                raise BridgeError("Bàn điện thoại đã đổi. Cập nhật gợi ý trước khi kéo khối.")
            row,col=data.get("row"),data.get("col")
            if type(row) is not int or type(col) is not int: raise BridgeError("Tọa độ không hợp lệ.")
            move=Move(data.get("piece_id"),row,col)
            step=apply_move(observed["state"],move)
            piece=next(p for p in observed["pieces"] if p["id"]==move.piece_id)
            grab=data.get("grab",[.5,.5])
            if not isinstance(grab,list) or len(grab)!=2 or any(not isinstance(v,(int,float)) or not np.isfinite(v) for v in grab):
                raise BridgeError("Điểm kéo không hợp lệ.")
            gr,gc=grab
            if not 0<=gr<piece["height"] or not 0<=gc<piece["width"] or [int(gr),int(gc)] not in piece["cells"]:
                raise BridgeError("Cần kéo từ một ô của khối.")
            x,y,w,h=piece["bounds"]
            sx=round(x+gc*w/piece["width"])
            sy=round(y+gr*h/piece["height"])
            ex=round(BOARD.x+(col+gc)*BOARD.width/8)
            ey=round(BOARD.y+(row+gr)*BOARD.height/8+self.input_y_offset)
            self.command("touchscreen","swipe",sx,sy,ex,ey,750)
            time.sleep(.4)
            frame=self.capture_stable()
            actual=self.parse(frame)
            self.current=actual
            actual_state=actual.get("state")
            verified=actual_state is not None and actual_state.board==step.state.board
            self.receipt={"piece_id":move.piece_id,"row":row,"col":col,"verified":verified,
                          "source":[sx,sy],"target":[ex,ey],
                          "message":"Đã đặt trên điện thoại và kiểm tra khớp." if verified else
                                    "Điện thoại chưa khớp vị trí dự kiến; đã nạp lại bàn thực tế. Không gửi thêm thao tác."}
            return self.serialize(actual)
    def tap(self,data):
        with self.lock:
            self.ensure_device()
            x,y=data.get("x"),data.get("y")
            if type(x) is not int or type(y) is not int or not 0<=x<1080 or not 0<=y<2340:
                raise BridgeError("Tọa độ chạm không hợp lệ.")
            self.command("touchscreen","tap",x,y)
            self.receipt=None
            time.sleep(.3)
            frame=self.capture_stable()
            parsed=self.parse(frame)
            self.current=parsed
            return self.serialize(parsed)

BRIDGE=PhoneBridge()
TOKEN=secrets.token_urlsafe(24)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,format,*args):
        print(self.address_string(),format%args,flush=True)
    def send(self,status,body,content_type="application/json"):
        if isinstance(body,(dict,list)): body=json.dumps(body,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type",content_type)
        self.send_header("Content-Length",str(len(body)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        path=urlparse(self.path).path
        try:
            if path=="/api/auto":
                return self.send(200,BRIDGE.auto.status())
            if path=="/api/live-status":
                return self.send(200,BRIDGE.live.status() if BRIDGE.live else {"live":False})
            if path=="/api/live.mjpeg":
                return self.stream_live()
            if path=="/api/session":
                return self.send(200,{"token":TOKEN,"version":"auto-local-18","ai":False})
            if path=="/api/screen.png":
                if not BRIDGE.png: return self.send(404,{"error":"Chưa có ảnh."})
                return self.send(200,BRIDGE.png,"image/png")
            if path=="/api/state":
                return self.send(200,BRIDGE.refresh())
            if path=="/": path="/index.html"
            target=(WEB/path.lstrip("/")).resolve()
            if WEB.resolve() not in target.parents or not target.is_file():
                return self.send(404,b"Not found","text/plain")
            return self.send(200,target.read_bytes(),mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        except Exception as exc: self.send(409,{"error":str(exc)})
    def stream_live(self):
        self.send_response(200)
        self.send_header("Content-Type","multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        previous=-1
        try:
            while BRIDGE.live and not BRIDGE.live.closed:
                with BRIDGE.live.condition:
                    BRIDGE.live.condition.wait_for(lambda: BRIDGE.live.sequence!=previous or BRIDGE.live.closed,timeout=2)
                    jpeg=BRIDGE.live.jpeg
                    sequence=BRIDGE.live.sequence
                    healthy=BRIDGE.live.error is None
                if not jpeg or sequence==previous or not healthy: continue
                previous=sequence
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "+str(len(jpeg)).encode()+b"\r\n\r\n"+jpeg+b"\r\n")
                self.wfile.flush()
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError): pass
    def do_POST(self):
        try:
            origin=self.headers.get("Origin")
            if origin and origin not in ("http://127.0.0.1:8765","http://localhost:8765"):
                return self.send(403,{"error":"Origin not allowed"})
            if self.headers.get("X-Session-Token")!=TOKEN: return self.send(403,{"error":"Invalid local session"})
            length=int(self.headers.get("Content-Length",0))
            if not 0<length<=4096: return self.send(400,{"error":"Invalid request"})
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict): return self.send(400,{"error":"Invalid request"})
            if self.path=="/api/auto":
                if data.get("action")=="start":return self.send(200,BRIDGE.auto.start(data.get("mode","balanced")))
                if data.get("action")=="mode":return self.send(200,BRIDGE.auto.set_mode(data.get("mode")))
                if data.get("action")=="stop":return self.send(200,BRIDGE.auto.stop())
                raise BridgeError("Lệnh Auto không hợp lệ")
            if self.path=="/api/touch":
                if not BRIDGE.live: raise BridgeError("Luồng trực tiếp chưa sẵn sàng")
                if data.get("action")==0 and BRIDGE.auto.active:BRIDGE.auto.stop("Đã dừng Auto để thao tác tay",wait=True)
                BRIDGE.live.touch(data.get("action"),data.get("x"),data.get("y"))
                return self.send(200,{"ok":True})
            if self.path=="/api/move": return self.send(200,BRIDGE.drag(data))
            if self.path=="/api/tap": return self.send(200,BRIDGE.tap(data))
            return self.send(404,{"error":"Not found"})
        except Exception as exc: self.send(409,{"error":str(exc)})

def main():
    from live_mirror import LiveMirror
    BRIDGE.live=LiveMirror(BRIDGE.adb)
    BRIDGE.live.start(BRIDGE.ensure_device)
    from autopilot import Autopilot
    BRIDGE.auto=Autopilot(BRIDGE)
    from live_socket import start_live_socket
    live_server=start_live_socket(BRIDGE.live,TOKEN,BRIDGE.auto)
    from phone_observer import start_observer
    BRIDGE.observer=start_observer(BRIDGE)
    server=ThreadingHTTPServer(("127.0.0.1",8765),Handler)
    print("Shopee HTML companion: http://127.0.0.1:8765",flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        BRIDGE.closed=True
        BRIDGE.auto.stop(wait=True)
        BRIDGE.live.stop()
        live_server.shutdown()
        server.server_close()
if __name__=="__main__": main()
