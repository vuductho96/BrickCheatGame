from autopilot import unique_clear_target
from engine.game_state import GameState,Piece
from engine.simulator import Move


def test_only_placement_that_completes_a_column_is_identified():
    state=GameState(4,sum(1<<(r*4+2) for r in (2,3)),(Piece('A',((0,0),(1,0))),))
    assert unique_clear_target(state,Move('A',0,2))


def test_no_clear_cannot_authorize_release():
    piece=Piece('A',((0,0),(1,0)))
    state=GameState(4,0,(piece,))
    assert not unique_clear_target(state,Move('A',0,0))


def test_same_cleared_row_with_different_lower_arm_placements_is_ambiguous():
    piece=Piece('A',((0,0),(2,0)))
    # At row zero only row two clears; at row two only row two also clears.
    board=sum(1<<(2*5+c) for c in range(1,5))
    state=GameState(5,board,(piece,))
    assert not unique_clear_target(state,Move('A',0,0))
    assert not unique_clear_target(state,Move('A',2,0))
