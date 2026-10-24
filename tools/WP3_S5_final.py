"""WP3 S5 VERDICT run (test touched once): L2b free space / occlusion. Variant from variant_choice.json (chosen on validation).
Threshold = pooled over the 16 train+val clean drives (tie-safe 1 %), nested per-drive LODO FA as spread. Writes results/WP3/S5/final.json.
Harness: L1 + L2a(intensity part, LODO) + L2b on the nine S4 attacks (joined by scan id). Usage: python -u -W ignore tools/WP3_S5_final.py"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS
from common.evaluate import EvalSet, evaluate_domain
from lidar import calibration as C
from lidar import density as D
from lidar import geometry as G
from lidar import occlusion as O
from lidar import occlusion_eval as E
from lidar import s4_eval as E4
from lidar.data import CACHE, FRAME_DT, TEST, VAL, drives_of
from lidar.geometry import STAT_NAMES
from lidar.l1 import L1Union
from lidar.sequence import EPISODE_SCANS, rolling_logodds

RES = RESULTS / "WP3" / "S5"
DRY = bool(os.environ.get("S5_DRY"))      # code-path check on validation drives only (no test data read); writes dry_final.json
if DRY:
    TEST = list(VAL)
ATTK = "att_val" if DRY else "att_test"
ROOT4 = CACHE / "S4" / (json.loads((RESULTS / "WP3" / "S4" / "variant_choice.json").read_text())["variant"] + "_t")
ATT9 = ["ph_replace_near", "ph_replace_far", "ph_budget_near", "ph_budget_far", "PointDrop", "IntensitySpoof", "cmp_boxcloud",
        "cmp_mradd_near", "cmp_mradd_far"]
ATT = ATT9 + E.FL
INT_STATS = ["int_hi", "int_lo", "cnt_int_hi", "cnt_int_lo"]


def windows(by_drive, step):
    return [s[a:a + EPISODE_SCANS] for s in by_drive.values() for a in range(0, len(s) - EPISODE_SCANS + 1, step)]


def tile_level(v, tiles, scans, trval):
    """Phantom tiles (>= 50 % injected returns): share with see-through fraction >= the 99th percentile of the clean-scan maximum fraction
    (the 1 % scan-level threshold of that statistic alone)."""
    fthr = float(np.quantile(trval["maxf"], 0.99))
    f = O.tile_fraction(tiles, v)
    caught = f >= fthr
    ph = tiles.ph_n.to_numpy() >= 0.5 * tiles.n_points.to_numpy()
    out = {"fraction_threshold": fthr}
    for a in ATT:
        sc = set(scans[scans.attack == a].scan)
        m = ph & tiles.scan.isin(sc).to_numpy()
        out[a] = {"n_scans": len(sc), "n_phantom_tiles": int(m.sum()), "scans_with_phantom_tile": int(tiles.scan[m].nunique()),
                  "tile_detection": float(caught[m].mean()) if m.any() else None,
                  "scans_with_caught_phantom_tile": float(tiles.scan[m & caught].nunique() / max(len(sc), 1))}
    return out


def evalset(layers, frames, names):
    df = pd.concat(frames, ignore_index=True)
    ev = {n: layers[n][0].score(layers[n][1](df)) for n in names}
    y = (df.attack != "clean").to_numpy().astype(int)
    return EvalSet(evidence=ev, y=y, attack_type=np.where(y == 1, df.attack, "normal"), group=df.drive.to_numpy(), t=df.idx.to_numpy() * FRAME_DT)


def main():
    t0 = time.time()
    v = tuple(json.loads((RES / "variant_choice.json").read_text())["variant"])
    tr, va = drives_of("train"), drives_of("val")
    alld = list(dict.fromkeys(tr + va + TEST))
    tc, sc = E.load_kind("clean", alld)
    cf = E.frame(tc, sc, v)
    trval, test = cf[cf.drive.isin(tr + va)], cf[cf.drive.isin(TEST)]
    lay = O.L2bUnion().calibrate(trval, 0.01)
    ta, sa = E.load_kind(ATTK, TEST)
    af = E.frame(ta, sa, v)
    out = {"variant": list(v), "threshold": float(lay.threshold), "n_clean_trval": int(len(trval)), "n_clean_test": int(len(test))}
    out["nested_lodo_fa_trval"] = E.nested_lodo_fa(trval, tr + va)
    out["fa_pooled_trval"] = float((E.cal(lay, trval) >= lay.threshold).mean())
    out["fa_test"] = float((E.cal(lay, test) >= lay.threshold).mean())
    out["fa_test_per_drive"] = {d: float(x) for d, x in E.per_drive_fa(lay, test).items()}
    det = E.detection(lay, af)
    out["attacks"] = {a: {"union": float(det[a]), "n": int((af.attack == a).sum())} for a in ATT}
    for s in O.STATS:
        sub = O.L2bUnion([s]).calibrate(trval, 0.01)
        d_ = E.detection(sub, af)
        out.setdefault("stat_fa", {})[s] = float((E.cal(sub, test) >= sub.threshold).mean())
        for a in ATT:
            out["attacks"][a][s] = float(d_[a])
    out["tile_level"] = tile_level(v, ta, sa, trval)
    # episodes
    cal_tv = {d: E.cal(lay, trval[trval.drive == d].sort_values("idx")) for d in tr + va}
    thr = float(np.quantile(np.concatenate([rolling_logodds(w) for w in windows(cal_tv, 10)]), 0.99))
    wt = windows({d: E.cal(lay, test[test.drive == d].sort_values("idx")) for d in TEST}, EPISODE_SCANS)
    te, se = E.load_kind("ep_test", TEST) if not DRY else (ta, sa.assign(ep=0, step=1))
    ef = E.frame(te, se, v)
    ef["cal"] = E.cal(lay, ef)
    ep = {"stat_threshold": thr, "false_episode_rate_test_clean": float(np.mean([(rolling_logodds(w) >= thr).any() for w in wt])),
          "n_clean_windows": len(wt), "kinds": {}}
    for kind, g in (ef.groupby("attack") if not DRY else []):
        res, delays = [], []
        for (d, j), e in g.groupby(["drive", "ep"]):
            hit = np.flatnonzero(rolling_logodds(e.sort_values("step").cal.to_numpy()) >= thr)
            res.append(len(hit) > 0 and hit[0] + 1 <= EPISODE_SCANS)
            if len(hit):
                delays.append((hit[0] + 1) * FRAME_DT)
        ep["kinds"][kind] = {"episodes": len(res), "detected_3s": int(sum(res)), "median_delay_s_of_alarmed": float(np.median(delays)) if delays else None,
                             "single_scan_alarm_rate": float((g.cal >= lay.threshold).mean())}
    out["episodes"] = ep
    # harness: L1 + L2a intensity (LODO) + L2b
    calib = C.load_calib(RESULTS / "WP3" / "S2" / "calibration_beta.npz")
    co, cs = E4.load_kind(ROOT4, "clean", alld)
    dco = cs.set_index("scan")["drive"].loc[co.scan.to_numpy()].to_numpy()
    ao_v, as_v = E4.load_kind(ROOT4, "att_val", VAL)
    ao_t, as_t = E4.load_kind(ROOT4, ATTK, TEST)
    nmin = json.loads((RESULTS / "WP3" / "S4" / "dev.json").read_text())["nmin_chosen"]
    m_v = D.ObjectModel(calib, nmin).fit(co[np.isin(dco, tr)])
    m_l = D.ObjectModel(calib, nmin).fit(co[np.isin(dco, tr + va)])
    oof = E4.lodo_scan_scores(co[np.isin(dco, tr + va)], cs[cs.drive.isin(tr + va)], tr + va, calib, nmin)
    l2a = D.L2aUnion(INT_STATS).calibrate(oof, 0.01)
    l2a.name = "L2a_int"
    l1 = L1Union().calibrate(oof[oof.drive.isin(va)].rename(columns={f"l1_{n}": n for n in STAT_NAMES}), 0.01)
    tv, sv = E.load_kind("att_val", VAL)

    def merge4(f4, f5):
        return f4.merge(f5[["scan"] + O.STATS], on="scan", how="inner")

    cv = merge4(oof[oof.drive.isin(va)].assign(attack="clean"), E.frame(tc, sc, v)[lambda x: x.drive.isin(va)])
    av = merge4(E4.scan_frame(m_v, ao_v, as_v), E.frame(tv, sv, v))
    ct = merge4(E4.scan_frame(m_l, co[np.isin(dco, TEST)], cs[cs.drive.isin(TEST)]).assign(attack="clean"), test.assign(attack="clean"))
    at = merge4(E4.scan_frame(m_l, ao_t, as_t), af)
    layers = {"L1": (l1, lambda d: d.rename(columns={f"l1_{n}": n for n in STAT_NAMES})), "L2a_int": (l2a, lambda d: d), "L2b": (lay, lambda d: d)}
    for n in ("L2b",):
        layers[n][0].name = n
    out["harness"] = {}
    for tag, names in (("harness_L1_L2a_L2b", ["L1", "L2a_int", "L2b"]), ("harness_L1_L2b", ["L1", "L2b"])):
        res = evaluate_domain(tag, evalset(layers, [cv, av], names), evalset(layers, [ct, at], names), wp="WP3", budget=0.01, method="noisy_or", out_dir=RES)
        out["harness"][tag] = {"layers": res["layers"], "ablation": res["ablation"]}
    out["seconds"] = time.time() - t0
    (RES / ("dry_final.json" if DRY else "final.json")).write_text(json.dumps(out, indent=1, default=float))
    print("done", out["seconds"], "FA test", out["fa_test"])


if __name__ == "__main__":
    main()
