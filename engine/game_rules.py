from dataclasses import dataclass
from functools import lru_cache

@dataclass(frozen=True)
class Rules:
    """Provisional standard rules: no rotation, simultaneous row/column clears."""
    points_per_cell: int = 1
    points_per_line: int = 10
    def __post_init__(self):
        if any(type(v) is not int or v < 0 for v in (self.points_per_cell,self.points_per_line)):
            raise ValueError("Scoring weights must be nonnegative integers")

@lru_cache(maxsize=16)
def line_masks(size):
    return (tuple(((1<<size)-1) << (r*size) for r in range(size)),
            tuple(sum(1 << (r*size+c) for r in range(size)) for c in range(size)))

@lru_cache(maxsize=4096)
def placements(size,cells):
    height,width=max(r for r,c in cells)+1,max(c for r,c in cells)+1
    return tuple((r,c,sum(1 << ((r+dr)*size+c+dc) for dr,dc in cells))
                 for r in range(size-height+1) for c in range(size-width+1))

def clear_lines(board,size):
    rows,cols=line_masks(size)
    full_rows=tuple(i for i,m in enumerate(rows) if board&m==m)
    full_cols=tuple(i for i,m in enumerate(cols) if board&m==m)
    remove=0
    for i in full_rows: remove |= rows[i]
    for i in full_cols: remove |= cols[i]
    return board & ~remove, full_rows, full_cols
