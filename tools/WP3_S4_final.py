"""WP3 S4 VERDICT run (test touched once): L2a density / intensity per object.
Reads dev.json (nmin, primary threshold mode chosen on validation), builds the models, scores clean test scans, attack tables, episodes,
runs the harness ablation (L1, L2a parts) and writes results/WP3/S4/final.json. Usage: python -u -W ignore tools/WP3_S4_final.py"""
import json
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
from lidar import s4_eval as E
from lidar.data import CACHE, FRAME_DT, TEST, VAL, drives_of
from lidar.geometry import STAT_NAMES
from lidar.l1 import L1Union
from lidar.sequence import EPISODE_SCANS, rolling_logodds

RES = RESULTS / "WP3" / "S4"
ROOT = CACHE / "S4" / (json.loads((RES / "variant_choice.json").read_text())["variant"] + "_t")
ATT = ["ph_replace_near", "ph_replace_far", "ph_budget_near", "ph_budget_far", "PointDrop", "IntensitySpoof", "cmp_boxcloud", "cmp_mradd_near",
       "cmp_mradd_far"]
OBJ_ATT = [a for a in ATT if a.startswith("ph_") or a.startswith("cmp_")]
PARTS = D.ALL_STATS


def l1_cols(df):
    return df.rename(columns={f"l1_{n}": n for n in STAT_NAMES})


def object_level(layer, model, tiles_, scans):
    """Tile level for the injected-return attacks: phantom tiles = tiles with >= 50 % injected returns. Reports the share of attacked scans
    with at least one phantom tile, the tile-level detection rate, and the share of scans in which a phantom tile is at or above the threshold."""
    of = E.object_frame(model, tiles_)
    of["caught"] = layer.calibrator.transform(E.object_raw(layer, of)) >= layer.threshold
    ph = of[of.ph_n >= 0.5 * of.n_points]
    res = {}
    for a in OBJ_ATT:
        sc = scans[scans.attack == a].scan
        g = ph[ph.scan.isin(sc)]
        res[a] = {"n_scans": int(len(sc)), "scans_with_phantom_tile": int(g.scan.nunique()), "n_phantom_tiles": int(len(g)),
                  "tile_detection": float(g.caught.mean()) if len(g) else None,
                  "scan_with_phantom_tile_caught": float(g[g.caught].scan.nunique() / max(len(sc), 1))}
    return res


def evalset(layers, frames, names):
    df = pd.concat(frames, ignore_index=True)
    ev = {n: layers[n][0].score(layers[n][1](df)) for n in names}
    y = (df.attack != "clean").to_numpy().astype(int)
    return EvalSet(evidence=ev, y=y, attack_type=np.where(y == 1, df.attack, "normal"), group=df.drive.to_numpy(),
                   t=df.idx.to_numpy() * FRAME_DT)


def windows(cal_by_drive, step):
    out = []
    for d, s in cal_by_drive.items():
        for a in range(0, len(s) - EPISODE_SCANS + 1, step):
            out.append(s[a:a + EPISODE_SCANS])
    return out


def main():
    t0 = time.time()
    dev = json.loads((RES / "dev.json").read_text())
    nmin, primary = dev["nmin_chosen"], dev["primary"]
    calib = C.load_calib(RESULTS / "WP3" / "S2" / "calibration_beta.npz")
    tr, va = drives_of("train"), drives_of("val")
    co, cs = E.load_kind(ROOT, "clean", tr + va + TEST)
    dco = cs.set_index("scan")["drive"].loc[co.scan.to_numpy()].to_numpy()
    ao_v, as_v = E.load_kind(ROOT, "att_val", VAL)
    ao_t, as_t = E.load_kind(ROOT, "att_test", TEST)
    eo, es = E.load_kind(ROOT, "ep_test", TEST)
    out = {"nmin": nmin, "primary": primary, "dev": dev}

    m_v = D.ObjectModel(calib, nmin).fit(co[np.isin(dco, tr)])
    cv = E.scan_frame(m_v, co[np.isin(dco, va)], cs[cs.drive.isin(va)])
    lay_v = E.union_layer(cv)
    co_t, cs_t = co[np.isin(dco, TEST)], cs[cs.drive.isin(TEST)]
    ctest_v = E.scan_frame(m_v, co_t, cs_t)
    m_l = D.ObjectModel(calib, nmin).fit(co[np.isin(dco, tr + va)])
    oof = E.lodo_scan_scores(co[np.isin(dco, tr + va)], cs[cs.drive.isin(tr + va)], tr + va, calib, nmin)
    lay_l = E.union_layer(oof)
    ctest_l = E.scan_frame(m_l, co_t, cs_t)
    modes = {"val_only": (m_v, lay_v, ctest_v, cv), "lodo": (m_l, lay_l, ctest_l, oof)}
    for name, (m, lay, ct, ref) in modes.items():
        fa = E.per_drive_fa(lay, ct)
        r = {"threshold": float(lay.threshold), "fa_test": float((E.cal_scores(lay, ct) >= lay.threshold).mean()),
             "fa_test_per_drive": {d: float(v) for d, v in fa.items()}, "attacks": {}, "parts_fa": {}}
        af = E.scan_frame(m, ao_t, as_t)
        det = E.detection(lay, af)
        for part in PARTS:
            sub = D.L2aUnion([part]).calibrate(ref)
            r["parts_fa"][part] = float((E.cal_scores(sub, ct) >= sub.threshold).mean())
            dp = E.detection(sub, af)
            for a in ATT:
                r["attacks"].setdefault(a, {})[part] = float(dp[a])
        for a in ATT:
            r["attacks"][a]["union"] = float(det[a])
            r["attacks"][a]["n"] = int((af.attack == a).sum())
        r["object_level"] = object_level(lay, m, ao_t, as_t)
        cal_clean_v = {d: E.cal_scores(lay, ref[ref.drive == d].sort_values("idx")) for d in sorted(ref.drive.unique())}
        if name == "val_only":
            cal_clean_v = {d: v for d, v in cal_clean_v.items() if d in va}
        stat_v = np.concatenate([rolling_logodds(w) for w in windows(cal_clean_v, 10)])
        thr = float(np.quantile(stat_v, 0.99))
        cal_clean_t = {d: E.cal_scores(lay, ct[ct.drive == d].sort_values("idx")) for d in TEST}
        wt = windows(cal_clean_t, EPISODE_SCANS)
        r["episodes"] = {"stat_threshold": thr, "false_episode_rate_test_clean": float(np.mean([(rolling_logodds(w) >= thr).any() for w in wt])),
                         "n_clean_windows": len(wt), "kinds": {}}
        ef = E.scan_frame(m, eo, es)
        ef["cal"] = E.cal_scores(lay, ef)
        for kind, g in ef.groupby("attack"):
            res, delays = [], []
            for (d, j), e in g.groupby(["drive", "ep"]):
                st = rolling_logodds(e.sort_values("step").cal.to_numpy())
                hit = np.flatnonzero(st >= thr)
                res.append(len(hit) > 0 and hit[0] + 1 <= EPISODE_SCANS)
                if len(hit):
                    delays.append((hit[0] + 1) * FRAME_DT)
            r["episodes"]["kinds"][kind] = {"episodes": len(res), "detected_3s": int(sum(res)),
                                            "median_delay_s_of_alarmed": float(np.median(delays)) if delays else None,
                                            "single_scan_alarm_rate": float((g.cal >= lay.threshold).mean())}
        t1 = time.time()
        m.scores(co_t)
        r["scoring_ms_per_scan"] = 1000 * (time.time() - t1) / len(cs_t)
        out[name] = r
        print(name, "FA", r["fa_test"], flush=True)

    # harness ablation (val-only model: its validation threshold is out-of-sample)
    l1v = L1Union().calibrate(l1_cols(cs[cs.drive.isin(va)]))
    ident = lambda d: d  # noqa
    layers = {"L1": (l1v, l1_cols), "L2a": (lay_v, ident),
              "L2a_dens": (D.L2aUnion(["dens_hi", "dens_lo", "cnt_dens_hi", "cnt_dens_lo"]).calibrate(cv), ident),
              "L2a_int": (D.L2aUnion(["int_hi", "int_lo", "cnt_int_hi", "cnt_int_lo"]).calibrate(cv), ident)}
    for n in ("L2a", "L2a_dens", "L2a_int"):
        layers[n][0].name = n
    vfr = [cv.assign(attack="clean"), E.scan_frame(m_v, ao_v, as_v)]
    tfr = [ctest_v.assign(attack="clean"), E.scan_frame(m_v, ao_t, as_t)]
    for tag, names in (("harness_L1_L2a", ["L1", "L2a"]), ("harness_L1_dens_int", ["L1", "L2a_dens", "L2a_int"])):
        res = evaluate_domain(tag, evalset(layers, vfr, names), evalset(layers, tfr, names), wp="WP3", budget=0.01, method="noisy_or", out_dir=RES)
        out[tag] = {"layers": res["layers"], "ablation": res["ablation"]}
    out["seconds"] = time.time() - t0
    (RES / "final.json").write_text(json.dumps(out, indent=1, default=float))
    print("done", out["seconds"])


if __name__ == "__main__":
    main()
