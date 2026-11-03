"""WP8 S3: freeze the v3.1 LiDAR domain (lidar/domain31.py) and save the per-scan scores (rule 6) of the selected configuration on V31_val.
Reads results/WP8/S3/selection_<tag>.json (chosen config), the records (results/WP8/S3/parts) and frame.pkl.
Frozen domain: layer references = the leave-one-drive-out clean statistics of all 23 V31 train + validation drives; intensity model on all 23 drives;
combiner budgets as selected. Output results/WP8/S3/frozen_lidar31/ (domain31.pkl, ~6 MB) and results/WP8/scores/S3/lidar_val.npz:
for every V31_val scan (clean, attacked, PointDrop episodes): drive, scan index, kind, attack, episode, step, the four layer raw scores, the stack
statistic, alarm, for the selected configuration (leave-one-drive-out) and for the v3 rule M0|all4 (same OOF protocol).
Run: python -u -W ignore tools/WP8_S3_freeze.py [--tag r3] [--name <candidate name>]"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S3_an as A
import WP8_S3_lib as L
from lidar import geometry as G
from lidar.domain31 import Domain31

OUT = L.ROOT / "results" / "WP8" / "S3"


def cfg_by_name(tag, name):
    return [c for c in A.candidates(tag) if c["name"] == name][0]


def lodo_scores(frame, cfg):
    """Per-scan layer raw, stack statistic and alarm of all V31_val scans (clean, att, pdep) for cfg, leave-one-drive-out."""
    parts = []
    for d in L.VAL:
        st, ref = A.fit_fold(frame, [d], cfg)
        fr = frame[(frame.drive == d) & ((frame.kind != "clean") | (frame.i >= 1))]
        raw = A.layer_raw(ref, fr, st.cs, st.as_)
        df = fr[["kind", "drive", "i", "attack", "ep", "step"]].copy()
        for l in A.LAYERS:
            df[f"raw_{l}"] = raw[l]
        df["stat"] = st.stat(raw)
        df["score"] = st.score(raw)
        df["alarm"] = df["stat"] >= 0.0
        parts.append(df)
    return pd.concat(parts, ignore_index=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="r3")
    ap.add_argument("--name", default=None)
    a = ap.parse_args()
    sel = json.loads((OUT / f"selection_{a.tag}.json").read_text())
    name = a.name or sel["chosen"]
    cfg = cfg_by_name(a.tag, name)
    frame = pd.read_pickle(OUT / "frame.pkl")
    # ---- scores (rule 6)
    s_new, s_v3 = lodo_scores(frame, cfg), lodo_scores(frame, cfg_by_name(a.tag, "M0|all4"))
    z = {}
    for tag, df in (("v31", s_new), ("v3rule", s_v3)):
        for c in ("raw_L1", "raw_L2a", "raw_L2c", "raw_L2d", "stat", "score", "alarm"):
            z[f"{tag}_{c}"] = df[c].to_numpy()
    z["drive"] = s_new.drive.astype(str).to_numpy()
    z["i"] = s_new.i.to_numpy()
    z["kind"] = s_new.kind.astype(str).to_numpy()
    z["attack"] = s_new.attack.astype(str).to_numpy()
    z["ep"] = s_new.ep.fillna(-1).to_numpy()
    z["step"] = s_new.step.fillna(-1).to_numpy()
    z["label"] = (s_new.kind != "clean").to_numpy().astype(int)
    z["group"] = np.array([f"{d}/{i}" for d, i in zip(s_new.drive, s_new.i)])
    L.SCORES.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(L.SCORES / "lidar_val.npz", **z)
    print("scores", len(s_new), "->", L.SCORES / "lidar_val.npz")
    # ---- frozen domain on all 23 drives
    cs, as_ = A.C_OPTIONS[cfg["c"]], A.A_SETS[cfg["a"]]
    st, ref = A.fit_fold(frame, [], cfg)
    stats = set(L.L1_KEYS) | set(as_) | set(cs) | set(A.LAYER_STATS["L2d"])
    stat_ref = {k: ref[k].to_numpy(float) for k in stats}
    parts = A.load_parts(("clean",))
    tiles = pd.concat([parts[("clean", d)]["tiles"] for d in L.DRIVES], ignore_index=True)
    iref = A.IntensityRef(tiles)
    st.ref_frame = None
    meta = {"version": "v3.1 S3", "config": name, "cfg": {k: (list(v) if isinstance(v, tuple) else v) for k, v in cfg.items()},
            "reference_drives": L.DRIVES, "reference_scans": int(len(ref)), "prm": L.PRM,
            "fit": "clean V31 train + validation drives only; no attack label in any fitted object; budgets chosen on V31_val (notes/WP8_v31.md S3)"}
    dom = Domain31(L.table(), L.PRM, iref, stat_ref, st, cs, meta, a_stats=as_)
    dom.save(OUT / "frozen_lidar31")
    (OUT / "frozen_lidar31" / "domain31.json").write_text(json.dumps(dict(meta, budgets=[float(b) for b in np.atleast_1d(st.budgets)],
                                                                          tau=[float(t) for t in st.tau]), indent=1))
    print("frozen", name, "budgets", st.budgets, "tau", st.tau)


if __name__ == "__main__":
    main()
