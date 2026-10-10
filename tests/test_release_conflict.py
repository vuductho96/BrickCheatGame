from pathlib import Path
from unittest.mock import Mock
import cv2
import pytest
from autopilot import Autopilot,MODES,PlacementRetry
from engine.game_state import GameState,Piece
from engine.simulator import Move
from vision.drop_preview import drop_preview
from web_bridge import BOARD


def test_real_gray_target_with_displaced_single_cell_is_not_released_on_board():
    held=cv2.imread(str(Path(__file__).resolve().parents[1]/'captures'/'auto-gray-sprite-conflict.png'))
    base=held.copy()
    base[690:818,630:756]=(56,61,8)
    base[1772:1828,848:904]=(237,210,17)
    piece=dict(id='C',cells=((0,0),),width=1,height=1,color='#11d2ed',bounds=[848,1772,56,56])
    move=Move('C',1,4)
    preview=drop_preview(held,BOARD,piece)
    assert (preview['row'],preview['col'])==(move.row,move.col)
    observed=dict(state=GameState(8,0,(Piece('C',((0,0),)),)),state_id='before',pieces=[piece],phase='playing')
    bridge=Mock()
    bridge.parse.return_value=observed
    bridge.snapshot.side_effect=[base]+[held]*40
    bridge.live.pressed=False
    bridge.live.touch_position=(0,0)
    bridge.live.status.return_value=dict(width=540,height=1170,live=True)
    def touch(action,x,y):
        bridge.live.pressed=action in (0,2)
        bridge.live.touch_position=(x,y)
    bridge.live.touch.side_effect=touch
    auto=Autopilot(bridge)
    auto.wait=lambda _:None
    auto.move_pointer=Mock()
    with pytest.raises(PlacementRetry):auto.perform_move(observed,move,MODES['fast'])
    assert auto.moves==0
    assert bridge.live.touch.call_args_list[-2].args==(2,438,900)
    assert bridge.live.touch.call_args_list[-1].args==(1,438,900)


@pytest.mark.parametrize('filename',['auto-clear-column-border.png','auto-clear-fragments.png'])
def test_real_clear_column_border_is_not_an_extra_footprint(filename):
    from vision.drop_preview import clear_drop_preview
    image=cv2.imread(str(Path(__file__).resolve().parents[1]/'captures'/filename))
    piece=dict(width=2,height=3)
    assert clear_drop_preview(image,BOARD,piece,5,1,(),(1,))
    assert not clear_drop_preview(image,BOARD,piece,4,5,(),(1,))
    # Even lit complete lines cannot authorize release without gray support.
    hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
    gray=cv2.inRange(hsv,(0,0,80),(179,65,215))
    image[gray>0]=(20,100,230)
    assert not clear_drop_preview(image,BOARD,piece,5,1,(),(1,))
