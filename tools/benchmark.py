"""Synthetic solver timings only; no claim of real Shopee recognition accuracy."""
import json
import random
import statistics
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine.game_state import GameState,Piece
from solver.beam_search import BeamSolver
from engine.simulator import apply_move

def run():
    rng=random.Random(23)
    samples=[]
    for density in (0.0,0.2,0.4,0.6,0.8):
        for trial in range(4):
            board=sum(1<<i for i in range(64) if rng.random()<density)
            pieces=(Piece("A",((0,0),(0,1),(0,2))),Piece("B",((0,0),(1,0),(1,1))),Piece("C",((0,0),(0,1),(1,0),(1,1))))
            state=GameState(8,board,pieces)
            solver=BeamSolver()
            result=solver.solve(state)
            for plan in result.plans:
                steps=solver.replay(state,plan)
                assert steps[-1].state.board==plan.final_board
            samples.append({"density":density,"ms":round(result.elapsed_ms,2),"explored":result.explored,
                            "depth":result.depth,"plans":len(result.plans),"timed_out":result.timed_out})
    times=sorted(s["ms"] for s in samples)
    report={"source":"20 synthetic seeded boards, n=8, width=100, budget=0.8s",
            "median_ms":statistics.median(times),"p95_ms":times[int(0.95*len(times))-1],
            "max_ms":max(times),"timeouts":sum(s["timed_out"] for s in samples),"samples":samples,
            "vision_accuracy":"Not measured: no labeled real-game screenshots supplied.",
            "solver_quality":"Legal replay checked. Weights untuned; no optimality guarantee."}
    out=Path(__file__).resolve().parents[1]/"artifacts"
    out.mkdir(exist_ok=True)
    (out/"benchmark.json").write_text(json.dumps(report,indent=2),encoding="utf8")
    print(json.dumps({k:v for k,v in report.items() if k!="samples"},indent=2))
if __name__=="__main__": run()
