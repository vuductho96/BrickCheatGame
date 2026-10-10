from unittest.mock import Mock
from engine.game_state import GameState,Piece
from engine.simulator import Move
from solver.beam_search import Plan,SearchResult
from solver.stochastic import ShapePrior,StochasticSolver,rollout_tray
from tools.build_shape_prior import build
import json


def test_refill_model_counts_verified_batches_not_retries(tmp_path):
    shape={'id':'A','cells':[[0,0],[1,1]]}
    tray={'pieces':[dict(shape,id=i) for i in ('A','B','C')]}
    events=[{'event':'planned','before':tray}]*10
    events+=[{'event':'verified','before':{'pieces':[shape]},'actual':tray}]
    events+=[{'event':'verified','before':tray,'actual':{'pieces':[shape]}}]
    path=tmp_path/'moves.jsonl';path.write_text('\n'.join(json.dumps(e) for e in events))
    data=build(path)
    assert data['batches']==1 and data['shapes'][0]['count']==3


def test_unknown_shapes_and_prior_sampling_are_local_reproducible():
    diagonal=((0,1),(1,0))
    prior=ShapePrior(((diagonal,20),))
    assert diagonal in prior.shapes
    assert abs(sum(prior.weights)-1)<1e-10
    assert prior.scenarios(22,6,2)==prior.scenarios(22,6,2)
    assert all(len(tray)==3 for scenario in prior.scenarios(22,6,2) for tray in scenario)


def test_verified_refill_updates_prior_version_and_counts():
    prior=ShapePrior();pieces=tuple(Piece(i,((0,1),(1,0))) for i in ('A','B','C'))
    prior.observe_refill(pieces)
    assert prior.counts[pieces[0].cells]==3 and prior.version==1 and prior.batches==1
    assert pieces[0].cells in prior.shapes

def test_recent_hard_shapes_adapt_without_overwriting_lifetime_history(tmp_path):
    small=((0,0),);large=tuple((r,c) for r in range(3) for c in range(3))
    prior=ShapePrior(((small,100),))
    old=dict(zip(prior.shapes,prior.weights))[large]
    pieces=tuple(Piece(i,large) for i in ('A','B','C'))
    for _ in range(30):prior.observe_refill(pieces)
    assert len(prior.recent)==72 and prior.counts[small]==100
    assert dict(zip(prior.shapes,prior.weights))[large]>old
    assert abs(sum(prior.weights)-1)<1e-10
    path=tmp_path/'profile.json'
    path.write_text(json.dumps({'batches':prior.batches,'recent':list(prior.recent),
        'shapes':[{'cells':s,'count':n} for s,n in prior.counts.items()]}))
    restored=ShapePrior.load(path)
    assert restored.weights==prior.weights and restored.batches==30

def test_adaptive_policy_tracks_recent_large_pieces_and_changes_cache_key():
    from solver.heuristics import SURVIVAL_WEIGHTS,COMPACT_WEIGHTS
    prior=ShapePrior();solver=StochasticSolver(prior=prior,adaptive=True,samples=1,horizon=1,time_limit=1)
    state=GameState(4,0,(Piece('A',((0,0),)),))
    solver.solve(state)
    assert solver.weights==SURVIVAL_WEIGHTS
    big=tuple((r,c) for r in range(3) for c in range(3))
    for _ in range(8):prior.observe_refill(tuple(Piece(i,big) for i in ('A','B','C')))
    assert not solver.solve(state).cached
    assert solver.weights==COMPACT_WEIGHTS and solver.base.weights==COMPACT_WEIGHTS
    for _ in range(24):prior.observe_refill(tuple(Piece(i,((0,0),)) for i in ('A','B','C')))
    solver.solve(state)
    assert solver.weights==SURVIVAL_WEIGHTS


def test_committed_tray_follows_tail_only_when_actual_board_and_shapes_match():
    from dataclasses import replace
    from engine.simulator import apply_move
    state=GameState(8,0,tuple(Piece(i,((0,0),(1,0))) for i in ('A','B','C')))
    solver=StochasticSolver(width=30,time_limit=1,samples=1,commit_tray=True)
    first=solver.solve(state);plan=first.plans[0]
    actual=replace(apply_move(state,plan.moves[0]).state,score=0)
    # Repeated HTML polls must not consume the remainder of the batch.
    for _ in range(3):
        tail=solver.solve(actual)
        assert tail.cached and tail.plans[0].moves==plan.moves[1:]
    actual=replace(apply_move(actual,plan.moves[1]).state,score=0)
    assert solver.solve(actual).plans[0].moves==plan.moves[2:]
    assert solver.solve(replace(actual,board=0)).plans[0].depth==1
    assert not solver.pending


def test_learning_new_refill_invalidates_cached_forecast():
    prior=ShapePrior();solver=StochasticSolver(prior=prior,time_limit=1,samples=1,horizon=1)
    state=GameState(4,0,(Piece('A',((0,0),)),))
    first=solver.solve(state)
    assert solver.solve(state).cached and first.future_samples==1
    prior.observe_refill(tuple(Piece(i,((0,0),)) for i in ('A','B','C')))
    assert not solver.solve(state).cached


def test_rollout_respects_clear_order_and_no_rotation():
    board=int('110110110',2)
    horizontal=((0,0),(0,1),(0,2));vertical=((0,0),(1,0),(2,0))
    assert rollout_tray(board,3,(horizontal,vertical))[0]==2
    assert rollout_tray(board,3,(horizontal,))[0]==0


def test_future_big_piece_changes_first_move_without_inventing_current_piece():
    state=GameState(4,0,(Piece('A',((0,0),)),))
    middle=Plan((Move('A',1,1),),100.,0,1,1<<5)
    corner=Plan((Move('A',0,0),),99.,0,1,1)
    big=tuple((r,c) for r in range(3) for c in range(3))
    prior=Mock();prior.scenarios.return_value=(((big,big,big),),)
    solver=StochasticSolver(time_limit=1,prior=prior,samples=1,horizon=1,robust=False)
    solver.base=Mock(solve=Mock(return_value=SearchResult((middle,corner),0.,2,1,False)))
    result=solver.solve(state)
    assert result.plans[0].moves==(Move('A',0,0),)
    assert result.future_samples==1 and result.future_horizon==1
    assert all(m.piece_id=='A' for p in result.plans for m in p.moves)
    assert solver.solve(state).cached


def test_incomplete_current_tray_never_replaced_by_sampled_future():
    state=GameState(3,0,(Piece('A',((0,0),)),Piece('B',((0,0),))))
    plan=Plan((Move('A',0,0),),10.,0,1,1)
    prior=Mock();solver=StochasticSolver(prior=prior,robust=False)
    solver.base=Mock(solve=Mock(return_value=SearchResult((plan,),0.,1,1,False)))
    result=solver.solve(state)
    assert result.plans==(plan,) and result.future_samples==0
    prior.scenarios.assert_not_called()


def test_real_plans_replay_legally_and_have_no_future_piece_ids():
    state=GameState(8,0,tuple(Piece(i,((0,0),(1,0))) for i in ('A','B','C')))
    solver=StochasticSolver(width=30,time_limit=.6,samples=2)
    result=solver.solve(state)
    assert result.future_samples>0
    for plan in result.plans:
        assert solver.replay(state,plan)[-1].state.board==plan.final_board
        assert len({m.piece_id for m in plan.moves})==len(plan.moves)


def test_budget_discards_an_unpaired_scenario_without_biasing_candidates(monkeypatch):
    state=GameState(4,0,(Piece('A',((0,0),)),))
    plans=(Plan((Move('A',1,1),),100.,0,1,1<<5),Plan((Move('A',0,0),),99.,0,1,1))
    solver=StochasticSolver(time_limit=.01,samples=1,robust=False)
    solver.base=Mock(solve=Mock(return_value=SearchResult(plans,0.,2,1,False)))
    clocks=iter((0.,1.,1.))
    monkeypatch.setattr('solver.stochastic.time.perf_counter',lambda:next(clocks))
    result=solver.solve(state)
    assert result.future_samples==0 and result.timed_out
    assert result.plans==plans


def test_truncated_current_tray_search_is_rescued_with_real_piece_ids():
    state=GameState(3,0,(Piece('A',((0,0),)),Piece('B',((0,0),))))
    partial=Plan((Move('A',0,0),),10.,0,1,1)
    solver=StochasticSolver(samples=1,horizon=1,time_limit=1)
    solver.base=Mock(solve=Mock(return_value=SearchResult((partial,),0.,1,1,True)))
    result=solver.solve(state)
    assert result.plans[0].depth==2
    assert {m.piece_id for m in result.plans[0].moves}=={'A','B'}
    from engine.simulator import apply_move
    for move in result.plans[0].moves:state=apply_move(state,move).state
    assert not state.pieces and state.board==result.plans[0].final_board
