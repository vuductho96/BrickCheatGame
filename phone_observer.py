"""Publish stable phone observations independently of the input/search loop."""
import threading
import time
from capture.frame_stabilizer import FrameStabilizer

def start_observer(bridge):
    def observe():
        stable=FrameStabilizer(required=3)
        from web_bridge import BOARD,SLOTS
        regions=(BOARD.tuple(),*SLOTS)
        while not bridge.closed:
            try:
                auto=bridge.auto
                moving=auto and auto.active and auto.stage in ("moving","settling")
                recent=bridge.live and time.monotonic()-bridge.live.touch_at<.45
                if not bridge.live or not bridge.live.status()["live"] or bridge.live.pressed or moving or recent:
                    stable.reset()
                    time.sleep(.12)
                    continue
                frame=bridge.snapshot()
                if stable.update(frame,regions):
                    parsed=bridge.parse(frame)
                    bridge.publish(parsed)
            except Exception as exc:
                bridge.observation_error=str(exc)
            time.sleep(.12)
    thread=threading.Thread(target=observe,daemon=True)
    thread.start()
    return thread
