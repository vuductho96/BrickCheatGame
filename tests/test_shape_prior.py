import random
from engine.game_rules import placements
from solver.shape_prior import SHAPES,legal_count,future_features
from solver.heuristics import Weights,evaluate


def test_bit_parallel_count_matches_enumeration_including_disconnected_shapes():
    rng=random.Random(872)
    for size in (3,5,8):
        for _ in range(15):
            board=sum(1<<i for i in range(size*size) if rng.random()<.45)
            for cells in SHAPES:
                assert legal_count(board,size,cells)==sum(not board&mask for _,_,mask in placements(size,cells))


def test_reserve_values_large_usable_space_over_same_empty_count_scattered():
    # Same 16 free cells: a 4x4 reserve versus isolated checkerboard pockets.
    reserve=sum(1<<(r*8+c) for r in range(4) for c in range(4))
    scattered=sum(1<<(r*8+c) for r in range(0,8,2) for c in range(0,8,2))
    full=(1<<64)-1
    good=future_features(full^reserve,8);bad=future_features(full^scattered,8)
    assert good[0]>bad[0] and good[1]>bad[1]


def test_zero_new_weights_preserve_baseline_evaluation():
    from solver.heuristics import features
    board=0x123456789
    w=Weights();empty,mobility,holes,fragmented=features(board,8)
    assert evaluate(board,8,2,w)==w.cleared*2+w.empty*empty+w.mobility*mobility-w.holes*holes-w.fragmentation*fragmented


def test_removing_cells_cannot_reduce_future_coverage_or_options():
    rng=random.Random(22)
    for _ in range(40):
        board=rng.getrandbits(64);reduced=board&rng.getrandbits(64)
        before=future_features(board,8);after=future_features(reduced,8)
        assert all(a>=b for a,b in zip(after,before))
