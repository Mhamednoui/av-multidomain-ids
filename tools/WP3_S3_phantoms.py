"""WP3 S3: how single-return ray-cast phantoms (calibrated generator) and the box cloud appear in the object table.
Validation drives, every 12th scan, bands near/far, modes add (== replace) and budget_add (== budget). For each attacked scan the
phantom points are located in the segmentation: share of phantom points in the main object, object centre vs phantom centre,
purity (phantom points / object points). Writes results/WP3/S3/phantom_appearance.json (+ .md in S3_tables)."""
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.config import RESULTS
from lidar import calibration as C
from lidar import geometry as G
from lidar import phantom as P
from lidar import segment as S
from lidar import singlereturn as SR
from lidar.data import VAL, load, scan_files
from lidar.features import apply_attack
from lidar.raycast import eval_params
from WP3_S3_build import params

RES = RESULTS / "WP3" / "S3"
S2 = RESULTS / "WP3" / "S2"
TABLE = G.RingTable.load(S2 / "ring_table.json")
STRIDE = 12


def one(args):
    d, i = args
    prm = params()
    calib = C.load_calib(S2 / f"calibration_{json.loads((S2 / 'calib_choice.json').read_text())['variant']}.npz")
    rng = np.random.default_rng([61, int(d), i])
    pts = load(scan_files(d)[i])
    rays = P.prepare(pts, TABLE)
    real_tab = S.segment(pts, TABLE, prm)
    rows = []
    cases = []
    for band in ("near", "far"):
        p = eval_params(rng, band)
        for mode in ("add", "budget_add"):
            att, n, q, idx = P.phantom(pts, rays, p, rng, mode, calib)
            cases.append((f"ray_{mode}", band, att, idx, P.box_pose(pts, q)[0], n))
        pb = dict(p, n=int(rng.integers(150, 1500)))
        att = SR.enforce_appended(pts, apply_attack("GhostCluster", pts, pb, rng), TABLE)
        az = np.radians(pb["az"])
        c = np.array([pb["range"] * np.cos(az), pb["range"] * np.sin(az)])
        # box cloud points are the appended ones after enforcement: the last n rows
        cases.append(("boxcloud", band, att, np.arange(len(att) - pb["n"], len(att)) if len(att) >= pb["n"] else np.arange(0), c, pb["n"]))
    for kind, band, att, idx, c, n in cases:
        if len(idx) == 0:
            continue
        tab, lab, _ = S.segment(att, TABLE, prm, return_labels=True)
        pl = lab[idx]
        in_obj = pl[pl >= 0]
        row = dict(drive=d, i=i, kind=kind, band=band, n_phantom=int(len(idx)), seg_frac=float(len(in_obj) / len(idx)))
        if len(in_obj):
            main = np.bincount(in_obj).argmax()
            o = tab.iloc[main]
            row.update(main_share=float((pl == main).mean()), n_objects=int(len(np.unique(in_obj))),
                       dist_centre=float(np.hypot(o.cx - c[0], o.cy - c[1])), purity=float((pl == main).sum() / o.n_points),
                       obj_n=int(o.n_points), obj_len=float(o.length), obj_wid=float(o.width), obj_h=float(o.height),
                       obj_rings=int(o.n_rings), obj_az_span=float(o.az_span), obj_int=float(o.int_mean), obj_range=float(o.range),
                       carlike=bool(o.carlike))
        rows.append(row)
    return rows


def main():
    jobs = [(d, i) for d in VAL for i in range(1, len(scan_files(d)), STRIDE)]
    with Pool(4) as pool:
        rows = [r for out in pool.imap_unordered(one, jobs) for r in out]
    df = pd.DataFrame(rows)
    df["one"] = (df.get("main_share", 0) >= 0.6) & (df.get("dist_centre", 99) <= 2.0)
    df["one_pure"] = df["one"] & (df["purity"] >= 0.8)
    df["one_merged"] = df["one"] & (df["purity"] < 0.8)
    df["split"] = df["main_share"].fillna(0) < 0.6
    out = {}
    for (k, b), g in df.groupby(["kind", "band"]):
        out[f"{k}|{b}"] = {"n": int(len(g)), "median_phantom_points": float(g.n_phantom.median()),
                           "segmented_frac": float(g.seg_frac.median()), "one_object": float(g.one.mean()),
                           "one_pure": float(g.one_pure.mean()), "one_merged_with_real": float(g.one_merged.mean()),
                           "split_or_absent": float(g.split.mean()), "median_obj_points": float(g.obj_n.median()),
                           "median_len": float(g.obj_len.median()), "median_width": float(g.obj_wid.median()),
                           "median_rings": float(g.obj_rings.median()), "carlike_frac": float(g.carlike.mean())}
    (RES / "phantom_appearance.json").write_text(json.dumps(out, indent=1))
    df.to_pickle(RES / "phantom_rows.pkl")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
