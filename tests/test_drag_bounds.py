"""Whole-sprite limits, including measured cross-axis touch response."""
import numpy as np
import pytest
from drag_servo import DragServo


@pytest.mark.parametrize("shape",[(1,1),(3,2),(3,3),(5,5)])
def test_every_predicted_correction_keeps_whole_shape_inside_board(shape):
    rng=np.random.default_rng(442)
    lower=np.array([46.,640.])
    size=np.array(shape)*np.array([123.5,123.75])
    upper=lower+np.array([988.,990.])-size
    servo=DragServo(lower,(123.5,123.75))
    servo.jacobian=np.array([[.8,.17],[-.12,1.3]])
    for _ in range(300):
        visual=rng.uniform(lower,upper)
        delta=rng.uniform(-500,500,2)
        bounded=servo.bound_delta(delta,visual,lower,upper)
        predicted=visual+servo.jacobian@bounded
        assert np.all(predicted>=lower-1e-8)
        assert np.all(predicted+size<=lower+[988,990]+1e-8)


def test_edge_probe_points_inward_and_outside_sprite_returns_inside():
    servo=DragServo((0,0),(100,100))
    assert servo.bound_delta((2,0),(600,600),(0,0),(600,600))==(0.,0.)
    assert servo.bound_delta((-2,0),(600,600),(0,0),(600,600))==(-2.,0.)
    assert servo.bound_delta((0,0),(650,700),(0,0),(600,600))==(-50.,-100.)


@pytest.mark.parametrize("gain",[.4,1.,1.7,2.4])
@pytest.mark.parametrize("corner",[(0,0),(0,1),(1,0),(1,1)])
def test_unknown_response_never_crosses_edges_while_converging(gain,corner):
    lower=np.array([46.,640.]);upper=np.array([787.,1382.5])
    target=np.array([upper[i] if corner[i] else lower[i] for i in range(2)])
    visual=(lower+upper)/2;pointer=visual+np.array([229.,440.])
    servo=DragServo(target,(123.5,123.75))
    for _ in range(14):
        delta=servo.observe(pointer,visual,1.)
        bounded=np.array(servo.bound_delta(delta,visual,lower,upper,overshoot=2.5))
        pointer+=bounded;visual+=gain*bounded
        assert np.all(visual>=lower-1e-8) and np.all(visual<=upper+1e-8)
    assert np.max(np.abs(visual-target)/servo.cell)<.22


def test_phone_servo_does_not_invent_cross_axis_response_from_lagged_frames():
    # Recorded first trial: tiny/lagged motions previously skewed the 2D model.
    pointers=[(476.5,1433.125),(346.1,1549.425),(299.9,1594.8),(268.53,1603.37),
              (254.95,1599.99),(243.22,1596.49),(232.16,1592.97)]
    poses=[(372,968),(200,1116),(140,1170),(93,1178),(78,1174),(76,1175),(62,1163)]
    servo=DragServo((46,1258.75),(123.5,123.75),diagonal=True)
    for p,v in zip(pointers,poses):delta=servo.observe(p,v,1.)
    assert servo.jacobian[0,1]==servo.jacobian[1,0]==0
    bounded=servo.bound_delta(delta,poses[-1],(46,640),(787,1258.75),overshoot=2.5)
    # Even an underestimated direct gain of 2.5 cannot move the sprite out.
    actual=np.array(poses[-1])+2.5*np.array(bounded)
    assert actual[0]>=46 and actual[1]<=1258.75


def test_bad_diagonal_gain_estimate_cannot_spend_all_actual_edge_clearance():
    servo=DragServo((46,1258.75),(123.5,123.75),diagonal=True)
    servo.jacobian=np.diag([.3,.4])
    visual=np.array([62.,1230.])
    delta=np.linalg.solve(servo.jacobian,servo.target-visual)
    bounded=servo.bound_delta(delta,visual,(46,640),(787,1258.75),overshoot=2.5)
    for gain in (.3,1.,2.5):
        actual=visual+gain*np.array(bounded)
        assert actual[0]>=46 and actual[1]<=1258.75
