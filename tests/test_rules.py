import random
import pytest
from engine.game_state import GameState,Piece
from engine.game_rules import Rules
from engine.simulator import Move,apply_move,is_game_over
from solver.move_generator import legal_moves

def test_simultaneous_cross_clear_and_score():
    # Last cell completes row 0 and column 0 together.
    state=GameState(3,(1<<1)|(1<<2)|(1<<3)|(1<<6),(Piece("A",((0,0),)),))
    step=apply_move(state,Move("A",0,0),Rules(2,7))
    assert step.state.board==0 and step.rows==(0,) and step.cols==(0,)
    assert step.points==16 and not step.state.pieces
    assert not is_game_over(step.state)
    assert state.board != 0  # Input immutable.

def reference(grid,cells,row,col):
    n=len(grid)
    result=[r[:] for r in grid]
    for dr,dc in cells:
        rr,cc=row+dr,col+dc
        if not 0<=rr<n or not 0<=cc<n or result[rr][cc]:
            return None
        result[rr][cc]=1
    rows=[r for r in range(n) if all(result[r])]
    cols=[c for c in range(n) if all(result[r][c] for r in range(n))]
    for r in rows:
        for c in range(n): result[r][c]=0
    for c in cols:
        for r in range(n): result[r][c]=0
    return result,tuple(rows),tuple(cols)

def test_random_placements_against_independent_matrix_reference():
    rng=random.Random(7)
    shapes=[((0,0),),((0,0),(0,1)),((0,0),(1,0),(1,1))]
    for _ in range(60):
        n=rng.randint(2,6)
        state=GameState(n,rng.getrandbits(n*n),(Piece("A",rng.choice(shapes)),))
        expected=[]
        for r in range(-1,n+1):
            for c in range(-1,n+1):
                outcome=reference(state.matrix(),state.pieces[0].cells,r,c)
                if outcome is None:
                    with pytest.raises(ValueError): apply_move(state,Move("A",r,c))
                else:
                    expected.append((r,c))
                    step=apply_move(state,Move("A",r,c))
                    assert (step.state.matrix(),step.rows,step.cols)==outcome
        assert [(m.row,m.col) for m in legal_moves(state)]==expected

def test_validation_and_json_roundtrip():
    state=GameState(4,17,(Piece("A",((2,3),(2,4))),),12)
    assert GameState.from_json(state.to_json())==state
    with pytest.raises(ValueError): GameState(4,1<<16)
    with pytest.raises(ValueError): Piece("A",((0,0),(0,0)))
    with pytest.raises(ValueError): GameState(4,0,(Piece("A",((0,0),)),)*2)
    with pytest.raises(ValueError): apply_move(state,Move("missing",0,0))
    data=state.to_dict()
    data["board"][0][0]=2
    with pytest.raises(ValueError): GameState.from_dict(data)

def test_game_over_vs_empty_tray():
    assert is_game_over(GameState(3,(1<<9)-1,(Piece("A",((0,0),)),)))
    assert not is_game_over(GameState(3,(1<<9)-1,()))
