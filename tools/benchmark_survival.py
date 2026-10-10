"""Paired seeded unlimited games; score is engine units, not phone points."""
import argparse,json,random,statistics,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine.game_state import GameState,Piece
from engine.simulator import apply_move
from solver.beam_search import BeamSolver
from solver.heuristics import Weights
from solver.shape_prior import SHAPES
from solver.stochastic import StochasticSolver,ShapePrior

BASE=Weights(cleared=20,empty=1,mobility=.2,holes=6,fragmentation=3)

def run_game(seed,weights,max_moves,width,budget,pool,lookahead=False,prior_path=None,robust=False,adaptive=False,learn=False,commit=False):
    rng=random.Random(seed);state=GameState(8);lines=0;moves=0;elapsed=0
    solver=StochasticSolver(width=width,time_limit=budget,weights=weights,
                            prior=ShapePrior.load(prior_path),robust=robust,adaptive=adaptive,commit_tray=commit) if lookahead else BeamSolver(width=width,time_limit=budget,weights=weights)
    batches=0
    while moves<max_moves:
        if not state.pieces:
            choices=pool(batches) if callable(pool) else pool
            pieces=tuple(Piece(chr(65+i),rng.choice(choices)) for i in range(3))
            if learn and moves:solver.prior.observe_refill(pieces)
            batches+=1
            state=GameState(8,state.board,pieces,state.score)
        result=solver.solve(state);elapsed+=result.elapsed_ms
        if not result.plans:break
        # Replan after each move, exactly as the observed-frame autopilot does.
        step=apply_move(state,result.plans[0].moves[0]);state=step.state
        lines+=len(step.rows)+len(step.cols);moves+=1
    return dict(seed=seed,moves=moves,lines=lines,engine_score=state.score,
                capped=moves==max_moves,mean_search_ms=round(elapsed/max(1,moves),2))

def main():
    p=argparse.ArgumentParser();p.add_argument('--seeds',type=int,default=6)
    p.add_argument('--start',type=int,default=100);p.add_argument('--moves',type=int,default=180)
    p.add_argument('--width',type=int,default=40);p.add_argument('--budget',type=float,default=.25)
    p.add_argument('--output',default='artifacts/survival-benchmark.json')
    p.add_argument('--variants',default='baseline,reserve,reserve_strong')
    p.add_argument('--pools',default='observed,broad')
    p.add_argument('--prior',default=None)
    args=p.parse_args()
    observed=set()
    for line in Path('artifacts/play-until-loss-log/moves.jsonl').read_text(encoding='utf8').splitlines():
        item=json.loads(line)
        for piece in (item.get('before') or {}).get('pieces',[]):
            observed.add(tuple(tuple(c) for c in piece['cells']))
    large=tuple(s for s in SHAPES if len(s)>=6)
    pools={'observed':tuple(sorted(observed)), 'broad':SHAPES,
           'large_stress':SHAPES+large*12,
           'curriculum':lambda batch:SHAPES if batch<8 else SHAPES+large*12}
    variants={'baseline':BASE,
        'reserve':Weights(cleared=20,empty=1,mobility=.2,holes=6,fragmentation=3,coverage=45,options=12),
        'reserve_strong':Weights(cleared=20,empty=1,mobility=.2,holes=6,fragmentation=3,coverage=90,options=20),
        'lookahead':Weights(cleared=20,empty=1,mobility=.2,holes=6,fragmentation=3,coverage=45,options=12),
        'robust':Weights(cleared=20,empty=1,mobility=.2,holes=6,fragmentation=3,coverage=45,options=12)}
    variants['spatial']=Weights(cleared=10,empty=1.5,mobility=.15,holes=6,fragmentation=3,coverage=45,options=12,boundary=.35)
    variants['compact']=Weights(cleared=20,empty=1,mobility=.2,holes=6,fragmentation=3,coverage=45,options=12,boundary=.7)
    variants['learned']=variants['lookahead']
    variants['adaptive']=variants['spatial']
    variants['committed']=variants['spatial']
    variants['learned_commit']=variants['lookahead']
    report={'settings':vars(args),'units':'provisional engine score; not phone points','results':{}}
    for name,weights in variants.items():
        if name not in args.variants.split(','):continue
        report['results'][name]={}
        for distribution,pool in pools.items():
            if distribution not in args.pools.split(','):continue
            games=[run_game(seed,weights,args.moves,args.width,args.budget,pool,lookahead=name in ('lookahead','robust','spatial','compact','learned','adaptive','committed','learned_commit'),prior_path=args.prior,robust=name in ('robust','spatial','compact','adaptive','committed','learned_commit'),adaptive=name=='adaptive',learn=name in ('learned','adaptive','learned_commit'),commit=name in ('committed','learned_commit'))
                   for seed in range(args.start,args.start+args.seeds)]
            stats={k:round(statistics.mean(g[k] for g in games),2) for k in ('moves','lines','engine_score','mean_search_ms')}
            report['results'][name][distribution]={'mean':stats,'games':games}
            print(name,distribution,json.dumps(stats),flush=True)
            Path(args.output).write_text(json.dumps(report,indent=2),encoding='utf8')
if __name__=='__main__':main()
