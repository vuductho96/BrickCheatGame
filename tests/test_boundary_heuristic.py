import random
from solver.heuristics import boundary_edges

def test_corners_and_row_wrap_are_counted_correctly():
    assert boundary_edges(0,8)==0
    assert boundary_edges((1<<64)-1,8)==0
    assert boundary_edges(1,8)==2
    assert boundary_edges(1<<(3*8+3),8)==4
    assert boundary_edges((1<<7)|(1<<8),8)==5

def test_bitboard_boundary_matches_cell_adjacencies():
    rng=random.Random(152)
    for size in (3,4,8,16):
        for _ in range(30):
            board=rng.randrange(1<<(size*size))
            expected=sum(((board>>(r*size+c))&1)!=((board>>(rr*size+cc))&1)
                         for r in range(size) for c in range(size)
                         for rr,cc in ((r+1,c),(r,c+1)) if rr<size and cc<size)
            assert boundary_edges(board,size)==expected
