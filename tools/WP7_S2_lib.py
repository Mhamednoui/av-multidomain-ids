"""WP7 S2 shared code: paths, seeds, tick-series helpers (Evidence logs -> the fusion/streams.py tick format with an availability time), and the cross-domain runtime objects
that reproduce the model of the WP6 test packs (sigma models fitted on the DEV clean rows, per-edge ECDF + tie-safe tau on the leave-one-out dev statistics, domain-level blame).
Nothing here chooses or tunes anything: every object is built by the recipe of tools/WP6_stage code that produced the frozen packs (tools/WP6_S3_streams.py stage_cross_kitti /
stage_cross_comma), only the Evidence is produced by the WP7 runners (system/cross_runner.py).
Seeds: SEED = 42 (common.config); S2 streams use [SEED, 77, k, ...] (notes/WP7_system.md "S2 start").
"""
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True

import numpy as np

from common.config import DATA_EXTRA, SEED
from crossdomain import consistency as CS
from fusion import streams as ST
from system.cross_runner import CrossObject

OUT = ROOT / "results" / "WP7"
CACHE = DATA_EXTRA / "cache_v3" / "WP7"
WP6C = DATA_EXTRA / "cache_v3" / "WP6"
LIDAR_DIR = CACHE / "S2_lidar"
BUDGET = 0.01
ONSET = 3                           # attack onset tick of every persistent attack (3 s clean pre-roll)
K_DOMAINS = ["gps", "lidar", "can", "network", "v2x", "cross"]
C_DOMAINS = ["can", "network", "v2x", "cross"]
CACHE.mkdir(parents=True, exist_ok=True)


class FixedOnsetRng:
    """Wraps a numpy Generator; the onset draw of gps.stream.make_run (integers(3, ...)) returns 3, every other call is passed through unchanged."""

    def __init__(self, rng, onset=ONSET):
        self._r, self._on = rng, onset

    def integers(self, low, high=None, *a, **k):
        if low == 3 and high is not None:
            return self._on
        return self._r.integers(low, high, *a, **k)

    def __getattr__(self, name):
        return getattr(self._r, name)


def make_series(group, name, kind, family, score, layers, dom_alarm, layer_alarm, label, t, fam=None, blame=None, count=None, avail=None, **extra):
    """A tick series in the fusion/streams.py format plus dom_alarm / layer_alarm / count / t / avail (availability time of each tick's Evidence, s of the block clock)."""
    s = ST.series(group, name, kind, family, score, layers, label, fam=fam, blame=blame)
    n = len(s["score"])
    s["dom_alarm"] = np.asarray(dom_alarm, bool)
    s["layer_alarm"] = np.asarray(layer_alarm, bool).reshape(n, -1)
    s["count"] = np.ones(n, np.float32) if count is None else np.asarray(count, np.float32)
    s["t"] = np.asarray(t, float)
    s["avail"] = (np.arange(n) + 1.0) if avail is None else np.asarray(avail, float)
    s.update(extra)
    return s


def cross_ticks(evs, t_grid):
    """Cross-domain Evidence list (one per GPS-grid second) -> arrays on the run grid t_grid: score, edge statistics (n, E), alarm, blame (object), present."""
    n, E = len(t_grid), len(evs[0].details["edge_stat"]) if evs else 0
    score = np.zeros(n, np.float32)
    layers = np.zeros((n, E), np.float32)
    alarm = np.zeros(n, bool)
    blame = np.full(n, None, object)
    present = np.zeros(n, bool)
    for e in evs:
        k = int(np.argmin(np.abs(t_grid - e.t)))
        if abs(t_grid[k] - e.t) > 1e-6:
            continue
        score[k], alarm[k], present[k] = e.score, e.alarm, True
        layers[k] = [np.nan_to_num(v, nan=0.0) if v is not None else 0.0 for v in e.details["edge_stat"].values()]
        if e.alarm:
            b = e.details["blamed_domain"]
            blame[k] = "undecided" if b is None else str(b)
    return score, layers, alarm, blame, present


def kitti_cross_object():
    """Sigma models on the DEV clean phase-0 rows, calibration on the leave-one-drive-out dev statistics: exactly the model of tools/WP6_S3_streams.py stage_cross_kitti (test pack)."""
    import WP6_S2_kitti as SK
    import WP6_S2b_eval as B
    edges, runs = B.kitti_runs()
    clean = {g: np.vstack([np.abs(r["Z"]) for r in rs if r["attack"] == "none"]) for g, rs in runs.items()}
    cal = CS.Calibration(BUDGET).fit(np.vstack(list(clean.values())))
    dev = pickle.load(open(WP6C / "s2b_kitti.pkl", "rb"))["rows"]
    models = B.oof_models(dev[(dev["attack"] == "none") & (dev["phase"] == 0)], edges)
    model = CS.WhichDomainLies(edges, SK.DOMAIN_OF, k="inst", budget=BUDGET, tb=None, domain_level=True)
    model.calibration = cal
    return CrossObject(models, model)


def comma_cross_objects():
    """{class: CrossObject} for the comma test routes: per-gyro-class sigma models on the DEV routes, shared calibration (stage_cross_comma, glitch filter OFF as in S5)."""
    import WP6_S2_comma as SC
    import WP6_S2b_eval as B
    edges, data, cls = B.comma_data()
    clean = {n: np.abs(d["Z"]) for n, d in data.items()}
    cal = CS.Calibration(BUDGET).fit(np.vstack(list(clean.values())))
    c2 = pickle.load(open(WP6C / "s2_comma.pkl", "rb"))
    b2 = pickle.load(open(WP6C / "s2b_comma.pkl", "rb"))
    setup = {**b2["setup"], **c2["setup"]}
    clsall = {n: ("g10" if s["gyro_hz"] <= 20 else "g100") for n, s in setup.items()}
    dev_routes = b2["routes"][b2["routes"]["part"].isin(["train", "val"])]
    out = {}
    for k in ("g10", "g100"):
        models = B.oof_models(dev_routes[dev_routes["route"].map(clsall) == k], edges)
        model = CS.WhichDomainLies(edges, SC.DOMAIN_OF, k="inst", budget=BUDGET, tb=None, domain_level=True)
        model.calibration = cal
        out[k] = CrossObject(models, model)
    return out, clsall, setup


def load_pickle(name):
    return pickle.load(open(CACHE / name, "rb"))


def save_pickle(obj, name):
    f = CACHE / name
    pickle.dump(obj, open(f.with_suffix(".tmp"), "wb"), protocol=4)
    f.with_suffix(".tmp").replace(f)
