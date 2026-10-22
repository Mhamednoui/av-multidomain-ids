"""WP6 S2 evaluation: "which domain lies" on KITTI (gps / lidar / simulated can / imu) and comma2k19 (gnss / can / wheel / imu).

Stages (python -u -W ignore tools/WP6_S2_eval.py <stage>):
  dev  : VALIDATION only. comma per-setup sigma models fitted on TRAIN routes (candidates A = gyro class, B = gyro x gnss class
         with fallback), honesty on val (AC1), choice of the setup definition; KITTI uses the S1 kitti_R models (one setup).
         CUSUM reference k in {0.25, 0.5, 1.0, inst} chosen per data set on val (selection attacks only) at the val 1% threshold.
         -> results/WP6/s2_dev.json, results/WP6/s2_choices.json (frozen before the test stage).
  test : ONCE. Chosen configuration on TEST: FA (clean rows / runs), detection, blame, delay per attack, coordinated attacks,
         comparison with the frozen GPS domain (KITTI), ablation (inst vs chosen k) -> results/WP6/s2_test.json.
Inputs: ../data_extra/cache_v3/WP6/s2_kitti.pkl, s2_comma.pkl, s2_gpsdomain.pkl (tools/WP6_S2_kitti.py, WP6_S2_comma.py,
WP6_S2_gpsdomain.py); results/WP6/s1_sigma_models.json.
"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.config import SEED, results_dir  # noqa: E402
from crossdomain import consistency as CS  # noqa: E402
from crossdomain import witness as W  # noqa: E402
import WP6_S2_comma as SC  # noqa: E402
import WP6_S2_kitti as SK  # noqa: E402

OUT = results_dir("WP6")
CACHE = SK.CACHE
KS = [0.25, 0.5, 1.0, "inst"]
SELECTION = ["drift", "accel_drift", "lidar_scale", "lidar_bias", "can_scale", "can_offset"]
HELD_OUT = ["doppler_spoof", "meaconing", "lidar_yaw", "can_freeze"]
SINGLE = {"kitti": SK.GPS_ATTACKS + SK.LIDAR_ATTACKS + SK.CAN_ATTACKS, "comma": SC.GNSS_ATTACKS + SC.CAN_ATTACKS}
COORD = {"kitti": ["gps_can"], "comma": ["gnss_can", "can_bus"]}
TARGET_DOMAIN = {"gps": "gps", "gnss": "gps", "lidar": "lidar", "can": "can"}


# ---------------------------------------------------------------------------------------------------------------------
# data sets -> edges, models, z
# ---------------------------------------------------------------------------------------------------------------------
def kitti_edges():
    return [CS.Edge(a, b, q, m) for a, b, q, m in SK.EDGES]


def comma_edges():
    return [CS.Edge(*n.split(" ")[0].split("-"), n.split(" ")[1], n) for n in SC.EDGE_NAMES]


def kitti_z(rows, edges):
    sm = json.loads((OUT / "s1_sigma_models.json").read_text())["kitti_R"]["models"]
    Z = np.full((len(rows), len(edges)), np.nan)
    for j, e in enumerate(edges):
        m = W.SigmaModel.from_dict(sm[e.model])
        Z[:, j] = m.z(rows[f"r_{e.name}"].to_numpy(float), rows[f"v_{e.name}"].to_numpy(float))
    return Z


def setup_key(s, mode):
    g = "g10" if s["gyro_hz"] <= 20 else "g100"
    return g if mode == "A" else g + ("n5" if s["gnss_hz"] <= 6.5 else "n10")


def fit_comma_models(routes, setup, mode):
    """{setup key: {edge: SigmaModel}} fitted on TRAIN routes; mode B cells with < 3 train routes fall back to the gyro class."""
    tr = routes[routes["part"] == "train"]
    keys = {n: setup_key(s, mode) for n, s in setup.items()}
    out, used = {}, {}
    for key in sorted(set(keys.values())):
        rs = [n for n in tr["route"].unique() if keys[n] == key]
        fb = None
        if mode == "B" and len(rs) < 3:
            fb = key[:4] if key.startswith("g100") else key[:3]
            rs = [n for n in tr["route"].unique() if setup_key(setup[n], "A") == fb]
        used[key] = {"train_routes": len(rs), "fallback": fb}
        if not rs:
            continue
        g = tr[tr["route"].isin(rs)]
        out[key] = {e: W.SigmaModel(bias="linear").fit(*_ok(g[f"r_{e}"], g[f"v_{e}"])) for e in SC.EDGE_NAMES}
    return out, keys, used


def _ok(r, v):
    r, v = np.asarray(r, float), np.asarray(v, float)
    m = np.isfinite(r) & np.isfinite(v)
    return r[m], v[m]


def comma_z(rows, edges, models, keys):
    Z = np.full((len(rows), len(edges)), np.nan)
    rk = rows["route"].map(keys).to_numpy()
    for key, ms in models.items():
        m = rk == key
        for j, e in enumerate(edges):
            Z[m, j] = ms[e.name].z(rows.loc[m, f"r_{e.name}"].to_numpy(float), rows.loc[m, f"v_{e.name}"].to_numpy(float))
    return Z


def honesty(Z, edges):
    return {e.name: W.honesty(Z[:, j]) for j, e in enumerate(edges)}


def ac1_ok(h):
    """not too narrow: |mean| <= 0.25, std <= 1.25, p99 |z| <= 4 (std < 0.8 allowed)."""
    return bool(h["n"] > 0 and abs(h["mean"]) <= 0.25 and h["std"] <= 1.25 and h["p99_abs"] <= 4.0)


# ---------------------------------------------------------------------------------------------------------------------
# runs and metrics
# ---------------------------------------------------------------------------------------------------------------------
def split_runs(rows, Z):
    out = []
    for run, idx in rows.groupby("run", sort=True).indices.items():
        idx = np.sort(idx)
        r0 = rows.iloc[idx[0]]
        out.append({"run": run, "t": rows["t"].to_numpy(float)[idx], "Z": Z[idx], "attack": r0["attack"], "target": r0["target"],
                    "onset_t": float(r0["onset_t"]), "severity": float(r0["severity"]), "group": r0.get("drive", r0.get("route"))})
    return out


def evaluate(layer, runs):
    """Per run outcome + per attack summary. Clean runs: FA at row and run level."""
    per = []
    clean_alarm, clean_rows = 0, 0
    for r in runs:
        res = layer.run(r["Z"])
        if r["attack"] == "none":
            n_al = int(res["layer_alarm"].sum())
            clean_alarm += n_al
            clean_rows += len(r["t"])
            per.append({"run": r["run"], "attack": "none", "group": r["group"], "alarms": n_al, "rows": len(r["t"]), "detected": n_al > 0,
                        "wrong_blames": int(sum(b not in (None, CS.UNDECIDED) for b in res["blamed"]))})
        else:
            o = CS.run_outcome(r["t"], r["onset_t"], res)
            pre = res["layer_alarm"] & (r["t"] < r["onset_t"])
            per.append({"run": r["run"], "attack": r["attack"], "target": r["target"], "group": r["group"], "severity": r["severity"],
                        "detected": o["detected"], "delay": o["delay"], "blame": o["blame"],
                        "blamed_domain": None if o["blame"] in (None, CS.UNDECIDED) else layer.domain_of[o["blame"]], "pre_onset_alarms": int(pre.sum())})
    return per, (clean_alarm, clean_rows)


def summarise(per, fa, single, coord):
    df = pd.DataFrame(per)
    cl = df[df["attack"] == "none"]
    out = {"fa_rows": fa[0] / max(fa[1], 1), "clean_rows": fa[1], "fa_runs": float(cl["detected"].mean()), "clean_runs": int(len(cl)),
           "clean_rows_with_decided_blame": int(cl["wrong_blames"].sum()), "attacks": {}}
    for a in single + coord:
        g = df[df["attack"] == a]
        if not len(g):
            continue
        det = g[g["detected"]]
        tdom = TARGET_DOMAIN.get(g["target"].iloc[0])
        s = {"runs": int(len(g)), "detection": float(g["detected"].mean()), "detected": int(len(det)),
             "median_delay_s": float(det["delay"].median()) if len(det) else None,
             "undecided": float((det["blame"] == CS.UNDECIDED).mean()) if len(det) else None,
             "blame_counts": {str(k): int(v) for k, v in det["blamed_domain"].fillna(CS.UNDECIDED).value_counts().items()}}
        if tdom is not None and len(det):
            s["correct_blame"] = float((det["blamed_domain"] == tdom).mean())
            s["wrong_blame"] = float((det["blamed_domain"].notna() & (det["blamed_domain"] != tdom)).mean())
        out["attacks"][a] = s
    sg = [out["attacks"][a] for a in single if a in out["attacks"]]
    n_det = sum(s["detected"] for s in sg)
    out["mean_detection_single"] = float(np.mean([s["detection"] for s in sg]))
    out["pooled_single"] = {"detected": n_det,
                            "correct_blame": float(sum(s.get("correct_blame", 0) * s["detected"] for s in sg) / max(n_det, 1)),
                            "wrong_blame": float(sum(s.get("wrong_blame", 0) * s["detected"] for s in sg) / max(n_det, 1)),
                            "undecided": float(sum((s["undecided"] or 0) * s["detected"] for s in sg) / max(n_det, 1))}
    return out


def cluster_ci(per, single, n_boot=1000, seed=SEED):
    """95% bootstrap over groups (drives / routes) of: mean single-attack detection, FA rows."""
    df = pd.DataFrame(per)
    groups = sorted(df["group"].unique())
    rng = np.random.default_rng(seed)
    det, fa = [], []
    by = {g: df[df["group"] == g] for g in groups}
    for _ in range(n_boot):
        s = pd.concat([by[g] for g in rng.choice(groups, len(groups))], ignore_index=True)
        a = s[s["attack"].isin(single)]
        det.append(a.groupby("attack")["detected"].mean().mean())
        c = s[s["attack"] == "none"]
        fa.append(c["alarms"].sum() / max(c["rows"].sum(), 1))
    return {"mean_detection_single": [float(x) for x in np.percentile(det, [2.5, 97.5])], "fa_rows": [float(x) for x in np.percentile(fa, [2.5, 97.5])]}


def layer_for(edges, domain_of, k, clean_runs):
    return CS.WhichDomainLies(edges, domain_of, k=k).fit([r["Z"] for r in clean_runs])


# ---------------------------------------------------------------------------------------------------------------------
def load(ds, setup_mode=None):
    if ds == "kitti":
        c = pickle.load(open(CACHE / "s2_kitti.pkl", "rb"))
        rows = c["rows"]
        edges = kitti_edges()
        return rows, edges, kitti_z(rows, edges), SK.DOMAIN_OF, None
    c = pickle.load(open(CACHE / "s2_comma.pkl", "rb"))
    edges = comma_edges()
    models, keys, used = fit_comma_models(c["routes"], c["setup"], setup_mode)
    rows = c["episodes"]
    return rows, edges, comma_z(rows, edges, models, keys), SC.DOMAIN_OF, {"routes": c["routes"], "models": models, "keys": keys, "used": used,
                                                                              "setup": c["setup"]}


def dev():
    res, choices = {}, {}
    # ---- sigma calibration (AC1) on val ----
    rows, edges, Z, dom, _ = load("kitti")
    m = (rows["part"] == "val").to_numpy() & (rows["attack"] == "none").to_numpy() & (rows["phase"] == 0).to_numpy()
    hk = honesty(Z[m], edges)
    res["kitti_honesty_val"] = {"setup": "one KITTI setup, S1 kitti_R models (train)", "edges": hk, "ac1": {k: ac1_ok(v) for k, v in hk.items()}}
    c = pickle.load(open(CACHE / "s2_comma.pkl", "rb"))
    res["comma_setups"] = c["setup"]
    cand = {}
    for mode in ("A", "B"):
        models, keys, used = fit_comma_models(c["routes"], c["setup"], mode)
        vr = c["routes"][c["routes"]["part"] == "val"].reset_index(drop=True)
        h = honesty(comma_z(vr, comma_edges(), models, keys), comma_edges())
        ok = {k: ac1_ok(v) for k, v in h.items()}
        cand[mode] = {"edges": h, "ac1": ok, "n_fail": int(sum(not v for v in ok.values())), "mean_abs_std_minus_1": float(np.mean([abs(v["std"] - 1) for v in h.values()])),
                      "cells": used, "models": {k: {e: m.to_dict() for e, m in ms.items()} for k, ms in models.items()}}
        # pooled design R (S1 single model fitted on all train routes) as reference row
    allok = [m for m in cand if cand[m]["n_fail"] == 0]
    mode = min(allok, key=lambda m: cand[m]["mean_abs_std_minus_1"]) if allok else min(cand, key=lambda m: (cand[m]["n_fail"], cand[m]["mean_abs_std_minus_1"]))
    res["comma_honesty_val"] = cand
    choices["comma_setup_mode"] = mode
    # ---- k choice on val ----
    for ds in ("kitti", "comma"):
        rows, edges, Z, dom, extra = load(ds, mode)
        val = rows["part"] == "val"
        runs = split_runs(rows[val].reset_index(drop=True), Z[val.to_numpy()])
        clean = [r for r in runs if r["attack"] == "none"]
        res[f"{ds}_k"] = {}
        for k in KS:
            layer = layer_for(edges, dom, k, clean)
            per, fa = evaluate(layer, runs)
            s = summarise(per, fa, SINGLE[ds], COORD[ds])
            sel = [s["attacks"][a]["detection"] for a in SELECTION if a in s["attacks"]]
            s["selection_mean_detection"] = float(np.mean(sel))
            s["tau"] = layer.calibration.tau
            res[f"{ds}_k"][str(k)] = s
            print(ds, k, "sel", round(s["selection_mean_detection"], 3), "fa", round(s["fa_rows"], 4), "blame", s["pooled_single"], flush=True)
        best = max(KS, key=lambda k: res[f"{ds}_k"][str(k)]["selection_mean_detection"])
        choices[f"{ds}_k"] = best
    choices["note"] = "frozen after the dev stage (validation only); the test stage reads this file"
    (OUT / "s2_dev.json").write_text(json.dumps(res, indent=1, default=str))
    (OUT / "s2_choices.json").write_text(json.dumps(choices, indent=1))
    print(choices)
    for k, v in res["kitti_honesty_val"]["edges"].items():
        print("kitti val", k, {a: round(b, 3) if isinstance(b, float) else b for a, b in v.items()})
    for mo in ("A", "B"):
        for k, v in res["comma_honesty_val"][mo]["edges"].items():
            print("comma", mo, k, {a: round(b, 3) if isinstance(b, float) else b for a, b in v.items()})


def gps_domain_compare(per_cross, part="test"):
    g = pickle.load(open(CACHE / "s2_gpsdomain.pkl", "rb"))
    g = g[g["part"] == part]
    gd = {}
    for run, x in g.groupby("run"):
        on = x["onset_t"].iloc[0]
        post = x["t"] >= on if np.isfinite(on) else np.ones(len(x), bool)
        gd[run] = bool((x["alarm"] & post).any())
    clean_fa_rows = float(g[g["attack"] == "none"]["alarm"].mean())
    df = pd.DataFrame(per_cross)
    out = {"gps_domain_fa_rows": clean_fa_rows, "attacks": {}}
    for a in SK.GPS_ATTACKS + ["gps_can"]:
        x = df[df["attack"] == a]
        gdet = np.array([gd[r] for r in x["run"]])
        cdet = x["detected"].to_numpy(bool)
        out["attacks"][a] = {"runs": int(len(x)), "gps_domain": float(gdet.mean()), "cross": float(cdet.mean()), "union": float((gdet | cdet).mean()),
                             "cross_catches_gps_misses": int((cdet & ~gdet).sum()), "gps_misses": int((~gdet).sum())}
    return out, gd


def union_fa(layer, runs, part="test"):
    g = pickle.load(open(CACHE / "s2_gpsdomain.pkl", "rb"))
    g = g[(g["part"] == part) & (g["attack"] == "none")].set_index(["run", "t"])["alarm"]
    n = al = 0
    for r in runs:
        if r["attack"] != "none":
            continue
        res = layer.run(r["Z"])
        ga = np.array([bool(g.get((r["run"], t), False)) for t in r["t"]])
        al += int((ga | res["layer_alarm"]).sum())
        n += len(r["t"])
    return al / max(n, 1)


def test():
    ch = json.loads((OUT / "s2_choices.json").read_text())
    res = {"note": "TEST run 2 = SECOND EXPOSURE after the setup-rate bug fix (run 1: s2_test_run1.json); choices frozen on validation in s2_choices.json", "choices": ch}
    for ds in ("kitti", "comma"):
        rows, edges, Z, dom, extra = load(ds, ch["comma_setup_mode"])
        vmask = (rows["part"] == "val").to_numpy()
        tmask = (rows["part"] == "test").to_numpy()
        vruns = split_runs(rows[vmask].reset_index(drop=True), Z[vmask])
        truns = split_runs(rows[tmask].reset_index(drop=True), Z[tmask])
        vclean = [r for r in vruns if r["attack"] == "none"]
        out = {}
        for tag, k in (("chosen", ch[f"{ds}_k"]), ("ablation_inst", "inst")):
            layer = layer_for(edges, dom, k, vclean)
            per, fa = evaluate(layer, truns)
            s = summarise(per, fa, SINGLE[ds], COORD[ds])
            s["k"], s["tau"] = k, layer.calibration.tau
            if tag == "chosen":
                s["ci95_groups"] = cluster_ci(per, SINGLE[ds])
                s["edge_fa_rows"] = edge_fa(layer, truns)
                if ds == "kitti":
                    s["vs_gps_domain"], _ = gps_domain_compare(per)
                    s["vs_gps_domain"]["union_fa_rows"] = union_fa(layer, truns)
                    pooled = [s["vs_gps_domain"]["attacks"][a] for a in ("doppler_spoof", "meaconing")]
                    s["vs_gps_domain"]["doppler_meaconing_pooled"] = {"gps_domain": float(np.mean([p["gps_domain"] for p in pooled])),
                                                                     "union": float(np.mean([p["union"] for p in pooled]))}
                    a_run = next(r for r in truns if r["attack"] == "lidar_scale")
                    ev = layer.evidence(a_run["t"], a_run["Z"])
                    s["example_evidence"] = [e.to_dict() for e in ev if e.alarm][:2]
                else:
                    s["full_route_fa"] = full_route_fa(layer, extra, edges)
                s["per_run"] = per
            out[tag] = s
            print(ds, tag, "FA", round(s["fa_rows"], 4), "mean det", round(s["mean_detection_single"], 3), s["pooled_single"], flush=True)
            for a, v in s["attacks"].items():
                print("   ", a, {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items()}, flush=True)
        res[ds] = out
    (OUT / "s2_test.json").write_text(json.dumps(res, indent=1, default=str))


def edge_fa(layer, runs):
    al, n = None, 0
    for r in runs:
        if r["attack"] != "none":
            continue
        a = layer.run(r["Z"])["alarm"].sum(0)
        al = a if al is None else al + a
        n += len(r["t"])
    return {e.name: float(al[j] / n) for j, e in enumerate(layer.edges)}


def full_route_fa(layer, extra, edges):
    """Continuous deployment: CUSUM over whole TEST routes (not 120 s windows), row-level FA."""
    rt = extra["routes"][extra["routes"]["part"] == "test"].reset_index(drop=True)
    Z = comma_z(rt, edges, extra["models"], extra["keys"])
    n = al = 0
    per = {}
    for route, idx in rt.groupby("route").indices.items():
        a = layer.run(Z[np.sort(idx)])["layer_alarm"]
        per[route] = float(a.mean())
        al += int(a.sum())
        n += len(a)
    return {"fa_rows": al / n, "rows": n, "per_route": per}


if __name__ == "__main__":
    {"dev": dev, "test": test}[sys.argv[1]]()
