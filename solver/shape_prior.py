"""Broad local prior, not a prediction of the game's random generator.

Bit intersections count legal anchors, including disconnected/diagonal pieces.
Equal shape weights avoid assuming that early, easy trays persist forever.
"""
from functools import lru_cache
from math import log1p


def orientations(cells):
    result=set()
    for mirror in (1,-1):
        current=tuple((r,c*mirror) for r,c in cells)
        for _ in range(4):
            r0=min(r for r,c in current);c0=min(c for r,c in current)
            result.add(tuple(sorted((r-r0,c-c0) for r,c in current)))
            current=tuple((c,-r) for r,c in current)
    return result


def catalog():
    shapes=set()
    for length in range(1,6):
        shapes.update(orientations(tuple((0,c) for c in range(length))))
    for h,w in ((2,2),(2,3),(3,3)):
        shapes.update(orientations(tuple((r,c) for r in range(h) for c in range(w))))
    for seed in (
        ((0,0),(1,0),(1,1)),
        ((0,0),(1,0),(2,0),(2,1)),
        ((0,0),(1,0),(2,0),(2,1),(2,2)),
        ((0,0),(0,1),(0,2),(1,1)),
        ((0,0),(0,1),(1,1),(1,2)),
        ((0,1),(1,0),(1,1),(1,2),(2,1)),
        ((0,0),(1,1),(2,2)),
        ((0,0),(0,2),(1,0),(1,1),(1,2)),
    ):
        shapes.update(orientations(seed))
    return tuple(sorted(shapes))


SHAPES=catalog()


@lru_cache(maxsize=4096)
def anchor_mask(size,cells):
    h=max(r for r,c in cells)+1;w=max(c for r,c in cells)+1
    return sum(1<<(r*size+c) for r in range(size-h+1) for c in range(size-w+1))


def legal_count(board,size,cells):
    free=((1<<(size*size))-1)^board
    anchors=anchor_mask(size,cells)
    for r,c in cells:
        anchors &= free>>(r*size+c)
        if not anchors:return 0
    return anchors.bit_count()


@lru_cache(maxsize=50000)
def future_features(board,size):
    counts=[legal_count(board,size,shape) for shape in SHAPES]
    # Coverage prevents trading the last slot of a hard shape for many easy slots.
    # Logarithms reward alternatives, with diminishing returns on plentiful slots.
    return sum(n>0 for n in counts)/len(counts),sum(log1p(n) for n in counts)/len(counts)
