from pathlib import Path
import cv2
import numpy as np
from autopilot import clear_effect_baseline,match_dragged_piece
from web_bridge import BOARD,PhoneBridge


def test_real_yellow_s_remains_trackable_during_clear_without_hiding_empty_cells():
    root=Path(__file__).resolve().parents[1]/'captures'
    before=cv2.imread(str(root/'auto-yellow-s-before.png'))
    held=cv2.imread(str(root/'auto-yellow-s-clear.png'))
    parsed=PhoneBridge().parse(before)
    piece=parsed['pieces'][0]
    baseline=clear_effect_baseline(before,held,parsed['state'],(4,),(),BOARD)
    cw,ch=BOARD.width/8,BOARD.height/8
    # This empty cell must remain evidence of newly moving material.
    r,c=4,0
    y0,y1=round(BOARD.y+r*ch),round(BOARD.y+(r+1)*ch)
    x0,x1=round(BOARD.x+c*cw),round(BOARD.x+(c+1)*cw)
    assert np.array_equal(baseline[y0:y1,x0:x1],before[y0:y1,x0:x1])
    x,y,w,h=piece['bounds']
    template=cv2.resize(before[y:y+h,x:x+w],(round(piece['width']*cw),round(piece['height']*ch)))
    point,confidence=match_dragged_piece(held,template,(BOARD.x,BOARD.y+3*ch),
        color=piece['color'],cells=piece['cells'],baseline=baseline)
    assert abs(point[0]-BOARD.x)<cw*.22
    assert abs(point[1]-(BOARD.y+3*ch))<ch*.22
    assert confidence>.9
