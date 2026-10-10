import numpy as np
import cv2
import pytest
import threading
from unittest.mock import Mock
from drag_servo import DragServo
from autopilot import Autopilot,MODES,PlacementRetry,AutoStopped,grip_cell
from engine.game_state import GameState,Piece
from engine.simulator import Move,apply_move
from web_bridge import BOARD
from vision.piece_tracker import track_pattern

def test_servo_converges_over_1000_unknown_offsets_and_responses():
    rng=np.random.default_rng(812)
    for _ in range(1000):
        target=rng.uniform([100,400],[800,1300])
        matrix=np.diag(rng.uniform(.55,1.65,2))
        matrix[0,1]=rng.uniform(-.18,.18)
        matrix[1,0]=rng.uniform(-.18,.18)
        pointer=target+rng.uniform(-300,300,2)
        offset=rng.uniform(-350,350,2)
        servo=DragServo(target,(124,124))
        for i in range(14):
            visual=matrix@pointer+offset
            delta=servo.observe(pointer,visual,1.)
            if servo.ready_without_ghost:break
            pointer+=delta
            if np.linalg.norm(delta)<2:pointer+=np.array([6,4])
        assert servo.ready_without_ghost
        assert np.max(np.abs(visual-target))<15

@pytest.mark.parametrize("seed",range(30))
@pytest.mark.parametrize("decorated",[False,True])
def test_tracker_accepts_arbitrary_shapes_and_ignores_unchanged_same_color(seed,decorated):
    rng=np.random.default_rng(seed)
    rows,cols=int(rng.integers(1,6)),int(rng.integers(1,6))
    cells={(int(rng.integers(rows)),int(rng.integers(cols))) for _ in range(rows*cols)}
    cells|={(0,0),(rows-1,cols-1)}
    width,height=cols*24,rows*24
    baseline=np.zeros((330,330,3),np.uint8)
    # Identical static distractor, with a better distance to the search target.
    for r,c in cells:baseline[10+r*24:33+r*24,10+c*24:33+c*24]=(20,100,230)
    frame=baseline.copy()
    for r,c in cells:frame[160+r*24:183+r*24,160+c*24:183+c*24]=(20,100,230)
    if decorated:
        for r,c in cells:frame[167+r*24:177+r*24,167+c*24:177+c*24]=(20,230,30)
    point,confidence=track_pattern(frame,"#e66414",tuple(cells),width,height,baseline,(10,10))
    assert max(abs(point[0]-160),abs(point[1]-160))<5
    assert confidence>.9

SHAPES=[
 ((0,0),),
 tuple((r,c) for r in range(2) for c in range(3)),
 ((0,0),(0,1),(0,2),(1,2),(2,2)),
 ((0,1),(1,0),(1,1),(1,2)),
 ((0,0),(1,1),(2,2)),
 ((0,0),(1,0),(1,1),(2,1)),
]
SHAPES.append(tuple((r,c) for r in range(3) for c in range(3)))
@pytest.mark.parametrize("cells",SHAPES)
@pytest.mark.parametrize("gain",[(1.,1.),(.70,1.35)])
@pytest.mark.parametrize("show_preview",[True,False])
def test_complete_fake_phone_drag_requires_exact_game_preview(cells,gain,show_preview):
    cw,ch=BOARD.width/8,BOARD.height/8
    p=Piece("A",cells)
    move=Move("A",1,2)
    state=GameState(8,0,(p,))
    source_bounds=[100,1720,p.width*32,p.height*32]
    descriptor={"id":"A","width":p.width,"height":p.height,"cells":p.cells,
                "bounds":source_bounds,"color":"#e66414"}
    before={"phase":"playing","state":state,"state_id":"before","pieces":[descriptor]}
    after={"phase":"waiting_for_pieces","state":apply_move(state,move).state,
           "state_id":"after","pieces":[]}
    base=np.zeros((2340,1080,3),np.uint8)
    base[BOARD.y:BOARD.y+BOARD.height,BOARD.x:BOARD.x+BOARD.width]=(56,61,8)
    for r,c in p.cells:
        cv2.rectangle(base,(100+c*32,1720+r*32),(100+c*32+30,1720+r*32+30),(20,100,230),-1)
    bridge=Mock();bridge.lock=threading.Lock()
    live=bridge.live
    live.pressed=False;live.sequence=0;live.touch_position=(0,0)
    live.status.return_value={"live":True,"width":1080,"height":2340}
    desired=np.array([BOARD.x+move.col*cw,BOARD.y+move.row*ch])
    matrix=np.diag(gain)
    gr,gc=grip_cell(p.cells)
    first_pointer=desired+np.array([gc*cw+60,gr*ch+360])
    offset=desired+np.array([170,-90])-matrix@first_pointer
    dropped=[False];pointer=[first_pointer.copy()]
    def touch(action,x,y):
        pointer[0]=np.array([x,y],float)
        live.touch_position=(x,y);live.pressed=action in (0,2);live.sequence+=1
        if action==1:
            if not show_preview:
                assert y>1600, "UP on board without a game preview"
                return
            assert np.max(np.abs(matrix@pointer[0]+offset-desired)/[cw,ch])<.12
            dropped[0]=True
    live.touch.side_effect=touch
    def snapshot():
        f=base.copy()
        if live.pressed:
            origin=matrix@pointer[0]+offset
            for r,c in p.cells:
                x,y=round(origin[0]+c*cw),round(origin[1]+r*ch)
                cv2.rectangle(f,(x,y),(x+round(cw)-3,y+round(ch)-3),(20,100,230),-1)
            if show_preview and np.max(np.abs(origin-desired)/[cw,ch])<.12:
                # The simulated game, not the colored sprite, establishes the target.
                x,y=round(desired[0]),round(desired[1])
                cv2.rectangle(f,(x,y),(x+round(p.width*cw)-2,y+round(p.height*ch)-2),
                              (160,170,160),7)
        return f
    bridge.snapshot.side_effect=snapshot
    bridge.capture_stable.side_effect=snapshot
    bridge.parse.side_effect=lambda frame:after if dropped[0] else before
    auto=Autopilot(bridge)
    # Simulate a static surface: frames advance only after a touch event.
    # Confirmation must request fresh evidence instead of waiting forever.
    auto.wait=lambda _:auto.check()
    def move_pointer(source,target,seconds):auto.touch(2,*target)
    auto.move_pointer=move_pointer
    if show_preview:
        auto.perform_move(before,move,MODES["fast"])
        assert dropped[0] and auto.last_verified and auto.moves==1
    else:
        with pytest.raises(PlacementRetry):auto.perform_move(before,move,MODES["fast"])
        assert not dropped[0] and not live.pressed and auto.moves==0

def test_frozen_feedback_is_cancelable_and_never_released_as_confirmed():
    bridge=Mock();bridge.live.sequence=7
    auto=Autopilot(bridge)
    waits=[]
    def wait(seconds):
        waits.append(seconds)
        auto.cancel.set()
        auto.check()
    auto.wait=wait
    with pytest.raises(AutoStopped):auto.feedback_snapshot(7)
    bridge.snapshot.assert_not_called()
    bridge.live.touch.assert_not_called()



def test_level16_gem_piece_is_localized_from_cell_rims():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    frame=cv2.imread(str(root/"captures"/"level16-servo-reference.png"))
    point,confidence=track_pattern(frame,"#e66414",SHAPES[2],
        round(BOARD.width*3/8),round(BOARD.height*3/8),target=(540,640))
    assert abs(point[0]-663)<=3 and abs(point[1]-793)<=3
    assert confidence>.95

def test_live_decoder_error_keeps_auto_armed_until_video_returns():
    bridge=Mock();bridge.lock=threading.Lock()
    bridge.live.pressed=False
    bridge.live.status.return_value={"live":False}
    state=GameState(3,0,(Piece("A",((0,0),)),))
    bridge.parse.return_value={"phase":"playing","state":state,"state_id":"same","pieces":[{"id":"A"}]}
    auto=Autopilot(bridge);auto.mode="fast"
    attempts=[]
    def execute(*args):
        attempts.append(1)
        if len(attempts)==1:raise RuntimeError("Decoder temporarily disconnected")
        auto.cancel.set()
    auto.perform_move=execute
    recoveries=[]
    def wait(seconds):
        if "video" in auto.message:
            recoveries.append(auto.message)
            bridge.live.status.return_value={"live":True}
        auto.check()
    auto.wait=wait
    auto.run()
    assert len(attempts)==2 and recoveries


@pytest.mark.parametrize("over",[False,True])
def test_wrong_actual_cell_is_fatal_and_not_counted_as_success(monkeypatch,over):
    import autopilot
    from types import SimpleNamespace
    from autopilot import PlacementMismatch
    counter=[0]
    def tick():
        counter[0]+=1
        return counter[0]
    monkeypatch.setattr(autopilot,"time",SimpleNamespace(monotonic=tick,sleep=lambda _:None))
    state=GameState(8,0,(Piece("A",((0,0),)),))
    piece={"id":"A","width":1,"height":1,"cells":[[0,0]],"bounds":[100,1720,58,58],"color":"#e66414"}
    before={"phase":"playing","state":state,"state_id":"before","pieces":[piece]}
    actual={"phase":"waiting_for_pieces","state":GameState(8,1<<10,()),"state_id":"wrong","pieces":[]}
    if over:actual={"phase":"game_over","state":None,"pieces":[]}
    frame=np.zeros((2340,1080,3),np.uint8)
    held=frame.copy()
    cw,ch=BOARD.width/8,BOARD.height/8
    x,y=round(BOARD.x+cw),round(BOARD.y+ch)
    cv2.rectangle(held,(x,y),(x+round(cw)-2,y+round(ch)-2),(160,170,160),7)
    held[y+8:y+round(ch)-10,x+8:x+round(cw)-10]=(20,100,230)
    bridge=Mock();bridge.live.pressed=False
    bridge.live.status.return_value={"live":True,"width":1080,"height":2340}
    bridge.snapshot.side_effect=[frame,held,held]
    parsed=[0]
    def parse(_):
        parsed[0]+=1
        return before if parsed[0]==1 else actual
    bridge.parse.side_effect=parse
    mirror=bridge.live;mirror.touch_position=(0,0)
    def touch(action,x,y):
        mirror.pressed=action in (0,2);mirror.touch_position=(x,y)
    mirror.touch.side_effect=touch
    auto=Autopilot(bridge);auto.wait=lambda _:None
    auto.move_pointer=lambda source,target,seconds:auto.touch(2,*target)
    with pytest.raises(PlacementMismatch):
        auto.perform_move(before,Move("A",1,1),MODES["fast"])
    assert auto.moves==0 and not auto.last_verified
    if not over:assert "Thả lệch" in auto.message


def test_move_history_records_intent_and_actual_without_phone_input(tmp_path,monkeypatch):
    import autopilot,json
    from web_bridge import PhoneBridge
    (tmp_path/"artifacts").mkdir()
    monkeypatch.setattr(autopilot,"__file__",str(tmp_path/"autopilot.py"))
    bridge=PhoneBridge()
    auto=Autopilot(bridge)
    state=GameState(8,0,(Piece("A",((0,0),)),))
    move=Move("A",1,1)
    expected=apply_move(state,move).state
    actual={"phase":"waiting_for_pieces","state":GameState(8,1<<10,())}
    auto.record_move("planned",{"state":state,"state_id":"before","pieces":[]},move,expected)
    auto.record_move("mismatch",{"state":state},move,expected,actual)
    lines=(tmp_path/"artifacts"/"auto-moves.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines)==2
    entries=[json.loads(line) for line in lines]
    assert entries[0]["move"]=={"piece_id":"A","row":1,"col":1}
    assert entries[1]["expected"]["board"]!=entries[1]["actual"]["board"]


def test_grip_uses_center_when_occupied_and_real_cell_for_shapes_with_holes():
    assert grip_cell(tuple((r,c) for r in range(3) for c in range(3)))==(1,1)
    assert tuple(grip_cell(((0,0),(0,1),(0,2),(1,2),(2,2)))) in ((0,0),(0,1),(0,2),(1,2),(2,2))
    assert grip_cell(((0,0),(1,1),(2,2)))==(1,1)


def test_target_lock_survives_a_different_solver_result_on_retry():
    from solver.beam_search import BeamSolver
    from dataclasses import replace
    state=GameState(3,0,(Piece("A",((0,0),)),))
    result=BeamSolver(width=60,time_limit=.2).solve(state)
    alternate=replace(result,plans=tuple(reversed(result.plans)))
    bridge=Mock();bridge.lock=threading.Lock();bridge.live.pressed=False
    bridge.parse.return_value={"phase":"playing","state":state,"state_id":"fixed","pieces":[{"id":"A"}]}
    auto=Autopilot(bridge);auto.mode="fast"
    auto.solvers["fast"]=Mock(solve=Mock(side_effect=[result,alternate,alternate]))
    targets=[]
    def perform(*args):
        assert auto.result.plans[0].moves[0]==result.plans[0].moves[0]
        targets.append(args[1])
        if len(targets)==1:raise PlacementRetry("retry")
        auto.cancel.set()
    auto.perform_move=perform
    auto.wait=lambda _:auto.check()
    auto.run()
    assert len(targets)==2 and targets[0]==targets[1]==result.plans[0].moves[0]
