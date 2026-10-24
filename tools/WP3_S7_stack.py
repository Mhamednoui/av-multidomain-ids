"""WP3 S7: per-scan raw scores of the physics layers (L1, L2a intensity, L2c, L2d), L3 and L4 on the same scans (identical seeds in S4 / S6 /
S7), in two modes.
  dev   : models fitted on the 13 train drives; reference = clean validation scans (3 drives); sets = validation attacks.
  final : reference = out-of-fold clean scores of the 16 train+val drives; models fitted on the 16 drives; sets = clean test, test attacks,
          test sensor-fixed episodes (this is the only place where test data is read; call it only from the verdict script).
A frame has the columns scan, drive, idx, attack (+ ep, step for episodes) and raw_<layer>.
"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from WP3_S6_lib import load as s6load, layer as s6layer
from common.config import RESULTS
from lidar import calibration as C
from lidar import density as D
from lidar import learned as L
from lidar import learned_eval as LE
from lidar import learned_l4 as L4
from lidar import s4_eval as E
from lidar.data import CACHE, TEST, VAL, drives_of
from lidar.geometry import STAT_NAMES
from lidar.l1 import L1Union

S4 = RESULTS / "WP3" / "S4"
S6 = RESULTS / "WP3" / "S6"
S7 = RESULTS / "WP3" / "S7"
S4ROOT = CACHE / "S4" / (json.loads((S4 / "variant_choice.json").read_text())["variant"] + "_t")
INT_PARTS = ["int_hi", "int_lo", "cnt_int_hi", "cnt_int_lo"]
MODELS = L4.ROOT / "models"
KEYS = ["scan", "drive", "idx", "attack", "ep", "step"]


def l1_cols(df):
    return df.rename(columns={f"l1_{n}": n for n in STAT_NAMES})


def keep(df, raw, name):
    cols = [c for c in KEYS if c in df.columns]
    return df[cols].assign(**{f"raw_{name}": np.asarray(raw, float)})


def merge(frames):
    """Inner join of single-layer frames on scan (keys of the first)."""
    out = frames[0]
    for f in frames[1:]:
        out = out.merge(f[["scan"] + [c for c in f.columns if c.startswith("raw_")]], on="scan", how="inner")
    return out


def l1_clean_tv(cs):
    """Clean L1 statistics of the 16 train+val drives: train drives from the S7 cache, val drives from the S4 scan tables."""
    tr = [pd.read_pickle(CACHE / "S7" / f"l1_{d}.pkl") for d in drives_of("train")]
    va = cs[cs.drive.isin(drives_of("val"))][["drive", "idx", "scan", "attack"] + [f"l1_{n}" for n in STAT_NAMES]]
    return pd.concat(tr + [va], ignore_index=True)


def physics(mode):
    """Dict of frames {'ref', 'clean', 'att', 'ep'} (ep only in final) with raw_L1, raw_L2a, raw_L2c, raw_L2d."""
    calib = C.load_calib(RESULTS / "WP3" / "S2" / "calibration_beta.npz")
    tr, va = drives_of("train"), drives_of("val")
    tv = tr + va
    nmin = json.loads((S4 / "dev.json").read_text())["nmin_chosen"]
    ch6 = json.loads((S6 / "dev.json").read_text())["choice"]
    co, cs = E.load_kind(S4ROOT, "clean", tv + TEST)
    dco = cs.set_index("scan")["drive"].loc[co.scan.to_numpy()].to_numpy()
    out = {}
    if mode == "dev":
        m = D.ObjectModel(calib, nmin).fit(co[np.isin(dco, tr)])
        ref4 = E.scan_frame(m, co[np.isin(dco, va)], cs[cs.drive.isin(va)])
        sets4 = {"att": E.scan_frame(m, *E.load_kind(S4ROOT, "att_val", VAL))}
        l1_ref = ref4
        s6clean = s6load("clean", tv)
        s6sets = {"att": s6load("att_val", VAL)}
        refname, ref_drives = "ref", va
    else:
        oof = E.lodo_scan_scores(co[np.isin(dco, tv)], cs[cs.drive.isin(tv)], tv, calib, nmin)
        m = D.ObjectModel(calib, nmin).fit(co[np.isin(dco, tv)])
        ref4 = oof
        sets4 = {"clean": E.scan_frame(m, co[np.isin(dco, TEST)], cs[cs.drive.isin(TEST)]),
                 "att": E.scan_frame(m, *E.load_kind(S4ROOT, "att_test", TEST)),
                 "ep": E.scan_frame(m, *E.load_kind(S4ROOT, "ep_test", TEST))}
        l1_ref = l1_clean_tv(cs)
        s6clean = s6load("clean", tv)
        s6sets = {"clean": s6load("clean", TEST), "att": s6load("att_test", TEST), "ep": s6load("ep_test", TEST)}
        ref_drives = tv
    a2 = D.L2aUnion(INT_PARTS).calibrate(ref4)
    l1 = L1Union().calibrate(l1_cols(l1_ref))
    l2c, l2d = (s6layer(lid, ch6[lid]["stats"], s6clean) for lid in ("L2c", "L2d"))

    def frame(df4, df6):
        f = merge([keep(df4, a2.raw_scores(df4), "L2a"), keep(df6, l2c.raw_scores(df6), "L2c"), keep(df6, l2d.raw_scores(df6), "L2d")])
        f1 = keep(df4, l1.raw_scores(l1_cols(df4)), "L1")
        return merge([f1, f])

    out["ref"] = frame(ref4, s6clean[s6clean.drive.isin(ref_drives)])
    # L1 on the reference: the reference scans (val clean in dev; tv clean in final) need L1 statistics of all their drives
    if mode == "final":
        l1f = keep(l1_ref, l1.raw_scores(l1_cols(l1_ref)), "L1")
        out["ref"] = out["ref"].drop(columns=["raw_L1"]).merge(l1f[["scan", "raw_L1"]], on="scan", how="inner")
    for k, d4 in sets4.items():
        out[k] = frame(d4, s6sets[k])
    return out


def add_l3(frames, mode):
    """raw_L3 on every frame. dev: model fitted on the train drives (re-fit, deterministic); final: final model + out-of-fold reference."""
    ch = json.loads((S7 / "dev_l3.json").read_text())["choice"]
    feats = L.BASE_FEATS + (L.TRK_FEATS if ch["features"] == "base+track" else [])
    if mode == "dev":
        tr, va = drives_of("train"), drives_of("val")
        Ftr, _ = LE.load_l3("clean", tr)
        m = L.NormalModel(ch["model"]).fit(Ftr[feats].to_numpy())
        Fv, Sv = LE.load_l3("clean", va)
        ref_l3 = L.scan_frame(m, Fv[feats].to_numpy(np.float32), Fv["scan"].astype(str).to_numpy(), Sv)
        src = {"att": ("att_val", VAL)}
    else:
        with open(MODELS / "l3_final.pkl", "rb") as fh:
            m = pickle.load(fh)["model"]
        ref_l3 = pd.read_pickle(MODELS / "oof_l3.pkl")
        src = {"clean": ("clean", TEST), "att": ("att_test", TEST), "ep": ("ep_test", TEST)}
    lay = L.make_layer(ref_l3)
    frames["ref"] = frames["ref"].merge(keep(ref_l3, lay.raw_scores(ref_l3), "L3")[["scan", "raw_L3"]], on="scan", how="inner")
    for k, (kind, ds) in src.items():
        F, S = LE.load_l3(kind, ds)
        fr = L.scan_frame(m, F[feats].to_numpy(np.float32), F["scan"].astype(str).to_numpy(), S)
        frames[k] = frames[k].merge(keep(fr, lay.raw_scores(fr), "L3")[["scan", "raw_L3"]], on="scan", how="inner")
    return frames


def add_l4(frames, mode, name="l4", model=None):
    """raw_<NAME> (score 1 - P(Normal)) on every frame. dev: `model` fitted on train drives is given; final: cached final model + OOF reference."""
    col = "raw_" + name.upper()
    if mode == "dev":
        ref_rows = L4.normal_rows(drives_of("val"))
        sets = {"att": ("ev", VAL)}
        score = lambda X: L4.attack_score(model, X)  # noqa
        ref = ref_rows[0].assign(**{col: score(ref_rows[1])})
    else:
        with open(MODELS / f"{name}_final.pkl", "rb") as fh:
            model = pickle.load(fh)
        score = lambda X: L4.attack_score(model, X)  # noqa
        ref = pd.read_pickle(MODELS / f"oof_{name}.pkl").rename(columns={"raw": col})
        nm, nx = L4.normal_rows(TEST)
        clean = nm.assign(**{col: score(nx)})
        sets = {"att": ("ev", TEST), "ep": ("ep", TEST)}
        frames["clean"] = frames["clean"].merge(clean[["scan", col]], on="scan", how="inner")
    frames["ref"] = frames["ref"].merge(ref[["scan", col]], on="scan", how="inner")
    for k, (kind, ds) in sets.items():
        zs = [pd.read_pickle(L4.ROOT / f"l4_{kind}_{d}.pkl") for d in ds]
        meta, X = pd.concat([z["meta"] for z in zs], ignore_index=True), np.vstack([z["X"] for z in zs])
        fr = meta[["scan"]].assign(**{col: score(X)})
        frames[k] = frames[k].merge(fr, on="scan", how="inner")
    return frames
