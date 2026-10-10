from dataclasses import dataclass
from functools import lru_cache
from engine.game_rules import placements
from .shape_prior import future_features

@dataclass(frozen=True)
class Weights:
    """Untuned baseline; benchmark before claiming optimal play."""
    cleared: float = 12.0
    empty: float = 1.0
    mobility: float = 0.15
    holes: float = 4.0
    fragmentation: float = 2.0
    coverage: float = 0.0
    options: float = 0.0
    boundary: float = 0.0


# Selected on paired unlimited simulations. A broad shape prior supplements
# current-tray search; it does not reveal future random pieces.
CLASSIC_WEIGHTS=Weights(cleared=20,empty=1,mobility=.2,holes=6,
                       fragmentation=3,coverage=45,options=12)

SURVIVAL_WEIGHTS=Weights(cleared=10,empty=1.5,mobility=.15,holes=6,
                        fragmentation=3,coverage=45,options=12,boundary=.35)
COMPACT_WEIGHTS=Weights(cleared=20,empty=1,mobility=.2,holes=6,
                       fragmentation=3,coverage=45,options=12,boundary=.7)

@lru_cache(maxsize=50000)
def boundary_edges(board,size):
    # Count internal filled/empty edges once. Compact clusters and walls leave
    # usable areas; equal empty counts can hide very different fragmentation.
    horizontal=sum(((1<<(size-1))-1)<<(r*size) for r in range(size))
    vertical=(1<<(size*(size-1)))-1
    return ((board^(board>>1))&horizontal).bit_count()+((board^(board>>size))&vertical).bit_count()

@lru_cache(maxsize=50000)
def features(board,size):
    empty=size*size-board.bit_count()
    unseen={i for i in range(size*size) if not (board>>i)&1}
    regions,holes=0,0
    while unseen:
        regions+=1
        stack=[unseen.pop()]
        count=0
        while stack:
            i=stack.pop()
            count+=1
            r,c=divmod(i,size)
            for rr,cc in ((r-1,c),(r+1,c),(r,c-1),(r,c+1)):
                j=rr*size+cc
                if 0<=rr<size and 0<=cc<size and j in unseen:
                    unseen.remove(j)
                    stack.append(j)
        if count<=2: holes+=count
    shapes=(((0,0),(0,1),(0,2)),((0,0),(1,0),(2,0)),
            ((0,0),(0,1),(1,0),(1,1)),tuple((r,c) for r in range(3) for c in range(3)))
    mobility=sum(sum(not board&mask for r,c,mask in placements(size,s)) for s in shapes)
    return empty,mobility,holes,max(0,regions-1)

def evaluate(board,size,cleared,weights=Weights()):
    empty,mobility,holes,fragmented=features(board,size)
    value=weights.cleared*cleared+weights.empty*empty+weights.mobility*mobility-weights.holes*holes-weights.fragmentation*fragmented
    if weights.boundary:value-=weights.boundary*boundary_edges(board,size)
    if weights.coverage or weights.options:
        coverage,options=future_features(board,size)
        value+=weights.coverage*coverage+weights.options*options
    return value
