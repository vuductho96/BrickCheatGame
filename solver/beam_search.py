"""Bounded deterministic search explores all remaining piece choices at each level."""
from dataclasses import dataclass
from time import perf_counter
from collections import OrderedDict
from engine.game_rules import Rules, placements, clear_lines
from engine.simulator import Move, apply_move
from .heuristics import Weights, evaluate

@dataclass(frozen=True)
class Plan:
    moves: tuple[Move,...]
    value: float
    cleared: int
    depth: int
    final_board: int

@dataclass(frozen=True)
class SearchResult:
    plans: tuple[Plan,...]
    elapsed_ms: float
    explored: int
    depth: int
    timed_out: bool
    cached: bool = False
    future_samples: int = 0
    future_survived: int = 0
    future_horizon: int = 0

class BeamSolver:
    def __init__(self,width=100,time_limit=0.8,weights=Weights(),rules=Rules(),plan_limit=3):
        if width<3 or time_limit<=0: raise ValueError("Width >=3 and positive time limit required")
        self.width,self.time_limit,self.weights,self.rules=width,time_limit,weights,rules
        self.plan_limit=max(3,plan_limit)
        self.cache=OrderedDict()
    def solve(self,state):
        start=perf_counter()
        key=(state,self.width,self.time_limit,self.weights,self.rules,self.plan_limit)
        if key in self.cache:
            self.cache.move_to_end(key)
            old=self.cache[key]
            return SearchResult(old.plans,(perf_counter()-start)*1000,0,old.depth,old.timed_out,True)
        beam=[(state.board,tuple(range(len(state.pieces))),(),0,0.0)]
        terminals,explored,depth,timed_out=[],0,0,False
        candidates_for=[placements(state.size,p.cells) for p in state.pieces]
        for level in range(len(state.pieces)):
            children={}
            for board,remaining,path,cleared,value in beam:
                produced=False
                for i in remaining:
                    for row,col,mask in candidates_for[i]:
                        if mask&board: continue
                        if explored and explored%32==0 and perf_counter()-start>=self.time_limit:
                            timed_out=True
                            break
                        produced=True
                        explored+=1
                        new_board,rows,cols=clear_lines(board|mask,state.size)
                        new_cleared=cleared+len(rows)+len(cols)
                        new_path=path+(Move(state.pieces[i].id,row,col),)
                        new_remaining=tuple(j for j in remaining if j!=i)
                        new_value=evaluate(new_board,state.size,new_cleared,self.weights)
                        child=(new_board,new_remaining,new_path,new_cleared,new_value)
                        signature=(new_board,new_remaining,new_path[0])
                        old=children.get(signature)
                        if old is None or new_value>old[4]: children[signature]=child
                    if timed_out: break
                if not produced and path: terminals.append((board,remaining,path,cleared,value))
                if timed_out: break
            if children:
                beam=sorted(children.values(),key=lambda n:n[4],reverse=True)[:self.width]
                depth=level+1
            else: break
            if timed_out: break
        finalists=[n for n in beam+terminals if n[2]]
        finalists.sort(key=lambda n:(len(n[2]),n[4]),reverse=True)
        plans,first_moves,final_boards=[],set(),set()
        for board,remaining,path,cleared,value in finalists:
            if self.plan_limit==3:
                if path[0] in first_moves:continue
            elif board in final_boards:continue
            first_moves.add(path[0])
            final_boards.add(board)
            plans.append(Plan(path,value,cleared,len(path),board))
            if len(plans)==self.plan_limit: break
        result=SearchResult(tuple(plans),(perf_counter()-start)*1000,explored,depth,timed_out)
        if not timed_out:
            self.cache[key]=result
            if len(self.cache)>128: self.cache.popitem(last=False)
        return result
    def replay(self,state,plan):
        steps=[]
        for move in plan.moves:
            step=apply_move(state,move,self.rules)
            steps.append(step)
            state=step.state
        return tuple(steps)
