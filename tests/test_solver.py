from engine.game_state import GameState,Piece
from engine.simulator import apply_move
from solver.beam_search import BeamSolver
from solver.move_generator import legal_moves
from solver.heuristics import evaluate

def exhaustive(state,cleared=0,depth=0):
    children=[]
    for move in legal_moves(state):
        step=apply_move(state,move)
        children.append(exhaustive(step.state,cleared+len(step.rows)+len(step.cols),depth+1))
    return max(children) if children else (depth,evaluate(state.board,state.size,cleared))

def test_small_search_matches_exhaustive_oracle():
    state=GameState(3,0b000001001,(Piece("A",((0,0),(0,1))),Piece("B",((0,0),))))
    solver=BeamSolver(width=10000,time_limit=5)
    result=solver.solve(state)
    assert not result.timed_out and len(result.plans)==3
    best=result.plans[0]
    assert (best.depth,best.value)==exhaustive(state)
    assert len({p.moves[0] for p in result.plans})==3
    for plan in result.plans:
        steps=solver.replay(state,plan)
        assert steps[-1].state.board==plan.final_board
        assert len(steps)==plan.depth
        assert len({m.piece_id for m in plan.moves})==plan.depth
    assert solver.solve(state).cached

def test_piece_order_can_rescue_blocked_piece():
    state=GameState(3,0b110110110,(Piece("A",((0,0),(0,1),(0,2))),Piece("B",((0,0),(1,0),(2,0)))))
    result=BeamSolver(width=100,time_limit=2).solve(state)
    assert result.plans[0].depth==2
    assert result.plans[0].moves[0].piece_id=="B"

def test_empty_and_no_legal_moves():
    solver=BeamSolver()
    assert not solver.solve(GameState(3)).plans
    assert not solver.solve(GameState(3,511,(Piece("A",((0,0),)),))).plans

def test_tiny_budget_returns_legal_prefix():
    state=GameState(8,0,tuple(Piece(str(i),((0,0),)) for i in range(3)))
    solver=BeamSolver(time_limit=0.000001)
    result=solver.solve(state)
    assert result.timed_out and result.plans
    assert not solver.solve(state).cached
    for plan in result.plans: assert solver.replay(state,plan)
