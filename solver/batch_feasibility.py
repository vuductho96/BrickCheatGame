"""Bounded exhaustive batch feasibility, with witnesses and honest unknowns.

Inspired by the feasibility/robustness separation in zacharygoh/block-blast-solver:
https://github.com/zacharygoh/block-blast-solver/tree/main/packages/core/src
Independent Python implementation using this project's rules and arbitrary shapes.
"""
from dataclasses import dataclass
from functools import lru_cache
from engine.game_rules import placements,clear_lines

@dataclass(frozen=True)
class BatchWitness:
    status: str  # feasible, impossible, unknown (node cap)
    board: int
    cleared: int
    steps: tuple  # (original piece index, row, col)
    nodes: int

@lru_cache(maxsize=12000)
def feasible_batch(board,size,shapes,node_cap=4000):
    options=tuple(placements(size,s) for s in shapes)
    failed=set();nodes=0;capped=False
    def visit(current,left):
        nonlocal nodes,capped
        if not left:return current,0,()
        key=(current,tuple(sorted(shapes[i] for i in left)))
        if key in failed:return None
        choices=[];seen=set()
        for i in left:
            if shapes[i] in seen:continue
            seen.add(shapes[i])
            valid=[(r,c,m) for r,c,m in options[i] if not current&m]
            if valid:choices.append((len(valid),i,valid))
        # Try constrained pieces first, but try all orders: a clear can unlock
        # a currently unplaceable piece, so zero anchors is not a death proof.
        for _,i,valid in sorted(choices):
            rest=tuple(j for j in left if j!=i)
            successors=[]
            for r,c,mask in valid:
                after,rows,cols=clear_lines(current|mask,size)
                successors.append((len(rows)+len(cols),-after.bit_count(),r,c,after))
            for clears,_,r,c,after in sorted(successors,reverse=True):
                if nodes>=node_cap:
                    capped=True;return None
                nodes+=1
                result=visit(after,rest)
                if result:
                    final,lines,path=result
                    return final,lines+clears,((i,r,c),)+path
                if capped:return None
        failed.add(key)
        return None
    result=visit(board,tuple(range(len(shapes))))
    if result:
        final,lines,path=result
        return BatchWitness('feasible',final,lines,path,nodes)
    return BatchWitness('unknown' if capped else 'impossible',board,0,(),nodes)
