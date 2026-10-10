"""Optional known-future-batch evaluation; never invent or predict random pieces."""
from dataclasses import dataclass, replace
from time import perf_counter
from .beam_search import BeamSolver

@dataclass(frozen=True)
class FutureEvaluation:
    current_plan: object
    total_depth: int
    total_lines: int
    batches_completed: int
    truncated: bool

def evaluate_known_batches(state,plans,batches,solver=None,budget=2.0):
    if budget<=0: raise ValueError("Positive budget required")
    template=solver or BeamSolver()
    deadline=perf_counter()+budget
    results=[]
    for plan in plans:
        replay=template.replay(state,plan)
        if not replay: continue
        current=replay[-1].state
        depth,lines,completed=plan.depth,plan.cleared,0
        truncated=False
        if current.pieces:
            results.append(FutureEvaluation(plan,depth,lines,0,True))
            continue
        for batch in batches:
            remaining=deadline-perf_counter()
            if remaining<=0:
                truncated=True
                break
            current=replace(current,pieces=tuple(batch))
            future=BeamSolver(template.width,min(template.time_limit,remaining),template.weights,template.rules)
            search=future.solve(current)
            if not search.plans:
                truncated=True
                break
            best=search.plans[0]
            depth+=best.depth
            lines+=best.cleared
            current=future.replay(current,best)[-1].state
            if current.pieces or search.timed_out:
                truncated=True
                break
            completed+=1
        results.append(FutureEvaluation(plan,depth,lines,completed,truncated))
    return tuple(sorted(results,key=lambda r:(r.total_depth,r.total_lines,r.current_plan.value),reverse=True))
