import json
from engine.game_state import Piece
from solver.stochastic import ShapePrior
from tools.rebuild_joint_prior import rebuild


def test_joint_samples_keep_large_pair_and_remain_reproducible(tmp_path):
    square=tuple((r,c) for r in range(3) for c in range(3))
    tray=(Piece('A',square),Piece('B',square),Piece('C',((0,0),)))
    prior=ShapePrior()
    for _ in range(8):prior.observe_refill(tray)
    samples=prior.scenarios(73,100,3)
    assert samples==prior.scenarios(73,100,3)
    assert sum(t==tuple(p.cells for p in tray) for s in samples for t in s)>100
    path=tmp_path/'prior.json'
    path.write_text(json.dumps({'shapes':[], 'trays':list(prior.trays)}))
    assert tuple(ShapePrior.load(path).trays)==tuple(prior.trays)


def test_rebuild_ignores_retries_and_preserves_counts(tmp_path):
    piece={'id':'A','cells':[[0,0]]}
    refill={'before':{'pieces':[piece]},'actual':{'pieces':[dict(piece,id=i) for i in 'ABC']}}
    events=[dict(refill,event='planned'),dict(refill,event='verified')]
    log=tmp_path/'log';log.write_text('\n'.join(json.dumps(x) for x in events))
    profile=tmp_path/'profile';profile.write_text(json.dumps({'shapes':[dict(piece,count=30)],'batches':10}))
    assert rebuild(log,profile)==1
    data=json.loads(profile.read_text())
    assert data['batches']==10 and data['shapes'][0]['count']==30
    assert len(data['trays'])==1 and len(data['recent'])==3
