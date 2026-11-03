"""WP8 S6: channel-level hypothesis blame (crossdomain/blame31.py): single fault, colluding pair resolved by inertial edges, ties, persistence, new rule == v3 where the cross layer is silent."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from crossdomain import blame31 as B  # noqa: E402


def _state(graph, alarm=(), agree=()):
    st = np.full(len(graph.edges), -1, np.int8)
    for e in alarm:
        st[graph.edges.index(e)] = 1
    for e in agree:
        st[graph.edges.index(e)] = 0
    return st


def test_single_gps_fault_on_kitti_graph():
    g = B.graph_k(False)
    bl = B.Blame31(g, B.EQUAL_COST)
    st = _state(g, alarm=[("gps_v", "lidar_v"), ("gps_v", "can_v"), ("gps_lat", "lidar_lat")], agree=[("lidar_v", "can_v"), ("compass", "gyro")])
    assert bl.diagnose(st)[0] == "gps"


def test_lone_lidar_speed_fault_and_colluding_pair_without_inertial_edge():
    g = B.graph_k(False)
    st = _state(g, alarm=[("gps_v", "lidar_v"), ("lidar_v", "can_v")], agree=[("gps_v", "can_v"), ("gps_lat", "lidar_lat"), ("compass", "gyro")])
    assert B.Blame31(g, B.EQUAL_COST).diagnose(st)[0] == "lidar"
    assert B.Blame31(g, B.PRIOR_COST).diagnose(st)[0] == "lidar"       # the physics of three speed sources is symmetric; the prior alone does not flip it


def test_inertial_edges_resolve_gps_can_against_lone_lidar():
    g = B.graph_k(True)
    bl = B.Blame31(g, B.PRIOR_COST)
    base = dict(alarm=[("gps_v", "lidar_v"), ("lidar_v", "can_v")], agree=[("gps_v", "can_v"), ("gps_lat", "lidar_lat"), ("compass", "gyro")])
    lone_lidar = _state(g, alarm=base["alarm"] + [("lidar_v", "ins_v")], agree=base["agree"] + [("gps_v", "ins_v"), ("can_v", "ins_v")])
    coll = _state(g, alarm=base["alarm"] + [("gps_v", "ins_v"), ("can_v", "ins_v")], agree=base["agree"] + [("lidar_v", "ins_v")])
    assert bl.diagnose(lone_lidar)[0] == "lidar"
    assert bl.diagnose(coll)[0] in ("gps", "can")


def test_comma_position_channel_fault_is_decided_and_two_channel_tie_needs_the_prior():
    g = B.graph_c()
    pos = _state(g, alarm=[("gnss_pos", "can_v"), ("gnss_pos", "wheel_v")], agree=[("gnss_vel", "can_v"), ("gnss_vel", "wheel_v"), ("can_v", "wheel_v")])
    assert B.Blame31(g, B.EQUAL_COST).diagnose(pos)[0] == "gps"
    tie = _state(g, alarm=[("gnss_vel", "can_v"), ("gnss_vel", "wheel_v"), ("gnss_pos", "can_v"), ("gnss_pos", "wheel_v")], agree=[("can_v", "wheel_v")])
    assert B.Blame31(g, B.EQUAL_COST).diagnose(tie)[0] == B.UNDECIDED
    assert B.Blame31(g, B.PRIOR_COST).diagnose(tie)[0] == "gps"
    yaw = _state(g, alarm=[("gnss_vel", "can_v"), ("gnss_vel", "wheel_v"), ("gnss_pos", "can_v"), ("gnss_pos", "wheel_v"), ("gnss_yaw", "gyro")], agree=[("can_v", "wheel_v")])
    assert B.Blame31(g, B.EQUAL_COST).diagnose(yaw)[0] == "gps"


def test_can_fault_and_no_alarm():
    g = B.graph_c()
    can = _state(g, alarm=[("gnss_vel", "can_v"), ("gnss_pos", "can_v"), ("can_v", "wheel_v")], agree=[("gnss_vel", "wheel_v"), ("gnss_pos", "wheel_v")])
    assert B.Blame31(g, B.PRIOR_COST).diagnose(can)[0] == "can"
    assert B.Blame31(g, B.PRIOR_COST).diagnose(_state(g, agree=[("can_v", "wheel_v")]))[0] is None


def test_persistence_filter_and_cross_alarm_without_persistent_edge():
    al = np.zeros((8, 2), bool)
    al[2, 0] = True
    al[4:7, 1] = True
    ob = np.ones_like(al)
    st = B.persist_states(al, ob)
    assert st[2, 0] == -1 and st[3, 0] == -1 and st[0, 0] == 0          # one alarm: no constraint; none: agree
    assert st[5, 1] == 1 and st[6, 1] == 1 and st[7, 1] == 1             # >= 2 of the last 5
    g = B.graph_c()
    bl = B.Blame31(g, B.PRIOR_COST)
    a = np.zeros((6, len(g.edges)), bool)
    a[3, 0] = True
    out = B.blame_run(bl, a, np.ones_like(a), a.any(axis=1))
    assert out[3] == B.UNDECIDED and out[0] is None


def test_new_rule_is_silent_without_cross_alarm():
    g = B.graph_c()
    bl = B.Blame31(g, B.PRIOR_COST)
    a = np.zeros((10, len(g.edges)), bool)
    assert all(x is None for x in B.blame_run(bl, a, np.ones_like(a), np.zeros(10, bool)))


def test_inertial_model_flags_a_ramp_and_not_a_clean_run():
    rng = np.random.default_rng(0)
    runs = []
    for _ in range(12):
        n = 40
        v = 8 + np.cumsum(rng.normal(0, 0.05, n))
        A = np.r_[0.0, np.diff(v)]
        speed = np.column_stack([v + rng.normal(0, 0.4, n), v + rng.normal(0, 0.2, n), v + rng.normal(0, 0.3, n)])
        runs.append((speed, A))
    m = B.InertialModel().fit(runs)
    speed, A = runs[0]
    alarm = np.zeros(len(speed), bool)
    alarm[20:30] = True
    al, ob = m.edges(speed, A, alarm)
    assert ob[22:30].all() and al.sum() < 4
    s2 = speed.copy()
    s2[:, 0] += np.minimum(np.arange(len(s2)) * 0.4, 6.0)
    al2, _ = m.edges(s2, A, alarm)
    assert al2[26:30, 0].all() and not al2[26:30, 1:].any()


def test_speed_spoof_with_agreeing_yaw_edge_is_not_contradicted():
    g = B.graph_c()
    st = _state(g, alarm=[("gnss_vel", "can_v"), ("gnss_vel", "wheel_v"), ("gnss_pos", "can_v"), ("gnss_pos", "wheel_v")], agree=[("can_v", "wheel_v"), ("gnss_yaw", "gyro")])
    assert B.Blame31(g, B.PRIOR_COST).diagnose(st)[0] == "gps"
    only_doppler = _state(g, alarm=[("gnss_vel", "can_v"), ("gnss_vel", "wheel_v")], agree=[("can_v", "wheel_v"), ("gnss_pos", "can_v"), ("gnss_pos", "wheel_v"), ("gnss_yaw", "gyro")])
    assert B.Blame31(g, B.EQUAL_COST).diagnose(only_doppler)[0] == "gps"      # a superset with a spurious second sensor does not block the verdict
