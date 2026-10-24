"""WP6 S5b stage 1: LiDAR tick pack of the FROZEN LiDAR domain (lidar/domain.py, results/WP3/S9/frozen_lidar) for the M2 addendum.

Inputs (read only): the WP3 S9 raw layer score stores ../data_extra/cache_v3/WP3/S9/dev_frames.pkl (validation: ref = out-of-fold clean scans of the
16 train+val drives, att = val attacks, epw = val world-fixed episodes) and final_frames_s9.pkl (test: clean, att, ep, epw; frozen layers), the frozen
domain (Stack + per-layer calibrators / thresholds) and the OXTS timestamps of every scan (gps.stream.load_oxts).
Per scan: combined score = Stack ECDF of the max-rank statistic, combined alarm = stat >= Stack threshold, per-layer score = layer calibrator(raw),
per-layer alarm = score >= layer threshold (= LidarDomain.score_scan, checked by a replay of raw test scans: `check`).
Ticks (1 s): tick = floor(OXTS time of the scan); value = max over the scans of the second; own alarm = any scan alarm in the second.
Validation pack also holds "calib_series": clean series of the 13 TRAIN drives (WP3 S9 out-of-fold reference scans), used only to calibrate the LiDAR entry
(S5b round 2, lidar_cal = "trainval"); they never enter a composite or a fold.
Series (fusion/streams.py format, + dom_alarm, layer_alarm, count, t): clean per drive; per-scan attacks (every 3rd scan attacked, WP3 S4 design) 4 series per drive
and kind with onset ~ U[0, n/2) (rng [SEED, 66, 30, drive]); persistent episodes (30 scans): one series per episode (ep_* sensor-fixed test only, epW_* world-fixed).
Plan: notes/WP6_crossdomain.md "S5b start". Usage: python -u -W ignore tools/WP6_S5b_lidar.py [build check]
Output: ../data_extra/cache_v3/WP6/s5b_lidar.pkl
"""
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.config import DATA_EXTRA, SEED  # noqa: E402
from fusion import streams as ST  # noqa: E402

CACHE = DATA_EXTRA / "cache_v3" / "WP6"
S9C = DATA_EXTRA / "cache_v3" / "WP3" / "S9"
FROZEN = ROOT / "results" / "WP3" / "S9" / "frozen_lidar"
LAYERS = ("L1", "L2a", "L2c", "L2d")
LAYER_NAMES = ["lidar.l1_geometry", "lidar.l2a_intensity", "lidar.l2c_background", "lidar.l2d_tracking"]
PER_SCAN = ["ph_replace_near", "ph_budget_near", "ph_replace_far", "ph_budget_far", "PointDrop", "IntensitySpoof"]
COMPARISON = ["cmp_boxcloud", "cmp_mradd_near", "cmp_mradd_far"]
REPS = 4
VAL, TEST = ["0011", "0027", "0035"], ["0001", "0005", "0028", "0039", "0052", "0079", "0095"]


def log(*a):
    print(*a, flush=True)


def load_domain():
    from lidar.domain import LidarDomain
    return LidarDomain.load(FROZEN)


def scan_scores(dom, df):
    """df with raw_L1, raw_L2a, raw_L2c, raw_L2d -> dict(comb (N,), comb_alarm (N,), layers (N, 4), layer_alarm (N, 4), stat (N,))."""
    cols = pd.DataFrame({f"raw_{x}": df[f"raw_{x}"].to_numpy(float) for x in LAYERS})
    st = dom.stack.stat(cols)
    lay = np.column_stack([dom.layers[x].calibrator.transform(cols[f"raw_{x}"].to_numpy(float)) for x in LAYERS])
    thr = np.array([dom.layers[x].threshold for x in LAYERS])
    return {"stat": st, "comb": dom.stack.cal.transform(st), "comb_alarm": st >= dom.stack.threshold, "layers": lay, "layer_alarm": lay >= thr[None, :]}


def scan_times(d):
    from gps.stream import load_oxts
    return np.asarray(load_oxts(d)["t"], float)


def tick_series(k, sc, n):
    """per-scan scores (dict of scan_scores) at tick indices k -> tick arrays."""
    return {"score": ST.tick_max(k, sc["comb"], n), "layers": ST.tick_max(k, sc["layers"], n), "dom_alarm": ST.tick_any(k, sc["comb_alarm"], n),
            "layer_alarm": np.column_stack([ST.tick_any(k, sc["layer_alarm"][:, j], n) for j in range(len(LAYERS))]),
            "count": np.bincount(k, minlength=n)[:n].astype(np.float32)}


def make_series(d, name, kind, family, tk, label, t):
    s = ST.series(d, name, kind, family, tk["score"], tk["layers"], label)
    s.update(dom_alarm=tk["dom_alarm"], layer_alarm=tk["layer_alarm"], count=tk["count"], t=t)
    return s


def mix(clean_sc, att_sc, pos):
    """clean per-scan scores with the scans at positions pos replaced by att_sc rows."""
    out = {k: v.copy() for k, v in clean_sc.items()}
    for k in out:
        out[k][pos] = att_sc[k]
    return out


def drive_series(dom, d, clean, att, eps, rng):
    ts = scan_times(d)
    c = clean[clean.drive == d].sort_values("idx").reset_index(drop=True)
    idx = c["idx"].to_numpy(int)
    k = np.floor(ts[idx] - ts[0]).astype(int)
    n = int(k.max()) + 1
    t_tick = np.arange(n, dtype=float)
    csc = scan_scores(dom, c)
    pos_of = {int(i): j for j, i in enumerate(idx)}
    out = [make_series(d, f"{d}/clean", "clean", "none", tick_series(k, csc, n), np.zeros(n, bool), t_tick)]
    a = att[att.drive == d]
    for kind in PER_SCAN + COMPARISON:
        ak = a[a.attack == kind].sort_values("idx")
        ak = ak[ak["idx"].isin(pos_of)]
        if not len(ak):
            continue
        asc = scan_scores(dom, ak)
        apos = np.array([pos_of[int(i)] for i in ak["idx"]])
        for rep in range(REPS):
            k0 = int(rng.integers(0, max(1, n // 2)))
            sel = k[apos] >= k0
            tk = tick_series(k, mix(csc, {x: v[sel] for x, v in asc.items()}, apos[sel]), n)
            out.append(make_series(d, f"{d}/{kind}/r{rep}", "attack", kind, tk, t_tick >= k0, t_tick))
    for kind, e in eps:
        ed = e[e.drive == d]
        for (kd, ep), g in ed.groupby(["attack", "ep"], sort=True):
            g = g[g["idx"].isin(pos_of)].sort_values("idx")
            if not len(g):
                continue
            esc = scan_scores(dom, g)
            epos = np.array([pos_of[int(i)] for i in g["idx"]])
            tk = tick_series(k, mix(csc, esc, epos), n)
            lab = np.zeros(n, bool)
            lab[np.unique(k[epos])] = True
            out.append(make_series(d, f"{d}/{kd}/e{ep}", "attack", kd, tk, lab, t_tick))
    return out


def build():
    dom = load_domain()
    dev = pickle.load(open(S9C / "dev_frames.pkl", "rb"))
    fin = pickle.load(open(S9C / "final_frames_s9.pkl", "rb"))
    packs = {}
    for part, drives, clean, att, eps in (("val", VAL, dev["ref"], dev["att"], [("epw", dev["epw"])]),
                                          ("test", TEST, fin["clean"], fin["att"], [("ep", fin["ep"]), ("epw", fin["epw"])])):
        p = {"domain": "lidar", "layer_names": LAYER_NAMES, "layer_thr": np.array([dom.layers[x].threshold for x in LAYERS]), "dom_thr": float(dom.stack.threshold),
             "status": "FROZEN LiDAR domain (WP3 S9, lidar/domain.py): max of L1, L2a intensity, L2c, L2d ranks, 1% scan budget", "series": [],
             "per_scan_families": PER_SCAN, "comparison_families": COMPARISON}
        for d in drives:
            p["series"] += drive_series(dom, d, clean, att, eps, np.random.default_rng([SEED, 66, 30, int(d)]))
        if part == "val":                    # S5b round 2: clean calibration-only series of the 13 TRAIN drives (out-of-fold ref scans; never in a composite or fold)
            p["calib_series"] = []
            for d in sorted(set(dev["ref"].drive) - set(VAL) - set(TEST)):
                p["calib_series"] += drive_series(dom, d, dev["ref"], dev["att"].iloc[:0], [], None)
            log("calib series", len(p["calib_series"]), "ticks", sum(len(x["score"]) for x in p["calib_series"]))
        kinds = pd.Series([s["family"] for s in p["series"]]).value_counts().to_dict()
        log(part, "series", len(p["series"]), "ticks", sum(len(s["score"]) for s in p["series"]), kinds)
        packs[part] = p
    pickle.dump(packs, open(CACHE / "s5b_lidar.pkl", "wb"))
    log("saved", CACHE / "s5b_lidar.pkl")


def check(drive="0052", n_scans=6):
    """Replay of raw test scans through LidarDomain.stream() == the vectorised scores of the stored raw layer scores (combined score, alarm, per-layer)."""
    from lidar import ego
    from lidar.data import load, scan_files
    dom = load_domain()
    fin = pickle.load(open(S9C / "final_frames_s9.pkl", "rb"))
    c = fin["clean"][fin["clean"].drive == drive].set_index("idx")
    files, pose = scan_files(drive), ego.poses(drive)
    s = dom.stream()
    worst = 0.0
    for i in range(n_scans):
        comb, per = s.push(load(files[i]), pose[i], float(i), i)
        if i == 0:
            continue
        sc = scan_scores(dom, c.loc[[i]].reset_index())
        diffs = [abs(comb.score - sc["comb"][0])] + [abs(per[x].score - sc["layers"][0, j]) for j, x in enumerate(LAYERS)]
        assert comb.alarm == bool(sc["comb_alarm"][0]) and all(per[x].alarm == bool(sc["layer_alarm"][0, j]) for j, x in enumerate(LAYERS))
        worst = max(worst, max(diffs))
    assert worst < 1e-9, worst
    log("replay check", drive, n_scans - 1, "scans: max diff", worst)
    return worst


if __name__ == "__main__":
    for st in sys.argv[1:] or ["check", "build"]:
        {"build": build, "check": check}[st]()
