import json
from unittest.mock import Mock

from autopilot import Autopilot
from engine.game_state import GameState, Piece
from engine.simulator import Move, apply_move
from web_bridge import PhoneBridge


def test_execution_keeps_locked_sequence_and_serializes_during_drag():
    bridge=PhoneBridge()
    bridge.adb=Mock(serial='offline-fixture')
    auto=Autopilot(bridge)
    bridge.auto=auto
    state=GameState(8,0,(Piece('A',((0,0),)),Piece('B',((0,0),))))
    moves=(Move('A',2,3),Move('B',2,4))
    auto.result_state=state
    auto.result=Mock(plans=[Mock(moves=moves)])
    observed={'state':state,'state_id':'initial','phase':'playing',
              'pieces':[{'id':p.id,'cells':p.cells,'width':1,'height':1,'slot':i,'color':'#ff8800'} for i,p in enumerate(state.pieces)]}
    expected=apply_move(state,moves[0]).state
    auto.record_move('planned',observed,moves[0],expected)
    auto.stage='moving'
    auto.pending_move=vars(moves[0])
    payload=bridge.serialize(observed)
    assert payload['plans']==[]
    assert payload['execution']['moves']==[vars(m) for m in moves]
    assert payload['execution']['expected']==expected.matrix()
    json.dumps(payload)
    wrong=apply_move(state,Move('A',2,2)).state
    auto.record_move('mismatch',observed,moves[0],expected,{'state':wrong,'phase':'playing'})
    check=auto.status()['last_check']
    assert check['outcome']=='mismatch'
    assert check['expected'][2][3]==1 and check['actual'][2][2]==1
    assert check['expected']!=check['actual']
    json.dumps(check)


def test_unverified_end_does_not_invent_observed_board():
    auto=Autopilot(Mock())
    state=GameState(8,0,(Piece('A',((0,0),)),))
    move=Move('A',0,0)
    auto.record_move('unverified_game_over',{'state':state},move,
                     apply_move(state,move).state,{'phase':'game_over'})
    assert auto.status()['last_check']['actual'] is None


def test_cancel_waits_until_return_animation_restores_original_board_and_tray(monkeypatch):
    import autopilot
    monkeypatch.setattr(autopilot.time,'sleep',lambda _:None)
    bridge=Mock()
    auto=Autopilot(bridge)
    state=GameState(8,0,(Piece('A',((0,0),)),))
    ghost=apply_move(state,Move('A',7,1)).state
    observed=dict(state=state,state_id='before',pieces=[])
    returned=dict(state=state,state_id='before',pieces=[])
    bridge.parse.side_effect=[dict(state=ghost),dict(state=ghost),returned,returned,returned]
    auto.settle_return(observed,Move('A',0,0))
    assert bridge.parse.call_count==5
    bridge.publish.assert_called_once_with(returned)
    assert auto.stage=='settling'


def test_cancel_timeout_stops_instead_of_replanning_from_ghost(monkeypatch):
    import autopilot
    import pytest
    from types import SimpleNamespace
    clock=iter(range(10))
    monkeypatch.setattr(autopilot,'time',SimpleNamespace(monotonic=lambda:next(clock),sleep=lambda _:None))
    bridge=Mock()
    auto=Autopilot(bridge)
    state=GameState(8,0,(Piece('A',((0,0),)),))
    ghost=apply_move(state,Move('A',7,1)).state
    bridge.parse.return_value=dict(state=ghost,phase='playing')
    observed=dict(state=state,state_id='before',pieces=[])
    with pytest.raises(autopilot.PlacementMismatch):auto.settle_return(observed,Move('A',0,0))
    bridge.publish.assert_not_called()
    assert auto.last_check['outcome']=='abort_mismatch'
