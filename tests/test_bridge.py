from unittest.mock import patch
from dataclasses import replace
import cv2
import pytest
from engine.simulator import Move,apply_move
from web_bridge import PhoneBridge,BridgeError

def fixture():
    from pathlib import Path
    image=cv2.imread(str(Path(__file__).resolve().parents[1]/"captures"/"trial-current.png"))
    if image is None: pytest.skip("Real screenshot fixture not present")
    return image

def test_actual_s23_board_and_three_piece_shapes():
    bridge=PhoneBridge()
    parsed=bridge.parse(fixture())
    assert parsed["phase"]=="playing"
    assert parsed["board"]==[[0,0,0,1,1,0,0,0],[0,1,0,1,1,0,1,0],[1,1,0,1,1,0,1,1],
        [0]*8,[0]*8,[0,0,0,1,1,0,0,0],[0,0,1,0,0,1,0,0],[0]*8]
    assert [(p["width"],p["height"]) for p in parsed["pieces"]]==[(2,2),(3,2),(3,2)]

def test_stale_pc_drag_cannot_send_phone_input():
    bridge=PhoneBridge()
    frame=fixture()
    current=bridge.parse(frame)
    with patch.object(bridge,"ensure_device"),patch.object(bridge.adb,"screenshot",return_value=frame),patch.object(bridge,"save_frame"),patch.object(bridge,"command") as command:
        with pytest.raises(BridgeError,match="đã đổi"):
            bridge.drag({"state_id":"old","piece_id":"A","row":3,"col":0,"grab":[.5,.5]})
        command.assert_not_called()

def test_valid_drag_maps_coordinates_and_verifies_phone_board():
    bridge=PhoneBridge()
    frame=fixture()
    before=bridge.parse(frame)
    step=apply_move(before["state"],Move("A",3,0))
    after=dict(before,state=step.state,state_id="after",board=step.state.matrix(),
               pieces=[p for p in before["pieces"] if p["id"]!="A"])
    with patch.object(bridge,"ensure_device"),patch.object(bridge.adb,"screenshot",return_value=frame),patch.object(bridge,"parse",side_effect=[before,after]),patch.object(bridge,"capture_stable",return_value=frame),patch.object(bridge,"command") as command,patch("web_bridge.time.sleep"):
        result=bridge.drag({"state_id":before["state_id"],"piece_id":"A","row":3,"col":0,"grab":[.5,.5]})
        command.assert_called_once_with("touchscreen","swipe",176,1772,108,1073,750)
        assert result["receipt"]["verified"]

def test_invalid_drop_cannot_send_phone_input():
    bridge=PhoneBridge()
    frame=fixture()
    before=bridge.parse(frame)
    with patch.object(bridge,"ensure_device"),patch.object(bridge.adb,"screenshot",return_value=frame),patch.object(bridge,"command") as command:
        with pytest.raises(ValueError):
            bridge.drag({"state_id":before["state_id"],"piece_id":"A","row":0,"col":3,"grab":[.5,.5]})
        command.assert_not_called()

def test_game_over_popup_and_resolution_change():
    from pathlib import Path
    bridge=PhoneBridge()
    over=cv2.imread(str(Path(__file__).resolve().parents[1]/"captures"/"shopee-game-over.png"))
    assert bridge.parse(over)["phase"]=="game_over"
    with pytest.raises(BridgeError): bridge.parse(fixture()[::2,::2])
