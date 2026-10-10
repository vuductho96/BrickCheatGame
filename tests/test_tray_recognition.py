"""Regression for the real five-cell bar which stopped local Auto."""
from pathlib import Path
import cv2
import numpy as np
import pytest
from web_bridge import PhoneBridge, SLOTS, PITCH
from vision.board_detector import Rect
from vision.piece_detector import detect_piece
from engine.simulator import apply_move

ROOT=Path(__file__).resolve().parents[1]
EXPECTED=(((0,1),(1,0),(1,1)),tuple((0,c) for c in range(5)),((0,1),(1,0)))

@pytest.mark.parametrize('quality',[None,78,95])
def test_real_new_tray_is_complete_and_can_be_planned(quality):
    frame=cv2.imread(str(ROOT/'captures/new-piece-five.png'))
    assert frame is not None
    if quality is not None:
        _,encoded=cv2.imencode('.jpg',cv2.resize(frame,(540,1170)),[cv2.IMWRITE_JPEG_QUALITY,quality])
        frame=cv2.resize(cv2.imdecode(encoded,1),(1080,2340),interpolation=cv2.INTER_NEAREST)
    bridge=PhoneBridge()
    parsed=bridge.parse(frame)
    assert parsed['phase']=='playing'
    assert tuple(p.cells for p in parsed['state'].pieces)==EXPECTED
    result=bridge.solver.solve(parsed['state'])
    assert result.plans
    state=parsed['state']
    for move in result.plans[0].moves:
        state=apply_move(state,move).state

@pytest.mark.parametrize('slot',range(3))
@pytest.mark.parametrize('cells',[
    tuple((0,c) for c in range(5)),
    tuple((r,0) for r in range(5)),
    ((0,0),(0,4),(1,1),(1,3),(2,2)),
    ((0,0),(1,1),(2,2)),
])
def test_complete_tray_thirds_accept_wide_and_detached_patterns(slot,cells):
    frame=np.zeros((2340,1080,3),dtype=np.uint8)
    x,y,w,h=SLOTS[slot]
    width=(max(c for r,c in cells)+1)*PITCH
    height=(max(r for r,c in cells)+1)*PITCH
    x0=x+(w-width)//2; y0=y+(h-height)//2
    for r,c in cells:
        frame[y0+r*PITCH:y0+(r+1)*PITCH-1,x0+c*PITCH:x0+(c+1)*PITCH-1]=(0,160,250)
    assert detect_piece(frame,Rect(*SLOTS[slot]),'A',PITCH,min_value=100).cells==tuple(sorted(cells))

def test_a_clipped_bar_is_rejected_even_if_remaining_width_fits_a_grid():
    frame=np.zeros((100,200,3),dtype=np.uint8)
    frame[20:78,0:116]=(0,160,250)
    with pytest.raises(ValueError,match='cắt mất'):
        detect_piece(frame,Rect(0,0,200,100),'B',58)


@pytest.mark.parametrize('quality',[None,78,95])
def test_real_vertical_bars_overlapping_tray_border(quality):
    frame=cv2.imread(str(ROOT/'captures/new-piece-vertical-five.png'))
    assert frame is not None
    if quality is not None:
        _,encoded=cv2.imencode('.jpg',cv2.resize(frame,(540,1170)),[cv2.IMWRITE_JPEG_QUALITY,quality])
        frame=cv2.resize(cv2.imdecode(encoded,1),(1080,2340),interpolation=cv2.INTER_NEAREST)
    parsed=PhoneBridge().parse(frame)
    expected=(tuple((r,0) for r in range(5)),tuple((0,c) for c in range(3)),tuple((r,0) for r in range(5)))
    assert tuple(p.cells for p in parsed['state'].pieces)==expected
    for descriptor in parsed['pieces']:
        x,y,w,h=descriptor['bounds']
        assert w<300 and h<300  # Border must not become a giant piece.
    bridge=PhoneBridge()
    result=bridge.solver.solve(parsed['state'])
    assert result.plans
    state=parsed['state']
    for move in result.plans[0].moves:
        state=apply_move(state,move).state
