import numpy as np
import pytest
from vision.board_detector import Rect
from vision.cell_classifier import classify_cells
from vision.piece_detector import detect_piece
from capture.frame_stabilizer import FrameStabilizer

def test_calibrated_board_on_synthetic_image():
    frame=np.full((160,160,3),(52,40,35),dtype=np.uint8)
    for r,c in ((0,1),(2,3),(3,0)):
        frame[r*40:(r+1)*40,c*40:(c+1)*40]=(0,130,230)
    result=classify_cells(frame,Rect(0,0,160,160),4,(35,40,52))
    assert result.board==sum(1 << (r*4+c) for r,c in ((0,1),(2,3),(3,0)))
    assert not result.ambiguous

@pytest.mark.parametrize("cells",[((0,0),),((0,0),(0,1),(1,1)),((0,0),(1,0),(2,0)),((0,0),(0,1),(1,0),(1,1))])
def test_piece_shape_on_synthetic_slots(cells):
    frame=np.zeros((120,120,3),dtype=np.uint8)
    for r,c in cells: frame[10+r*24:10+(r+1)*24,10+c*24:10+(c+1)*24]=(0,160,250)
    piece=detect_piece(frame,Rect(0,0,120,120),"A",24)
    assert piece.cells==tuple(sorted(cells))

def test_blank_missing_piece_and_bad_roi_rejected():
    frame=np.zeros((100,100,3),dtype=np.uint8)
    with pytest.raises(ValueError): detect_piece(frame,Rect(0,0,100,100),"A",24)
    with pytest.raises(ValueError): Rect(80,80,40,40).crop(frame)

def test_stability_resets_after_animation_and_ignores_outside_roi():
    stable=FrameStabilizer(required=3)
    frame=np.zeros((160,160,3),dtype=np.uint8)
    roi=[(0,0,80,80)]
    assert not stable.update(frame,roi)
    assert not stable.update(frame,roi)
    assert stable.update(frame,roi)
    frame[100:,:,:]=255
    assert stable.update(frame,roi)
    frame[0:40,0:40]=255
    assert not stable.update(frame,roi)
    assert not stable.update(frame,roi)
    assert stable.update(frame,roi)

def test_ambiguous_cell_marked():
    frame=np.full((80,80,3),(40,0,0),dtype=np.uint8)
    result=classify_cells(frame,Rect(0,0,80,80),2,(0,0,0),tolerance=40)
    assert len(result.ambiguous)==4
