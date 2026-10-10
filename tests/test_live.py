import struct
from unittest.mock import Mock
import numpy as np
import pytest
from live_mirror import LiveMirror
from web_bridge import PhoneBridge

def ready():
    mirror=LiveMirror(Mock())
    mirror.frame=np.zeros((2340,1080,3),dtype=np.uint8)
    mirror.error=None
    mirror.control=Mock()
    return mirror

def test_touch_stream_preserves_down_move_up_and_original_resolution():
    mirror=ready()
    for action,x,y in [(0,176,1772),(2,176,1300),(1,176,1100)]:
        mirror.touch(action,x,y)
    messages=[struct.unpack(">BBQiiHHHII",c.args[0]) for c in mirror.control.sendall.call_args_list]
    assert [m[1] for m in messages]==[0,2,1]
    assert all(m[0]==2 and m[2]==0xfffffffffffffffe and m[5:7]==(1080,2340) for m in messages)
    assert messages[-1][7]==0
    assert not mirror.pressed

def test_out_of_bounds_and_move_without_down_never_send_input():
    mirror=ready()
    mirror.touch(2,100,100)
    with pytest.raises(ValueError):mirror.touch(0,1080,100)
    mirror.control.sendall.assert_not_called()

def test_offline_frame_cannot_enable_touch():
    mirror=ready()
    mirror.error="offline"
    with pytest.raises(RuntimeError):mirror.touch(0,100,100)
    mirror.control.sendall.assert_not_called()
    assert not mirror.status()["live"]

def test_static_video_is_valid_until_transport_disconnects():
    mirror=ready()
    mirror.updated=0
    assert mirror.status()["live"]
    assert mirror.screenshot().shape==(2340,1080,3)

def test_solver_reads_decoded_video_without_adb_screenshot():
    bridge=PhoneBridge()
    bridge.live=ready()
    bridge.adb.screenshot=Mock(side_effect=AssertionError("Must not use screencap"))
    assert bridge.snapshot().shape==(2340,1080,3)
    bridge.adb.screenshot.assert_not_called()
