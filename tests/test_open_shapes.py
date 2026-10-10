import cv2
import numpy as np
import pytest
from engine.game_state import GameState,Piece
from vision.board_detector import Rect
from vision.piece_detector import detect_tray_piece
from solver.stochastic import ShapePrior,StochasticSolver
from engine.simulator import apply_move


@pytest.mark.parametrize('pitch',[24,32,40])
@pytest.mark.parametrize('cells',[
    tuple((r,0) for r in range(8)),
    tuple((0,c) for c in range(8)),
    tuple((r,r) for r in range(7)),
    ((0,0),(0,1),(0,2),(1,0),(2,0),(2,2),(3,2),(4,2)),
])
def test_unlisted_shapes_at_smaller_scales(pitch,cells):
    frame=np.zeros((340,340,3),np.uint8)
    for r,c in cells:
        frame[10+r*pitch:10+(r+1)*pitch-1,10+c*pitch:10+(c+1)*pitch-1]=(0,160,250)
    piece,scale=detect_tray_piece(frame,Rect(0,0,340,340),'X')
    assert piece.cells==tuple(sorted(cells))
    assert scale==pitch


def test_shape_too_large_for_board_is_rejected():
    frame=np.zeros((340,340,3),np.uint8)
    for r in range(9):frame[10+r*24:10+(r+1)*24-1,10:33]=(0,160,250)
    with pytest.raises(ValueError):detect_tray_piece(frame,Rect(0,0,340,340),'X')


def test_new_shape_enters_forecasts_before_next_refill_without_fake_counts():
    cells=tuple((0,c) for c in range(8))
    prior=ShapePrior();prior.counts.pop(cells,None);prior._rebuild()
    assert cells not in prior.shapes
    state=GameState(8,0,(Piece('X',cells),))
    solver=StochasticSolver(prior=prior,time_limit=1,samples=1)
    result=solver.solve(state)
    assert cells in prior.shapes and prior.counts[cells]==0 and prior.batches==0
    assert result.plans
    assert not apply_move(state,result.plans[0].moves[0]).state.pieces
    version=prior.version
    solver.solve(state)
    assert prior.version==version
