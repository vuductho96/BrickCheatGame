import json,random
from pathlib import Path
from engine.game_state import GameState,Piece
from engine.game_rules import placements
from engine.simulator import apply_move,Move
from solver.batch_feasibility import feasible_batch
from solver.stochastic import rollout_tray

def replay(board,size,shapes,witness):
    state=GameState(size,board,tuple(Piece(str(i),s) for i,s in enumerate(shapes)))
    for i,r,c in witness.steps:state=apply_move(state,Move(str(i),r,c)).state
    assert not state.pieces and state.board==witness.board

def test_clear_can_unlock_a_piece_which_initially_has_no_space():
    shapes=(((0,0),(0,1),(0,2)),((0,0),(1,0),(2,0)))
    witness=feasible_batch(int('110110110',2),3,shapes)
    assert witness.status=='feasible'
    replay(int('110110110',2),3,shapes,witness)

def test_exact_search_rescues_a_narrow_beam_without_rotating_shapes():
    board=31911
    shapes=(((0,0),(0,1)),((0,2),(1,2),(2,0),(2,1),(2,2)),((0,0),(1,0),(1,1)))
    assert rollout_tray(board,4,shapes,width=1)[0]==2
    assert rollout_tray(board,4,shapes,width=1,robust=True)[0]==3
    witness=feasible_batch(board,4,shapes)
    assert witness.status=='feasible'
    replay(board,4,shapes,witness)

def test_node_cap_is_unknown_and_never_a_death_certificate():
    shapes=(((0,0),),)*3
    witness=feasible_batch(0,4,shapes,node_cap=0)
    assert witness.status=='unknown' and not witness.steps

def test_individual_placeability_is_not_whole_batch_survival():
    from solver.shape_prior import legal_count
    square=tuple((r,c) for r in range(3) for c in range(3))
    board=sum(1<<(r*8+c) for r in range(8) for c in range(8)
              if (r+c)%2==0 and not (r<3 and c<3))
    assert legal_count(board,8,square)==1
    assert feasible_batch(board,8,(square,square,((0,0),))).status=='impossible'

def test_latest_real_losing_tray_is_proven_impossible():
    data=json.loads((Path(__file__).resolve().parents[1]/'artifacts/loss-latest-analysis.json').read_text(encoding='utf8'))
    state=GameState.from_dict(data['last_before'])
    assert feasible_batch(state.board,8,tuple(p.cells for p in state.pieces)).status=='impossible'

def test_feasibility_agrees_with_independent_simulator_enumeration():
    rng=random.Random(1871)
    pool=(((0,0),),((0,0),(0,1)),((0,0),(1,1)),((0,0),(1,0),(1,1)))
    def exhaustive(state):
        if not state.pieces:return True
        for p in state.pieces:
            for r,c,mask in placements(state.size,p.cells):
                if state.board&mask:continue
                if exhaustive(apply_move(state,Move(p.id,r,c)).state):return True
        return False
    for _ in range(100):
        board=rng.randrange(1<<9);shapes=tuple(rng.choice(pool) for _ in range(3))
        state=GameState(3,board,tuple(Piece(str(i),s) for i,s in enumerate(shapes)))
        witness=feasible_batch(board,3,shapes)
        assert witness.status!='unknown'
        assert (witness.status=='feasible')==exhaustive(state)
        if witness.status=='feasible':replay(board,3,shapes,witness)
