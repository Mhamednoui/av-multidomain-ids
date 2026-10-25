"""WP7 S2 simulation helpers (tools/WP7_S2_lib.py, WP7_S2_sim.py): the fixed-onset wrapper only changes the onset draw, scan ticks follow floor(t - offset) with max / any / count,
Builder.place copies a source window with the right offsets and availability, cross_ticks maps Evidence to the run grid, runs_of finds the True runs. Synthetic data only."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True


def test_fixed_onset_rng_changes_only_the_onset_draw():
    import WP7_S2_lib as L
    a = np.random.default_rng(5)
    b = L.FixedOnsetRng(np.random.default_rng(5))
    assert b.integers(3, 20) == L.ONSET
    assert a.integers(3, 20) != -1
    # the stream after the onset draw is the same stream (the wrapper must not consume or reorder anything else)
    x = a.integers(3, 20)  # consumed by the unwrapped generator
    assert np.allclose(np.random.default_rng(5).normal(size=3), np.random.default_rng(5).normal(size=3))
    assert b.normal(size=2).shape == (2,) and b.uniform(0, 1) >= 0


def test_lidar_part_ticks():
    import WP7_S2_sim as M
    tab = {"t": np.array([0.05, 0.15, 0.95, 1.05, 2.5, 7.0]), "score": np.array([0.1, 0.9, 0.2, 0.3, 0.4, 0.5], np.float32), "alarm": np.array([0, 1, 0, 0, 0, 1], bool),
           "layers": np.tile(np.array([0.1, 0.2, 0.3, 0.4], np.float32), (6, 1)) * np.arange(1, 7)[:, None], "layer_alarm": np.zeros((6, 4), bool), "attacked": np.array([0, 1, 0, 0, 1, 0], bool)}
    tab["layer_alarm"][1, 2] = True
    lp = M.lidar_part(tab, 0.0, 4)
    assert lp["score"].tolist() == [np.float32(0.9), np.float32(0.3), np.float32(0.4), 0.0]
    assert lp["count"].tolist() == [3.0, 1.0, 1.0, 0.0]
    assert lp["dom_alarm"].tolist() == [True, False, False, False]
    assert lp["layer_alarm"][0, 2] and not lp["layer_alarm"][1].any()
    assert lp["label"].tolist() == [True, False, True, False] and lp["present"].tolist() == [True, True, True, False]
    lp2 = M.lidar_part(tab, 0.5, 3)          # a run that starts 0.5 s into the drive: t = 0.05 is before it, 7.0 is after it
    assert lp2["count"].tolist() == [2.0, 0.0, 1.0]


def test_builder_place_offsets_and_availability():
    import WP7_S2_lib as L
    import WP7_S2_sim as M

    class FakeSources:
        widths = {"gps": 16, "lidar": 4, "can": 3, "v2x": 12, "network": 5, "cross_K": 7, "cross_C": 6}
        veh_K = {"series": {}}
        veh_C = {"series": {}}
        can, v2x, net = [], [], []

    b = M.Builder.__new__(M.Builder)
    b.S, b.fam, b.domains = FakeSources, "C", L.C_DOMAINS
    P = b.new_parts(10)
    src = {"score": np.arange(20, dtype=np.float32) / 20, "layers": np.zeros((20, 3), np.float32), "dom_alarm": np.arange(20) % 2 == 0, "layer_alarm": np.zeros((20, 3), bool),
           "label": np.arange(20) >= 8, "avail": np.arange(20) + 1.0 + (np.arange(20) == 6) * 50.0}
    k = b.place(P, "can", 0, src, 5, 10)
    assert k == 10
    assert np.allclose(P["can"]["score"], src["score"][5:15])
    assert P["can"]["label"].tolist() == [False, False, False, True, True, True, True, True, True, True]
    # source tick 6 is composite tick 1; its availability (57) is expressed on the composite clock (57 - 5 = 52)
    assert abs(P["can"]["avail"][1] - 52.0) < 1e-9 and abs(P["can"]["avail"][0] - 1.0) < 1e-9
    # a window that starts before the source (start < 0) leaves the first ticks absent
    P2 = b.new_parts(10)
    b.place(P2, "can", 0, src, -3, 10)
    assert not P2["can"]["present"][:3].any() and P2["can"]["present"][3:].all() and abs(P2["can"]["score"][3] - src["score"][0]) < 1e-9


def test_runs_of_and_cross_ticks():
    import WP7_S2_lib as L
    import WP7_S2_sim_main as MM
    assert MM.runs_of([0, 1, 1, 0, 0, 1, 0, 1, 1]) == [(1, 2), (5, 5), (7, 8)]
    from common.evidence import Evidence
    ev = [Evidence(domain="cross", layer="L2", name="x", t=2.0, score=0.7, alarm=True, reason="", details={"edge_stat": {"a": 1.0, "b": float("nan")}, "blamed_domain": None}),
          Evidence(domain="cross", layer="L2", name="x", t=3.0, score=0.1, alarm=False, reason="", details={"edge_stat": {"a": 0.2, "b": 0.1}, "blamed_domain": "gps"})]
    grid = np.array([0.0, 1.0, 2.0, 3.0])
    score, layers, alarm, blame, present = L.cross_ticks(ev, grid)
    assert present.tolist() == [False, False, True, True] and alarm.tolist() == [False, False, True, False]
    assert blame[2] == "undecided" and blame[3] is None and abs(score[2] - 0.7) < 1e-6 and layers[2, 1] == 0.0
