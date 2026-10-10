"""Local persistent video/control transport: no HTTP request queue for mouse moves."""
import json
import threading
from urllib.parse import urlparse, parse_qs
from websockets.sync.server import serve

def start_live_socket(mirror, token, auto=None):
    def handler(ws):
        parsed=urlparse(ws.request.path)
        if parse_qs(parsed.query).get("token") != [token]:
            ws.close(1008,"Invalid local session")
            return
        if parsed.path=="/control":
            owns_touch=False
            try:
                for message in ws:
                    data=json.loads(message)
                    action=data.get("action")
                    if action!=0 and not owns_touch: continue
                    if action==0 and auto and auto.active:
                        auto.stop("Đã dừng Auto để thao tác tay",wait=True)
                        if auto.active:raise RuntimeError("Auto đang dừng; kéo lại sau một chút")
                    mirror.touch(action,data.get("x"),data.get("y"))
                    owns_touch=action in (0,2)
                    ws.send(json.dumps({"ok":True}))
            except Exception as exc:
                try:ws.send(json.dumps({"error":str(exc)}))
                except Exception:pass
            finally:
                if owns_touch and mirror.pressed:
                    try:mirror.touch(1,*mirror.touch_position)
                    except Exception:pass
        elif parsed.path=="/video":
            previous=-1
            try:
                while not mirror.closed:
                    with mirror.condition:
                        mirror.condition.wait_for(lambda:mirror.sequence!=previous or mirror.closed,timeout=2)
                        sequence,jpeg=mirror.sequence,mirror.jpeg
                        healthy=mirror.error is None
                    unchanged=sequence==previous
                    previous=sequence
                    if not healthy or not jpeg or unchanged:continue
                    ws.send(jpeg)
            except Exception:pass
        else:ws.close(1008,"Unknown channel")
    server=serve(handler,"127.0.0.1",8766,origins=["http://127.0.0.1:8765","http://localhost:8765"],
        compression=None,max_size=4096,max_queue=16,ping_interval=10,ping_timeout=10)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    return server
