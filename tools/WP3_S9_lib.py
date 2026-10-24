"""WP3 S9 shared code: per-scan raw scores of the headline layers (L1, L2a intensity, L2a with density, L2c, L2d) on the dev (validation) and
final (test) score stores. Same pipeline and seeds as tools/WP3_S7_stack.py (copied, plus the density variant L2aF and the world-fixed episodes).
  dev   : layers fitted on the 13 train drives; frames: ref (= the out-of-fold clean reference of the 16 train+val drives, no test data), att (val attacks), epw (val world-fixed episodes).
  final : ref = ref16; frames clean / att / ep / epw of the test drives (the only place where test data is read).
A frame has the columns scan, drive, idx, attack (+ ep, step) and raw_<layer>."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP3_S7_stack as ST
from WP3_S6_lib import load as s6load, layer as s6layer
from common.config import RESULTS
from lidar import calibration as C
from lidar import density as D
from lidar import s4_eval as E
from lidar.data import CACHE, TEST, VAL, drives_of
from lidar.l1 import L1Union

S4, S6 = ST.S4, ST.S6
S9C = CACHE / "S9"
INT_PARTS = ST.INT_PARTS
TV = drives_of("train") + drives_of("val")
HEAD = ["raw_L1", "raw_L2a", "raw_L2c", "raw_L2d"]
HEAD_DENS = ["raw_L1", "raw_L2aF", "raw_L2c", "raw_L2d"]
l1_cols, keep, merge = ST.l1_cols, ST.keep, ST.merge


def load_epw(split, drives):
    """World-fixed episode tables of the S4 format (scans with L1 statistics + tiles), built by tools/WP3_S9_build_epw.py."""
    zs = [pd.read_pickle(S9C / f"epw_{split}_{d}.pkl") for d in drives]
    tiles = pd.concat([z["tiles"] for z in zs], ignore_index=True)
    tiles["ring_min"], tiles["ring_max"], tiles["az_span"] = 0.0, 7.0, 2.0 - 0.1728
    return tiles, pd.concat([z["scans"] for z in zs], ignore_index=True)


def fit_layers(mode, with_test=False):
    """Fit everything the headline layers need (clean train+val data only; test tables are only loaded when with_test, for scoring).
    dev: object model on the 13 train drives; final: on the 16 train+val drives. Returns a dict of the fitted objects and the clean tables."""
    calib = C.load_calib(RESULTS / "WP3" / "S2" / "calibration_beta.npz")
    tr, va = drives_of("train"), drives_of("val")
    nmin = json.loads((S4 / "dev.json").read_text())["nmin_chosen"]
    ch6 = json.loads((S6 / "dev.json").read_text())["choice"]
    co, cs = E.load_kind(ST.S4ROOT, "clean", TV + (TEST if with_test else []))
    dco = cs.set_index("scan")["drive"].loc[co.scan.to_numpy()].to_numpy()
    s6clean = s6load("clean", TV)
    oof = E.lodo_scan_scores(co[np.isin(dco, TV)], cs[cs.drive.isin(TV)], TV, calib, nmin)
    l1_ref = ST.l1_clean_tv(cs)
    m = D.ObjectModel(calib, nmin).fit(co[np.isin(dco, tr if mode == "dev" else TV)])
    return {"calib": calib, "nmin": nmin, "model": m, "oof": oof, "l1_ref": l1_ref, "s6clean": s6clean, "co": co, "cs": cs, "dco": dco,
            "l1": L1Union().calibrate(l1_cols(l1_ref)),
            "l2c": s6layer("L2c", ch6["L2c"]["stats"], s6clean), "l2d": s6layer("L2d", ch6["L2d"]["stats"], s6clean),
            "a2": D.L2aUnion(INT_PARTS).calibrate(oof), "a2f": D.L2aUnion(D.ALL_STATS).calibrate(oof), "ch6": ch6}


def make_frame(F):
    """frame(df4, df6) -> per-scan raw scores of the layers fitted in F (df4: S4 scan frame with L1 / tile statistics, df6: S6 statistics)."""
    def frame(df4, df6):
        f1 = keep(df4, F["l1"].raw_scores(l1_cols(df4)), "L1")
        fa = merge([keep(df4, F["a2"].raw_scores(df4), "L2a"), keep(df4, F["a2f"].raw_scores(df4), "L2aF"),
                    keep(df6, F["l2c"].raw_scores(df6), "L2c"), keep(df6, F["l2d"].raw_scores(df6), "L2d")])
        return merge([f1, fa])
    return frame


def ref_frame(F):
    """Out-of-fold clean reference frame of the 16 train+val drives (no test data)."""
    f1 = keep(F["l1_ref"], F["l1"].raw_scores(l1_cols(F["l1_ref"])), "L1")
    r = make_frame(F)(F["oof"], F["s6clean"])
    return r.drop(columns=["raw_L1"]).merge(f1[["scan", "raw_L1"]], on="scan", how="inner")


def physics(mode):
    """dict of frames. dev: ref, att, epw. final: ref, clean, att, ep, epw (ref identical in both modes)."""
    F = fit_layers(mode, with_test=(mode == "final"))
    m, oof, l1_ref, s6clean, co, cs, dco = F["model"], F["oof"], F["l1_ref"], F["s6clean"], F["co"], F["cs"], F["dco"]
    l1, l2c, l2d, a2, a2f = F["l1"], F["l2c"], F["l2d"], F["a2"], F["a2f"]
    if mode == "dev":
        sets4 = {"att": E.scan_frame(m, *E.load_kind(ST.S4ROOT, "att_val", VAL))}
        sets6 = {"att": s6load("att_val", VAL)}
        epw4, epw6 = (E.scan_frame(m, *load_epw("val", VAL)), s6load("epw_val", VAL)) if all((S9C / f"epw_val_{d}.pkl").exists() for d in VAL) else (None, None)
    else:
        sets4 = {"clean": E.scan_frame(m, co[np.isin(dco, TEST)], cs[cs.drive.isin(TEST)]),
                 "att": E.scan_frame(m, *E.load_kind(ST.S4ROOT, "att_test", TEST)),
                 "ep": E.scan_frame(m, *E.load_kind(ST.S4ROOT, "ep_test", TEST))}
        sets6 = {"clean": s6load("clean", TEST), "att": s6load("att_test", TEST), "ep": s6load("ep_test", TEST)}
        epw4, epw6 = (E.scan_frame(m, *load_epw("test", TEST)), s6load("epw_test", TEST))
    frame = make_frame(F)
    out = {"ref": ref_frame(F)}
    for k, d4 in sets4.items():
        out[k] = frame(d4, sets6[k])
    if epw4 is not None:
        out["epw"] = frame(epw4, epw6)
    return out
