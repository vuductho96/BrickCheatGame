"""Local sampled lookahead. Random trays are scenarios, never known future."""
from collections import Counter,OrderedDict,deque
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
import json,random,time,threading
from engine.game_rules import placements,clear_lines
from .beam_search import BeamSolver
from .heuristics import CLASSIC_WEIGHTS,SURVIVAL_WEIGHTS,COMPACT_WEIGHTS
from .shape_prior import SHAPES,legal_count
from .batch_feasibility import feasible_batch


class ShapePrior:
    def __init__(self,counts=(),recent=(),trays=()):
        self.lock=threading.RLock();self.version=0;self.batches=0
        self.counts=Counter(dict(counts))
        self.recent=deque(recent,maxlen=72)
        self.trays=deque(trays,maxlen=48)
        self._rebuild()

    def _rebuild(self):
        shapes=sorted(set(SHAPES)|set(self.counts)|set(self.recent))
        total=sum(self.counts.values())
        recent=Counter(self.recent);recent_total=sum(recent.values())
        large=[s for s in shapes if len(s)>=6]
        self.shapes=tuple(shapes)
        self.weights=tuple(.3/len(shapes)+(.2/len(large) if s in large else 0)+
                           (.3*self.counts[s]/total if total else .3/len(shapes))+
                           (.2*recent[s]/recent_total if recent_total>=24 else
                            .2*self.counts[s]/total if total else .2/len(shapes)) for s in shapes)

    @classmethod
    def load(cls,path=None):
        path=path or Path(__file__).resolve().parents[1]/'config/shape-prior.json'
        try:data=json.loads(Path(path).read_text(encoding='utf8'))
        except (OSError,ValueError):return cls()
        prior=cls(((tuple(tuple(c) for c in p['cells']),p['count']) for p in data['shapes']),
                  recent=(tuple(tuple(c) for c in s) for s in data.get('recent',())),
                  trays=(tuple(tuple(tuple(c) for c in s) for s in tray)
                         for tray in data.get('trays',())))
        prior.batches=data.get('batches',0)
        return prior

    def observe_refill(self,pieces,persist=False):
        if len(pieces)!=3:raise ValueError('A verified refill must contain three pieces')
        with self.lock:
            self.counts.update(p.cells for p in pieces)
            self.recent.extend(p.cells for p in pieces)
            self.trays.append(tuple(p.cells for p in pieces))
            self.batches+=1;self.version+=1;self._rebuild()
            if persist:
                path=Path(__file__).resolve().parents[1]/'config/shape-prior.json'
                data={'source':'verified refill events only','batches':self.batches,
                      'recent':list(self.recent),'trays':list(self.trays),
                      'shapes':[{'cells':s,'count':n} for s,n in sorted(self.counts.items())]}
                temporary=path.with_suffix('.tmp')
                temporary.write_text(json.dumps(data,indent=2),encoding='utf8')
                temporary.replace(path)

    def include_shapes(self,pieces):
        """Allow observed novel shapes without fabricating refill frequencies."""
        with self.lock:
            missing={p.cells for p in pieces}-set(self.shapes)
            if not missing:return
            for shape in missing:self.counts[shape]=0
            self.version+=1
            self._rebuild()

    def scenarios(self,seed,count,horizon):
        with self.lock:
            rng=random.Random(seed)
            # Keep correlations within observed refills: two large squares in
            # one tray must not be modelled as three independent small draws.
            # Mix with broad draws so unseen combinations still receive weight.
            recent_trays=tuple(self.trays)[-24:]
            def draw():
                if recent_trays and rng.random()<.5:
                    return rng.choice(recent_trays)
                return tuple(rng.choices(self.shapes,weights=self.weights,k=3))
            return tuple(tuple(draw() for _ in range(horizon)) for _ in range(count))


@lru_cache(maxsize=12000)
def rollout_tray(board,size,shapes,width=4,robust=False):
    """Small deterministic beam: same effort for every candidate/scenario."""
    candidates=[placements(size,s) for s in shapes]
    beam=[(board,tuple(range(len(shapes))),0,0)]
    best=(0,0,board)
    for depth in range(1,len(shapes)+1):
        children={}
        for current,remaining,cleared,_ in beam:
            for i in remaining:
                rest=tuple(j for j in remaining if j!=i)
                for r,c,mask in candidates[i]:
                    if current&mask:continue
                    after,rows,cols=clear_lines(current|mask,size)
                    lines=cleared+len(rows)+len(cols)
                    # Known remaining pieces inform the approximate future search.
                    fits=sum(legal_count(after,size,shapes[j])>0 for j in rest)
                    value=lines*20+size*size-after.bit_count()+fits*8
                    key=(after,rest)
                    if key not in children or value>children[key][3]:
                        children[key]=(after,rest,lines,value)
        if not children:break
        beam=sorted(children.values(),key=lambda n:n[3],reverse=True)[:width]
        node=beam[0];best=(depth,node[2],node[0])
    if robust and best[0]<len(shapes):
        witness=feasible_batch(board,size,shapes)
        if witness.status=='feasible':
            return len(shapes),witness.cleared,witness.board
    return best


class StochasticSolver:
    def __init__(self,width=240,time_limit=.85,weights=CLASSIC_WEIGHTS,rules=None,
                 prior=None,samples=4,horizon=2,robust=True,adaptive=False,commit_tray=False):
        from engine.game_rules import Rules
        self.width,self.time_limit,self.weights=width,time_limit,weights
        self.rules=rules or Rules();self.prior=prior or ShapePrior.load()
        self.samples,self.horizon=samples,horizon
        self.robust=robust
        self.adaptive=adaptive
        self.commit_tray=commit_tray;self.pending={}
        self.base=BeamSolver(width=width,time_limit=time_limit*.65,weights=weights,
                             rules=self.rules,plan_limit=12)
        self.cache=OrderedDict()

    def replay(self,state,plan):return self.base.replay(state,plan)

    def commitment_key(self,state):
        # The phone does not OCR a cumulative score. Board and exact piece
        # identities/shapes must match the prediction before following a tail.
        return state.size,state.board,state.pieces,self.prior.version,self.weights

    def remember(self,state,result):
        if not self.commit_tray or not result.plans:return result
        plan=result.plans[0]
        if plan.depth!=len(state.pieces):return result
        from engine.simulator import apply_move
        from .beam_search import Plan
        current=state
        for i,move in enumerate(plan.moves[:-1],1):
            current=apply_move(current,move).state
            remaining=plan.moves[i:]
            final=current;cleared=0
            for next_move in remaining:
                step=apply_move(final,next_move);final=step.state
                cleared+=len(step.rows)+len(step.cols)
            tail=Plan(remaining,plan.value,cleared,len(remaining),final.board)
            self.pending[self.commitment_key(current)]=replace(result,plans=(tail,),
                depth=len(remaining),elapsed_ms=0,explored=0,cached=True)
        return result

    def solve(self,state):
        start=time.perf_counter()
        self.prior.include_shapes(state.pieces)
        if self.adaptive:
            with self.prior.lock:recent=tuple(self.prior.recent)
            hard=len(recent)>=24 and sum(len(s)>=6 for s in recent)/len(recent)>=1/3
            self.weights=COMPACT_WEIGHTS if hard else SURVIVAL_WEIGHTS
            self.base.weights=self.weights
        if self.commit_tray:
            committed=self.pending.get(self.commitment_key(state))
            if committed is not None:return committed
            self.pending.clear()
        key=(state,self.prior.version,self.weights)
        if key in self.cache:
            old=self.cache[key];self.cache.move_to_end(key)
            return self.remember(state,replace(old,elapsed_ms=(time.perf_counter()-start)*1000,explored=0,cached=True))
        result=self.base.solve(state)
        complete=[p for p in result.plans if p.depth==len(state.pieces)]
        if self.robust and not complete and state.pieces:
            witness=feasible_batch(state.board,state.size,tuple(p.cells for p in state.pieces))
            if witness.status=='feasible':
                from .beam_search import Plan
                from .heuristics import evaluate
                from engine.simulator import Move
                moves=tuple(Move(state.pieces[i].id,r,c) for i,r,c in witness.steps)
                rescued=Plan(moves,evaluate(witness.board,state.size,witness.cleared,self.weights),
                             witness.cleared,len(moves),witness.board)
                result=replace(result,plans=(rescued,),depth=len(moves))
                complete=[rescued]
        if not complete:
            plans=[];seen=set()
            for p in result.plans:
                if p.moves[0] in seen:continue
                plans.append(p);seen.add(p.moves[0])
                if len(plans)==3:break
            return replace(result,plans=tuple(plans))
        # Same sampled trays for every candidate. The state seed is reproducible.
        seed=state.board ^ sum((i+1)*sum((r*state.size+c+1)*7919 for r,c in p.cells)
                              for i,p in enumerate(state.pieces))
        scenarios=self.prior.scenarios(seed,self.samples,self.horizon)
        boards=list(dict.fromkeys(p.final_board for p in complete))
        totals={b:[] for b in boards};finished=0
        # Only completed paired rounds affect ranking; no candidate receives
        # an easier sample set because the wall-clock budget expired.
        for scenario in scenarios:
            round_values={}
            for board in boards:
                current=board;placed=lines=0
                for tray in scenario:
                    depth,clears,current=rollout_tray(current,state.size,tray)
                    placed+=depth;lines+=clears
                    if depth<3:break
                round_values[board]=(placed,lines)
                if time.perf_counter()-start>=self.time_limit:break
            if len(round_values)!=len(boards):break
            for b,value in round_values.items():totals[b].append(value)
            finished+=1
            if time.perf_counter()-start>=self.time_limit:break
        def rank(plan):
            values=totals[plan.final_board]
            if not values:return plan.value
            mean_depth=sum(d for d,l in values)/len(values)
            mean_lines=sum(l for d,l in values)/len(values)
            worst_depth=min(d for d,l in values)
            return plan.value+mean_depth*35+mean_lines*8+worst_depth*15
        ranked=sorted(complete,key=rank,reverse=True)
        plans=[];seen=set()
        for p in ranked:
            if p.moves[0] in seen:continue
            plans.append(replace(p,value=rank(p)));seen.add(p.moves[0])
            if len(plans)==3:break
        plans=tuple(plans)
        survived=sum(d==3*self.horizon for d,l in totals[ranked[0].final_board])
        final=replace(result,plans=plans,elapsed_ms=(time.perf_counter()-start)*1000,
                      cached=False,
                      future_samples=finished,future_survived=survived,future_horizon=self.horizon,
                      timed_out=result.timed_out or finished<self.samples)
        if not final.timed_out:
            self.cache[key]=final
            if len(self.cache)>128:self.cache.popitem(last=False)
        return self.remember(state,final)
