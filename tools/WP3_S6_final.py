"""WP3 S6 VERDICT run (test touched once): L2c background model + L2d tracking.
Reads dev.json (statistics per union chosen on validation), thresholds from the pooled clean train+val scans (1 %, tie-safe) and
their leave-one-drive-out check, then scores test attacks, persistent episodes (sensor-fixed and world-fixed) and runs the harness
ablation on top of L1 + L2a(intensity). Writes results/WP3/S6/final.json (+ harness_*.json/md).
Usage: python -u -W ignore tools/WP3_S6_final.py"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from WP3_S6_lib import *  # noqa
from common.config import RESULTS
from common.evaluate import EvalSet, evaluate_domain
from lidar import calibration as C
from lidar import density as D
from lidar import s4_eval as E
from lidar.geometry import STAT_NAMES
from lidar.l1 import L1Union

RES = RESULTS / "WP3" / "S6"
S4 = RESULTS / "WP3" / "S4"
S4ROOT = CACHE / "S4" / (json.loads((S4 / "variant_choice.json").read_text())["variant"] + "_t")
INT_PARTS = ["int_hi", "int_lo", "cnt_int_hi", "cnt_int_lo"]


def l1_cols(df):
    return df.rename(columns={f"l1_{n}": n for n in STAT_NAMES})


def layer_report(L, lid, clean_tv, clean_t, att_t, ep_t, epw_t, stats):
    r = {"stats": stats, "threshold": float(L.threshold), "fa_test": float(alarm(L, clean_t).mean()),
         "fa_test_per_drive": {d: float(alarm(L, g).mean()) for d, g in clean_t.groupby("drive")},
         "lodo_fa_trainval": lodo_fa(lid, stats, clean_tv)}
    r["attacks"] = {a: float(alarm(L, att_t[att_t.attack == a]).mean()) for a in ATT}
    r["parts_fa"], r["parts_det"] = {}, {}
    for s in stats:
        Ls = layer(lid, [s], clean_tv)
        r["parts_fa"][s] = float(alarm(Ls, clean_t).mean())
        r["parts_det"][s] = {a: float(alarm(Ls, att_t[att_t.attack == a]).mean()) for a in ATT}
    thr = episode_threshold(L, clean_tv)
    wt = windows(L, clean_t, EPISODE_SCANS)
    r["episodes"] = {"stat_threshold": thr, "false_episode_rate_test_clean": float(np.mean([(rolling_logodds(w) >= thr).any() for w in wt])),
                     "n_clean_windows": len(wt)}
    for tag, ep in (("sensor_fixed", ep_t), ("world_fixed", epw_t)):
        mv = ep.groupby(["drive", "ep", "attack"]).disp.transform("mean") > 0.5
        r["episodes"][tag] = episode_table(L, ep, thr)
        r["episodes"][tag + "_ego_moving"] = episode_table(L, ep[mv], thr)
        r["episodes"][tag + "_ego_slow"] = episode_table(L, ep[~mv], thr) if (~mv).any() else {}
    return r


def evalset(layers, frames, names):
    df = pd.concat(frames, ignore_index=True)
    ev = {n: layers[n][0].score(layers[n][1](df)) for n in names}
    y = (df.attack != "clean").to_numpy().astype(int)
    return EvalSet(evidence=ev, y=y, attack_type=np.where(y == 1, df.attack, "normal"), group=df.drive.to_numpy(), t=df.idx.to_numpy() * FRAME_DT)


def main():
    t0 = time.time()
    dev = json.loads((RES / "dev.json").read_text())
    ch = dev["choice"]
    clean_tv = load("clean", TRAINVAL)
    clean_t, att_t = load("clean", TEST), load("att_test", TEST)
    ep_t, epw_t = load("ep_test", TEST), load("epw_test", TEST)
    out = {"choice": ch, "layers": {}}
    lays = {}
    for lid in ("L2c", "L2d"):
        st = ch[lid]["stats"]
        lays[lid] = layer(lid, st, clean_tv)
        out["layers"][lid] = layer_report(lays[lid], lid, clean_tv, clean_t, att_t, ep_t, epw_t, st)
        print(lid, "FA", out["layers"][lid]["fa_test"], flush=True)

    # harness on top of L1 + L2a(intensity) (S4 tables, same attacked scans: identical seeds)
    calib = C.load_calib(RESULTS / "WP3" / "S2" / "calibration_beta.npz")
    tr, va = drives_of("train"), drives_of("val")
    nmin = json.loads((S4 / "dev.json").read_text())["nmin_chosen"]
    co, cs = E.load_kind(S4ROOT, "clean", tr + va + TEST)
    dco = cs.set_index("scan")["drive"].loc[co.scan.to_numpy()].to_numpy()
    ao_v, as_v = E.load_kind(S4ROOT, "att_val", VAL)
    ao_t, as_t = E.load_kind(S4ROOT, "att_test", TEST)
    m_l = D.ObjectModel(calib, nmin).fit(co[np.isin(dco, tr + va)])
    oof = E.lodo_scan_scores(co[np.isin(dco, tr + va)], cs[cs.drive.isin(tr + va)], tr + va, calib, nmin)
    a2 = D.L2aUnion(INT_PARTS).calibrate(oof)
    a2.name = "L2a_int"
    l1v = L1Union().calibrate(l1_cols(cs[cs.drive.isin(va)]))
    mine_clean = pd.concat([clean_tv, clean_t]).drop(columns=["drive", "idx", "attack"])
    mine_att = pd.concat([load("att_val", VAL), att_t]).drop(columns=["drive", "idx", "attack"])
    lays["L2c"].name, lays["L2d"].name = "L2c", "L2d"

    def frame(base, mine):
        return base.merge(mine, on="scan", how="inner")

    cl_v = frame(oof[oof.drive.isin(va)].assign(attack="clean"), mine_clean)
    cl_t = frame(E.scan_frame(m_l, co[np.isin(dco, TEST)], cs[cs.drive.isin(TEST)]).assign(attack="clean"), mine_clean)
    at_v = frame(E.scan_frame(m_l, ao_v, as_v), mine_att)
    at_t = frame(E.scan_frame(m_l, ao_t, as_t), mine_att)
    layers = {"L1": (l1v, l1_cols), "L2a_int": (a2, lambda d: d), "L2c": (lays["L2c"], lambda d: d), "L2d": (lays["L2d"], lambda d: d)}
    for tag, names in (("harness_L1_L2a_int", ["L1", "L2a_int"]), ("harness_full", ["L1", "L2a_int", "L2c", "L2d"])):
        res = evaluate_domain(tag, evalset(layers, [cl_v, at_v], names), evalset(layers, [cl_t, at_t], names), wp="WP3", budget=0.01,
                              method="noisy_or", out_dir=RES)
        out[tag] = {"layers": res["layers"], "ablation": res["ablation"]}
    t1 = time.time()
    from lidar import background_build as BB
    from lidar import geometry as G
    from lidar import background as B
    from lidar import ego
    from lidar.data import load as ld, scan_files
    table = G.RingTable.load(RESULTS / "WP3" / "S2" / "ring_table.json")
    edges, f, pose = B.ring_edges(table), scan_files("0011"), ego.poses("0011")
    t2 = time.time()
    for i in range(10, 30):
        BB.pair_row(ld(f[i - 1]), pose[i - 1], ld(f[i]), pose[i], edges)
    out["scoring_ms_per_scan"] = 1000 * (time.time() - t2) / 20
    out["seconds"] = time.time() - t0
    (RES / "final.json").write_text(json.dumps(out, indent=1, default=float))
    print("done", out["seconds"])


if __name__ == "__main__":
    main()
