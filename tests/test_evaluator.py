from engine.game_state import GameState,Piece
from solver.beam_search import BeamSolver
from solver.evaluator import evaluate_known_batches

def test_known_future_batches_preserve_order_without_prediction():
    state=GameState(3,0,(Piece("A",((0,0),)),))
    solver=BeamSolver(time_limit=2)
    plans=solver.solve(state).plans
    future=((Piece("NEXT",((0,0),(0,1),(0,2))),),)
    evaluated=evaluate_known_batches(state,plans,future,solver)
    assert evaluated and all(e.total_depth==2 for e in evaluated)
    assert all(e.batches_completed==1 and not e.truncated for e in evaluated)

def test_partial_current_tray_cannot_be_replaced_by_future():
    state=GameState(8,0,(Piece("A",((0,0),)),Piece("B",((0,0),)),Piece("C",((0,0),))))
    solver=BeamSolver(time_limit=0.000001)
    result=solver.solve(state)
    evaluated=evaluate_known_batches(state,result.plans,((Piece("F",((0,0),)),),),solver)
    assert evaluated and all(e.batches_completed==0 and e.truncated for e in evaluated)
