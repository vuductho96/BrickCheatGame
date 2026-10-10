from unittest.mock import Mock
import threading
import cv2
import numpy as np
import pytest
from pathlib import Path
from autopilot import Autopilot,AutoStopped,MODES,match_dragged_piece
from engine.game_state import GameState,Piece
from engine.simulator import Move,apply_move
from web_bridge import PhoneBridge

ROOT=Path(__file__).resolve().parents[1]

def test_win_reference_is_distinct_from_playing_and_loss():
    bridge=PhoneBridge()
    win=cv2.imread(str(ROOT/"captures"/"shopee-win-reference.png"))
    assert bridge.parse(win)["phase"]=="level_complete"
    # Real live frames pass through JPEG + downscale/upscale.
    small=cv2.resize(win,(540,1170))
    ok,jpeg=cv2.imencode(".jpg",small,[cv2.IMWRITE_JPEG_QUALITY,78])
    decoded=cv2.imdecode(jpeg,1)
    assert bridge.parse(cv2.resize(decoded,(1080,2340),interpolation=cv2.INTER_NEAREST))["phase"]=="level_complete"
    assert bridge.parse(cv2.imread(str(ROOT/"captures"/"trial-current.png")))["phase"]=="playing"
    assert bridge.parse(cv2.imread(str(ROOT/"captures"/"shopee-game-over.png")))["phase"]=="game_over"

def test_modes_change_search_budget_not_only_delay():
    assert MODES["fast"].width<MODES["balanced"].width<MODES["deep"].width
    assert MODES["fast"].budget<MODES["balanced"].budget<MODES["deep"].budget

def test_feedback_finds_piece_and_rejects_unrelated_frame():
    rng=np.random.default_rng(43)
    template=rng.integers(0,256,(80,100,3),dtype=np.uint8)
    frame=np.zeros((600,500,3),dtype=np.uint8)
    frame[280:360,200:300]=template
    position,confidence=match_dragged_piece(frame,template,(190,275))
    assert position==(200,280) and confidence>.99
    with pytest.raises(RuntimeError):
        match_dragged_piece(np.zeros_like(frame),template,(190,275))

def stub_bridge():
    bridge=Mock()
    bridge.lock=threading.Lock()
    bridge.live.pressed=False
    bridge.live.status.return_value={"live":True,"width":540,"height":1170}
    return bridge

def test_stop_is_checked_before_any_input():
    bridge=stub_bridge()
    auto=Autopilot(bridge)
    auto.cancel.set()
    with pytest.raises(AutoStopped):auto.touch(0,500,1000)
    bridge.live.touch.assert_not_called()

def test_refill_replans_only_after_observed_new_three_piece_tray():
    bridge=stub_bridge()
    pieces=tuple(Piece(chr(65+i),((0,0),)) for i in range(3))
    state=GameState(8,0,pieces)
    after1=apply_move(state,Move("A",0,0)).state
    after2=apply_move(after1,Move("B",0,1)).state
    after3=apply_move(after2,Move("C",0,2)).state
    fresh=GameState(8,after3.board,(Piece("A",((0,0),(1,0))),Piece("B",((0,0),(0,1))),Piece("C",((0,0),))))
    observed=iter([state,after1,after2,fresh])
    bridge.capture_stable.return_value=np.zeros((1,1,3),dtype=np.uint8)
    def parse(_):
        s=next(observed)
        return {"phase":"playing","state":s,"state_id":str(s.board),"pieces":[{"id":p.id} for p in s.pieces]}
    bridge.parse.side_effect=parse
    auto=Autopilot(bridge);auto.mode="fast"
    calls=[]
    real=auto.solvers["fast"]
    def solve(s):
        calls.append(s)
        return real.solve(s)
    auto.solvers["fast"]=Mock(solve=solve)
    def execute(obs,move,profile):
        if len(calls)==4:auto.cancel.set()
    auto.perform_move=execute
    auto.wait=lambda _:auto.check()
    auto.run()
    assert [len(s.pieces) for s in calls]==[3,2,1,3]
    assert calls[-1].pieces==fresh.pieces
    assert all(len(s.pieces)<=3 for s in calls)

def test_loss_stops_without_restart_tap():
    bridge=stub_bridge()
    bridge.parse.return_value={"phase":"game_over"}
    auto=Autopilot(bridge);auto.run()
    bridge.live.touch.assert_not_called()
    assert not auto.active and "thua" in auto.message


def test_confirmed_tray_with_no_legal_moves_stops_without_waiting_for_overlay():
    bridge=stub_bridge()
    state=GameState(8,(1<<64)-1,(Piece('A',((0,0),)),))
    bridge.parse.return_value={'phase':'playing','state':state,'state_id':'blocked',
                              'pieces':[{'id':'A'}]}
    auto=Autopilot(bridge);auto.run()
    bridge.live.touch.assert_not_called()
    assert not auto.active and 'Không còn vị trí hợp lệ' in auto.message

def test_decorated_occupied_cell_is_not_mistaken_for_animation():
    from vision.cell_classifier import classify_cells
    from vision.board_detector import Rect
    frame=np.full((160,160,3),(56,61,8),dtype=np.uint8)
    frame[0:80,0:80]=(20,100,230)
    frame[28:52,28:52]=(10,220,240)
    result=classify_cells(frame,Rect(0,0,160,160),2,(8,61,56),tolerance=48,margin=5)
    assert result.board==1 and not result.ambiguous

def test_color_tracking_ignores_same_colored_existing_board_cells():
    baseline=np.zeros((600,600,3),dtype=np.uint8)
    baseline[190:310,70:190]=(20,100,230)
    frame=baseline.copy()
    frame[200:320,200:320]=(20,100,230)
    template=np.full((120,120,3),(10,170,240),dtype=np.uint8)
    cells=[[r,c] for r in range(3) for c in range(3)]
    position,confidence=match_dragged_piece(frame,template,(200,200),color="#e66414",cells=cells,baseline=baseline)
    assert position==(200,200) and confidence>=.99

def test_win_popup_is_clicked_once_while_transition_is_pending():
    bridge=stub_bridge()
    state=GameState(8,0,(Piece("A",((0,0),)),))
    phases=iter([{"phase":"level_complete"},{"phase":"level_complete"},
        {"phase":"playing","state":state,"state_id":"new","pieces":[{"id":"A"}]}])
    bridge.parse.side_effect=lambda _:next(phases)
    auto=Autopilot(bridge)
    touches=[]
    auto.touch=lambda action,x,y:touches.append((action,x,y))
    auto.release=lambda **kw:None
    auto.perform_move=lambda *args:auto.cancel.set()
    auto.wait=lambda _:auto.check()
    auto.run()
    assert touches==[(0,540,1880)]
    assert auto.levels==1 and not auto.active

def test_phone_screenshot_ghost_is_one_row_above_the_old_suggestion():
    from vision.drop_preview import drop_preview
    from web_bridge import BOARD
    frame=cv2.imread(str(ROOT/"captures"/"misaligned-preview.png"))
    piece={"width":2,"height":3,"cells":[[r,c] for r in range(3) for c in range(2)]}
    preview=drop_preview(frame,BOARD,piece)
    assert (preview["row"],preview["col"])==(4,0)
    assert preview["confidence"]>.98

def test_preview_grid_location_changes_by_exact_cell_not_sprite_offset():
    from vision.drop_preview import drop_preview
    from vision.board_detector import Rect
    board=Rect(0,0,800,800)
    frame=np.full((800,800,3),(56,61,8),dtype=np.uint8)
    cv2.rectangle(frame,(0,500),(198,798),(160,170,160),thickness=7)
    # Lifted sprite displaced left/up; it must not determine the drop cell.
    cv2.rectangle(frame,(0,450),(155,745),(20,100,230),thickness=-1)
    preview=drop_preview(frame,board,{"width":2,"height":3})
    assert (preview["row"],preview["col"])==(5,0)

def test_active_auto_does_not_serve_frozen_old_board_without_fresh_observation():
    import time
    from web_bridge import BridgeError
    bridge=PhoneBridge()
    bridge.live=Mock()
    bridge.live.status.return_value={"live":True}
    bridge.live.pressed=False
    bridge.live.touch_at=0
    bridge.observer=object()
    state=bridge.parse(cv2.imread(str(ROOT/"captures"/"trial-current.png")))
    state["observed_at"]=time.time()-10
    bridge.current=state
    bridge.auto=Autopilot(bridge)
    bridge.auto.active=True
    with pytest.raises(BridgeError):bridge.refresh()

def test_moving_state_cannot_publish_old_move_plans_as_current_hints():
    bridge=PhoneBridge()
    bridge.auto=Autopilot(bridge)
    bridge.auto.active=True
    bridge.auto.stage="moving"
    bridge.auto.pending_move={"piece_id":"A","row":5,"col":0}
    observed=bridge.parse(cv2.imread(str(ROOT/"captures"/"trial-current.png")))
    data=bridge.serialize(observed)
    assert data["sync"]=="moving" and data["plans"]==[]
    assert data["pending_move"]["row"]==5

def test_autopilot_corrects_snapped_ghost_then_verifies_without_phone():
    from autopilot import MODES
    from web_bridge import BOARD
    frame=np.zeros((2340,1080,3),dtype=np.uint8)
    state=GameState(8,(1<<(6*8+2))|(1<<(7*8+2)),(Piece("A",tuple((r,c) for r in range(3) for c in range(2))),))
    piece={"id":"A","width":2,"height":3,"cells":[[r,c] for r in range(3) for c in range(2)],
           "bounds":[148,1720,114,168],"color":"#e66414"}
    observed={"state":state,"state_id":"before","phase":"playing","pieces":[piece]}
    move=Move("A",5,0)
    after_state=apply_move(state,move).state
    after={"state":after_state,"state_id":"after","phase":"waiting_for_pieces","pieces":[]}
    def ghost(row):
        f=frame.copy()
        x=BOARD.x;y=round(BOARD.y+row*BOARD.height/8)
        # Render a full-size lifted shape. The old inset sprite extended eight
        # pixels below the board at row 5 despite claiming a valid footprint.
        f[y:y+round(3*BOARD.height/8),x:x+round(2*BOARD.width/8)]=(20,100,230)
        cv2.rectangle(f,(x-2,y-2),(x+249,y+373),(160,170,160),thickness=2)
        return f
    bridge=stub_bridge()
    bridge.parse.side_effect=[observed,after]
    bridge.snapshot.side_effect=[frame,ghost(4),ghost(5),ghost(5)]
    bridge.capture_stable.return_value=frame
    mirror=bridge.live
    mirror.touch_position=(0,0)
    def touch(action,x,y):
        mirror.pressed=action in (0,2)
        mirror.touch_position=(x,y)
    mirror.touch.side_effect=touch
    auto=Autopilot(bridge)
    auto.wait=lambda _:None
    paths=[]
    auto.move_pointer=lambda source,target,seconds:paths.append((source,target))
    auto.perform_move(observed,move,MODES["fast"])
    assert len(paths)==2
    # The servo limits a correction to the remaining edge clearance / 2.5;
    # it must not blindly command a full cell near the bottom of the board.
    correction=paths[1][1][1]-paths[1][0][1]
    assert 0<correction<=BOARD.height/8/2.5+.01
    assert auto.moves==1 and auto.last_verified
    assert not mirror.pressed

def test_temporary_placement_failure_retries_same_target_without_switching_off():
    from autopilot import PlacementRetry
    bridge=stub_bridge()
    state=GameState(3,0,(Piece("A",((0,0),)),))
    observed={"phase":"playing","state":state,"state_id":"same","pieces":[{"id":"A"}]}
    bridge.parse.return_value=observed
    auto=Autopilot(bridge);auto.mode="fast"
    choices=[]
    def execute(obs,move,profile):
        choices.append(move)
        if len(choices)==1:raise PlacementRetry("retry")
        auto.cancel.set()
    auto.perform_move=execute
    auto.wait=lambda _:auto.check()
    auto.run()
    assert len(choices)==2 and choices[0]==choices[1]

def test_clear_effect_fallback_requires_every_expected_line_to_be_lit():
    from vision.drop_preview import clear_preview
    from vision.board_detector import Rect
    rect=Rect(0,0,800,800)
    frame=np.full((800,800,3),(56,61,8),dtype=np.uint8)
    frame[400:500]=(20,100,230)
    assert clear_preview(frame,rect,(4,),())
    frame[400:500,700:800]=(56,61,8)
    assert not clear_preview(frame,rect,(4,),())
    assert not clear_preview(frame,rect,(),())

@pytest.mark.parametrize("label,row,col,rows,cols",[
    ("l",2,5,(3,),()),("z",5,4,(5,),(4,5)),
])
def test_real_clear_effects_confirm_partial_ghost_without_sprite_alignment(label,row,col,rows,cols):
    from vision.drop_preview import clear_drop_preview,drop_preview
    from web_bridge import BOARD
    frame=cv2.imread(str(ROOT/"captures"/("stuck-"+label+"-preview.png")))
    piece={"width":2,"height":3}
    assert drop_preview(frame,BOARD,piece) is None
    assert clear_drop_preview(frame,BOARD,piece,row,col,rows,cols)
    assert not clear_drop_preview(frame,BOARD,piece,row-1,col,rows,cols)
    assert not clear_drop_preview(frame,BOARD,piece,row,col+1,rows,cols)
    assert not clear_drop_preview(frame,BOARD,piece,row,col,(),())

@pytest.mark.parametrize("label",["l","z"])
def test_occluded_clear_preview_cannot_release_displaced_sprite(label):
    matrices={
        "l":["11011111","00001100","00000000","11111011","10111001","11110111","01100000","01111000"],
        "z":["11011111","00001100","00001110","00001100","10111101","11110111","01100000","01111000"],
    }
    cells=((0,0),(0,1),(1,0),(2,0)) if label=="l" else ((0,0),(1,0),(1,1),(2,1))
    row,col=(2,5) if label=="l" else (5,4)
    bits=sum(1<<(r*8+c) for r,line in enumerate(matrices[label]) for c,v in enumerate(line) if v=="1")
    state=GameState(8,bits,(Piece("A",cells),))
    piece={"id":"A","width":2,"height":3,"cells":cells,"bounds":[148,1720,114,168],"color":"#e66414"}
    observed={"state":state,"state_id":"before","phase":"playing","pieces":[piece]}
    move=Move("A",row,col)
    after={"state":apply_move(state,move).state,"state_id":"after","phase":"waiting_for_pieces","pieces":[]}
    base=np.zeros((2340,1080,3),dtype=np.uint8)
    held=cv2.imread(str(ROOT/"captures"/("stuck-"+label+"-preview.png")))
    bridge=stub_bridge()
    bridge.parse.side_effect=[observed,after]
    bridge.snapshot.side_effect=[base]+[held]*40
    bridge.capture_stable.return_value=base
    mirror=bridge.live
    mirror.touch_position=(0,0)
    def touch(action,x,y):
        mirror.pressed=action in (0,2)
        mirror.touch_position=(x,y)
    mirror.touch.side_effect=touch
    auto=Autopilot(bridge)
    auto.wait=lambda _:None
    paths=[]
    auto.move_pointer=lambda source,target,seconds:paths.append((source,target))
    from autopilot import PlacementRetry
    with pytest.raises(PlacementRetry):auto.perform_move(observed,move,MODES["fast"])
    assert auto.moves==0 and not auto.last_verified and not mirror.pressed
    assert mirror.touch.call_args_list[-2].args[0]==2
    assert mirror.touch.call_args_list[-2].args[2]>850

def test_failed_alignment_recovers_with_backoff_instead_of_switching_off():
    from autopilot import PlacementRetry
    bridge=stub_bridge()
    state=GameState(3,0,(Piece("A",((0,0),)),))
    bridge.parse.return_value={"phase":"playing","state":state,"state_id":"same","pieces":[{"id":"A"}]}
    auto=Autopilot(bridge);auto.mode="fast"
    calls=[]
    def fail(obs,move,profile):
        calls.append(move)
        raise PlacementRetry("retry")
    auto.perform_move=fail
    waits=[]
    def wait(seconds):
        waits.append(seconds)
        if auto.recoveries:auto.cancel.set()
        auto.check()
    auto.wait=wait
    auto.run()
    assert 1<=len(calls)<=9
    assert auto.recoveries==1 and "tự phục hồi" in auto.message
    assert max(waits)>=3

def test_real_t_ghost_at_bottom_is_found_despite_disconnected_fragments():
    from vision.drop_preview import drop_preview
    from web_bridge import BOARD
    frame=cv2.imread(str(ROOT/"captures"/"stuck-t-preview.png"))
    piece={"width":3,"height":2,"cells":[[0,1],[1,0],[1,1],[1,2]]}
    preview=drop_preview(frame,BOARD,piece)
    assert (preview["row"],preview["col"])==(6,2)
    assert preview["confidence"]>.95
    # The same bounding rectangle does not establish the opposite T orientation.
    assert drop_preview(frame,BOARD,{"width":3,"height":2,"cells":[[0,0],[0,1],[0,2],[1,1]]}) is None

def test_bottom_t_preview_cannot_release_displaced_sprite():
    cells=((0,1),(1,0),(1,1),(1,2))
    matrix=["00010011","01011011","00011011","01011011","11011000","00000000","00001100","01000000"]
    bits=sum(1<<(r*8+c) for r,line in enumerate(matrix) for c,v in enumerate(line) if v=="1")
    state=GameState(8,bits,(Piece("B",cells),))
    piece={"id":"B","width":3,"height":2,"cells":cells,"bounds":[430,1720,170,114],"color":"#78dc0a"}
    observed={"state":state,"state_id":"before","phase":"playing","pieces":[piece]}
    move=Move("B",6,2)
    after={"state":apply_move(state,move).state,"state_id":"after","phase":"waiting_for_pieces","pieces":[]}
    base=np.zeros((2340,1080,3),dtype=np.uint8)
    held=cv2.imread(str(ROOT/"captures"/"stuck-t-preview.png"))
    bridge=stub_bridge()
    bridge.parse.side_effect=[observed,after]
    bridge.snapshot.side_effect=[base]+[held]*40
    bridge.capture_stable.return_value=base
    mirror=bridge.live;mirror.touch_position=(0,0)
    def touch(action,x,y):
        mirror.pressed=action in (0,2)
        mirror.touch_position=(x,y)
    mirror.touch.side_effect=touch
    auto=Autopilot(bridge);auto.wait=lambda _:None
    paths=[]
    auto.move_pointer=lambda source,target,seconds:paths.append((source,target))
    from autopilot import PlacementRetry
    with pytest.raises(PlacementRetry):auto.perform_move(observed,move,MODES["fast"])
    assert auto.moves==0 and not auto.last_verified
    assert not mirror.pressed

@pytest.mark.parametrize("pid,x,width,expected",[
    ("A",20,140,((0,0),(1,0),(2,0),(2,1),(2,2))),
    ("B",180,130,((0,0),(1,1),(2,2))),
    ("C",330,110,((0,0),(1,1),(2,2))),
])
def test_level12_reads_observed_l_and_diagonal_shapes(pid,x,width,expected):
    from vision.piece_detector import detect_piece
    from vision.board_detector import Rect
    frame=cv2.imread(str(ROOT/"captures"/"level12-changing-pieces.png"))
    assert detect_piece(frame,Rect(x,650,width,110),pid,25,min_value=100).cells==expected

def test_diagonal_piece_color_feedback_combines_detached_cells():
    baseline=np.zeros((600,600,3),dtype=np.uint8)
    frame=baseline.copy()
    for r in range(3):
        frame[200+r*40:238+r*40,210+r*40:248+r*40]=(20,100,230)
    template=np.full((120,120,3),(10,170,240),dtype=np.uint8)
    point,score=match_dragged_piece(frame,template,(200,200),color="#e66414",
                                   cells=[[0,0],[1,1],[2,2]],baseline=baseline)
    assert point==(210,200) and score>.9

def test_solver_applies_diagonal_mask_without_filling_its_bounding_rectangle():
    from solver.beam_search import BeamSolver
    diagonal=Piece("B",((0,0),(1,1),(2,2)))
    # Obstacles in the diagonal's bounding box are legal when off its occupied cells.
    state=GameState(3,(1<<1)|(1<<3),(diagonal,))
    result=BeamSolver(width=60,time_limit=.2).solve(state)
    assert result.plans and result.plans[0].moves[0]==Move("B",0,0)
    placed=apply_move(state,result.plans[0].moves[0]).state
    assert placed.board==state.board|(1<<0)|(1<<4)|(1<<8)

def test_real_no_ghost_rectangle_is_tracked_and_moved_to_target_before_release():
    from web_bridge import BOARD
    held=cv2.imread(str(ROOT/"captures"/"no-ghost-rectangle.png"))
    frame=held.copy()
    frame[912:1158,264:637]=(56,61,8)
    # Restore the occupied purple cell that the misplaced lifted sprite covered.
    cw,ch=BOARD.width/8,BOARD.height/8
    frame[round(BOARD.y+3*ch):round(BOARD.y+4*ch),round(BOARD.x+2*cw):round(BOARD.x+3*cw)]=(180,40,110)
    bounds=[100,1720,174,116]
    frame[1720:1836,100:274]=(230,210,20)
    cells=tuple((r,c) for r in range(2) for c in range(3))
    piece={"id":"A","width":3,"height":2,"cells":cells,"bounds":bounds,"color":"#14d2e6"}
    state=GameState(8,1<<(3*8+2),(Piece("A",cells),))
    observed={"state":state,"state_id":"before","phase":"playing","pieces":[piece]}
    move=Move("A",2,3)
    after={"state":apply_move(state,move).state,"state_id":"after","phase":"waiting_for_pieces","pieces":[]}
    ghost=frame.copy()
    cv2.rectangle(ghost,(round(BOARD.x+3*cw),round(BOARD.y+2*ch)),
                  (round(BOARD.x+6*cw)-2,round(BOARD.y+4*ch)-2),(160,170,160),thickness=7)
    ghost[round(BOARD.y+2*ch)+8:round(BOARD.y+4*ch)-10,
          round(BOARD.x+3*cw)+8:round(BOARD.x+6*cw)-10]=(230,210,20)
    bridge=stub_bridge()
    bridge.parse.side_effect=[observed,after]
    bridge.snapshot.side_effect=[frame,held,ghost,ghost]
    bridge.capture_stable.return_value=frame
    mirror=bridge.live;mirror.touch_position=(0,0)
    def touch(action,x,y):
        mirror.pressed=action in (0,2)
        mirror.touch_position=(x,y)
    mirror.touch.side_effect=touch
    auto=Autopilot(bridge);auto.wait=lambda _:None
    paths=[]
    auto.move_pointer=lambda source,target,seconds:paths.append((source,target))
    auto.perform_move(observed,move,MODES["fast"])
    assert len(paths)==2 and auto.last_verified and auto.moves==1
    # Correct the actual observed left/down displacement, without the invented bias.
    assert abs(paths[1][1][0]-paths[1][0][0]-(BOARD.x+3*cw-264))<3
    assert abs(paths[1][1][1]-paths[1][0][1]-(BOARD.y+2*ch-912))<3

def test_matching_never_tracks_unchanged_existing_template_as_dragged_piece():
    rng=np.random.default_rng(42)
    template=rng.integers(0,256,(60,90,3),dtype=np.uint8)
    baseline=np.zeros((400,400,3),dtype=np.uint8)
    baseline[150:210,140:230]=template
    with pytest.raises(RuntimeError):
        match_dragged_piece(baseline.copy(),template,(140,150),baseline=baseline)

def test_missing_ghost_even_with_learned_bias_never_causes_unverified_release():
    from autopilot import PlacementRetry
    from web_bridge import BOARD
    cells=tuple((r,c) for r in range(2) for c in range(3))
    state=GameState(8,0,(Piece("A",cells),))
    piece={"id":"A","width":3,"height":2,"cells":cells,"bounds":[100,1720,174,116],"color":"#14d2e6"}
    observed={"state":state,"state_id":"before","phase":"playing","pieces":[piece]}
    frame=np.zeros((2340,1080,3),dtype=np.uint8)
    frame[1720:1836,100:274]=(230,210,20)
    held=frame.copy()
    cw,ch=BOARD.width/8,BOARD.height/8
    x,y=round(BOARD.x+3*cw),round(BOARD.y+2*ch)
    held[y:y+round(2*ch),x:x+round(3*cw)]=(230,210,20)
    bridge=stub_bridge()
    bridge.parse.return_value=observed
    bridge.snapshot.side_effect=[frame]+[held]*30
    mirror=bridge.live;mirror.touch_position=(0,0)
    touches=[]
    def touch(action,x,y):
        touches.append((action,x,y))
        mirror.pressed=action in (0,2)
        mirror.touch_position=(x,y)
    mirror.touch.side_effect=touch
    auto=Autopilot(bridge);auto.wait=lambda _:None
    auto.sprite_bias[(3,2,0,0)]=(0,0)
    paths=[]
    auto.move_pointer=lambda source,target,seconds:paths.append((source,target))
    with pytest.raises(PlacementRetry):
        auto.perform_move(observed,Move("A",2,3),MODES["fast"])
    assert auto.moves==0 and not auto.last_verified and len(paths)<=15
    # All neighborhood probes remain within a quarter-cell of their common origin.
    for source,target in paths[2:]:
        assert abs(target[0]-source[0])<=cw*1.5+.01
        assert abs(target[1]-source[1])<=ch*1.5+.01
    assert touches[-2][0]==2 and touches[-2][2]>850
    assert touches[-1][0]==1 and not mirror.pressed
