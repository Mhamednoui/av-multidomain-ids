"""WP8 S8 step 3c: LiDAR domain rows (M4-8 style) with and without the reference-health gate, from the SAVED S7 per-scan raw scores (no scan is re-scored): clean scan false alarms and detection per attack kind
(operating point alarm, as tools/WP8_S7_domains.py), frozen union thresholds unchanged, pose layers L2c / L2d masked at gated scans. Paired difference gated - ungated with a cluster bootstrap over drives
(B = 2000, seed 31). Gated scans on attack rows are counted as they are (the masked statistic decides; no credit). Labelled: re-used hold-out, exposure 2 (post-M4 fix), NOT fresh.
Output results/WP8/S8/lidar_domain.json. Run: python -u -W ignore tools/WP8_S8_lidar_domain.py"""
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S7_lib as S7

import numpy as np

S7.open_guard()
S7.patch_h31_paths()
from gps import stream as GS
from lidar.domain31 import Domain31
from system import health31 as H


def boot(a, b, n_a, n_b, B=2000, seed=31):
    """a, b: per-drive counts (gated, ungated) of alarms; n_a/n_b per-drive scans. Returns pooled rate diff and a drive-cluster bootstrap 95 % CI."""
    rng = np.random.default_rng(seed)
    d = a.sum() / n_a.sum() - b.sum() / n_b.sum()
    bs = []
    for _ in range(B):
        i = rng.integers(0, len(a), len(a))
        bs.append(a[i].sum() / n_a[i].sum() - b[i].sum() / n_b[i].sum())
    return float(d), [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]


def main():
    lid = pickle.load(open(S7.CACHE / "lidar.pkl", "rb"))
    union = Domain31.load(S7.ROOT / "results" / "WP8" / "S3" / "frozen_lidar31").union
    drives = sorted(lid["drives"])
    rows = {}
    for d in drives:
        f = lid["drives"][d]["frame"]
        t, pa, va = H.read_oxts_health(GS.oxts_dir(d))
        deg = H.degraded_frames(pa, va)
        gs = deg[np.clip(f["i"].to_numpy(int), 0, len(deg) - 1)]
        raw = {l: f["v31_raw_" + l].to_numpy(float) for l in H.LIDAR_LAYERS}
        _, _, al_g = H.mask_union(union, raw, gs)
        al_u = f["v31_alarm"].to_numpy(bool)
        assert np.array_equal(al_u, union.alarm(raw)), d
        rows[d] = (f["kind"].to_numpy(), f["attack"].to_numpy(), al_u, al_g, gs)
    out = {"exposure": "re-used hold-out, exposure 2 (post-M4 fix), NOT fresh", "rows": {}}
    subsets = {"clean scans (FA)": lambda k, a: k == "clean", **{f"{kd}": (lambda kd: (lambda k, a: (k == "att") & (a == kd)))(kd) for kd in lid["kinds"]},
               "ep_PointDrop (episodes)": lambda k, a: k == "pdep"}
    for name, sel in subsets.items():
        n = np.array([sel(rows[d][0], rows[d][1]).sum() for d in drives], float)
        au = np.array([(rows[d][2] & sel(rows[d][0], rows[d][1])).sum() for d in drives], float)
        ag = np.array([(rows[d][3] & sel(rows[d][0], rows[d][1])).sum() for d in drives], float)
        gs_ = np.array([(rows[d][4] & sel(rows[d][0], rows[d][1])).sum() for d in drives], float)
        diff, ci = boot(ag, au, n, n)
        m = np.array([d != "0093" for d in drives])
        out["rows"][name] = {"scans": int(n.sum()), "gated_scans": int(gs_.sum()), "rate_ungated": float(au.sum() / n.sum()), "rate_gated": float(ag.sum() / n.sum()), "paired_diff": diff, "paired_ci": ci,
                             "rate_ungated_excl_0093": float(au[m].sum() / n[m].sum()), "rate_gated_excl_0093": float(ag[m].sum() / n[m].sum()),
                             "per_drive_gated": {d: float(x / y) for d, x, y in zip(drives, ag, n)}}
    import json
    S7.write_json(out, S7.ROOT / "results" / "WP8" / "S8" / "lidar_domain.json")
    for k, v in out["rows"].items():
        print(f"{k:28s} n={v['scans']:5d} gated={v['gated_scans']:4d} ungated {v['rate_ungated']:.4f} gated {v['rate_gated']:.4f} diff {v['paired_diff']:+.4f} {v['paired_ci']} | excl 0093: {v['rate_ungated_excl_0093']:.4f} -> {v['rate_gated_excl_0093']:.4f}")


if __name__ == "__main__":
    main()
