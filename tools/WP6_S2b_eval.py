"""WP6 S2b (VALIDATION ONLY, no test data read): bias-tolerant sequential test + leave-one-group-out calibration + domain-level blame.

Run: python -u -W ignore tools/WP6_S2b_eval.py [1|2]   (round 1 = pre-registered candidates; round 2 = post-hoc robust bias tracking)
Inputs: ../data_extra/cache_v3/WP6/s2b_kitti.pkl (KITTI DEV drives: train + val), s2b_comma.pkl (comma: whole routes + DEV episodes)
(tools/WP6_S2_kitti.py build_dev, tools/WP6_S2_comma.py build_dev). Test drives / routes are never loaded into any computation
(the comma routes table holds every route; rows of test routes are dropped first).
Protocol (notes/WP6_crossdomain.md "S2b start"): out-of-fold SigmaModels per dev group; per-edge ECDF + tie-safe 1% tau fitted on
the clean statistics of the OTHER dev groups; held-out group scored; pooled over folds. comma runs CONTINUOUSLY over whole routes
(attack episodes spliced in, statistic continued from the clean state at the window start). Candidates: plain CUSUM k 0.5 / 1,
inst, drift-compensated CUSUM (k 0.5 / 1, Tb 60 / 300 s, bias frozen while the edge statistic >= 2). Domain-level blame.
Outputs: results/WP6/s2b_dev.json (every candidate), s2b_choice.json, s2b_acceptance.json, s2b_tables.md.
"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.config import results_dir  # noqa: E402
from crossdomain import consistency as CS  # noqa: E402
from crossdomain import witness as W  # noqa: E402
import WP6_S2_comma as SC  # noqa: E402
import WP6_S2_kitti as SK  # noqa: E402

OUT = results_dir("WP6")
CACHE = SK.CACHE
FREEZE = 2.0
BUDGET = 0.01
CANDS = [{"name": "cusum_k0.5", "k": 0.5, "tb": None}, {"name": "cusum_k1", "k": 1.0, "tb": None}, {"name": "inst", "k": "inst", "tb": None},
         {"name": "drift_k0.5_tb60", "k": 0.5, "tb": 60}, {"name": "drift_k0.5_tb300", "k": 0.5, "tb": 300},
         {"name": "drift_k1_tb60", "k": 1.0, "tb": 60}, {"name": "drift_k1_tb300", "k": 1.0, "tb": 300}]
CANDS_R2 = [{"name": "R2_wu60_k0.5_tb300", "k": 0.5, "tb": 300, "warmup": 60}, {"name": "R2_wu60_k1_tb300", "k": 1.0, "tb": 300, "warmup": 60},
            {"name": "R2_k1_tb120", "k": 1.0, "tb": 120, "warmup": 0}, {"name": "R2_k0.5_tb120", "k": 0.5, "tb": 120, "warmup": 0}]
C_CLIP = 0.5
SELECTION = {"kitti": ["drift", "accel_drift", "lidar_scale", "lidar_bias", "can_scale", "can_offset"],
             "comma": ["drift", "accel_drift", "can_scale", "can_offset"]}
SINGLE = {"kitti": SK.GPS_ATTACKS + SK.LIDAR_ATTACKS + SK.CAN_ATTACKS, "comma": SC.GNSS_ATTACKS + SC.CAN_ATTACKS}
COORD = {"kitti": ["gps_can"], "comma": ["gnss_can", "can_bus"]}
TARGET_DOMAIN = {"gps": "gps", "gnss": "gps", "lidar": "lidar", "can": "can"}


def stats(Z, c, state=None):
    if "warmup" in c:
        return CS.robust_cusum(Z, c["k"], c["tb"], C_CLIP, c["warmup"], state=state, return_state=True)
    if c["k"] == "inst":
        return np.abs(Z), None
    return CS.drift_cusum(Z, c["k"], c["tb"], FREEZE, state, return_state=True)


def outcome_rows(S, cal, edges, domain_of):
    es = cal.edge_scores(S)
    al = es >= cal.tau
    return {"layer_alarm": al.any(1), "blamed": CS.blame(edges, al, np.isfinite(S), domain_of)}


def oof_models(fit_rows, edges):
    out = {}
    for e in edges:
        r, v = fit_rows[f"r_{e.name}"].to_numpy(float), fit_rows[f"v_{e.name}"].to_numpy(float)
        ok = np.isfinite(r) & np.isfinite(v)
        out[e.name] = W.SigmaModel(bias="linear").fit(r[ok], v[ok])
    return out


def z_of(rows, edges, models):
    Z = np.full((len(rows), len(edges)), np.nan)
    for j, e in enumerate(edges):
        Z[:, j] = models[e.name].z(rows[f"r_{e.name}"].to_numpy(float), rows[f"v_{e.name}"].to_numpy(float))
    return Z


# ---------------------------------------------------------------------------------------------------------------------
def kitti_runs():
    rows = pickle.load(open(CACHE / "s2b_kitti.pkl", "rb"))["rows"]
    assert set(rows["part"]) <= {"train", "val"}
    edges = [CS.Edge(a, b, q, m) for a, b, q, m in SK.EDGES]
    clean0 = rows[(rows["attack"] == "none") & (rows["phase"] == 0)]
    runs = {}
    for d, rd in rows.groupby("drive"):
        models = oof_models(clean0[clean0["drive"] != d], edges)
        rd = rd.sort_values(["run", "t"]).reset_index(drop=True)
        Z = z_of(rd, edges, models)
        for run, idx in rd.groupby("run").indices.items():
            r0 = rd.iloc[idx[0]]
            runs.setdefault(d, []).append({"run": run, "t": rd["t"].to_numpy(float)[idx], "Z": Z[idx], "attack": r0["attack"], "target": r0["target"],
                                           "onset_t": float(r0["onset_t"]), "part": r0["part"]})
    return edges, runs


def eval_kitti(edges, runs, c):
    S = {g: [stats(r["Z"], c)[0] for r in rs] for g, rs in runs.items()}
    clean = {g: np.vstack([s for s, r in zip(S[g], runs[g]) if r["attack"] == "none"]) for g in runs}
    per, fa = [], {}
    for g in runs:
        cal = CS.Calibration(BUDGET).fit(np.vstack([clean[h] for h in runs if h != g]))
        n_al = n = 0
        for s, r in zip(S[g], runs[g]):
            res = outcome_rows(s, cal, edges, SK.DOMAIN_OF)
            if r["attack"] == "none":
                n_al += int(res["layer_alarm"].sum())
                n += len(r["t"])
                continue
            o = CS.run_outcome(r["t"], r["onset_t"], res)
            per.append({"group": g, "part": r["part"], "attack": r["attack"], "target": r["target"], **o})
        fa[g] = (n_al, n, runs[g][0]["part"])
    return per, fa


# ---------------------------------------------------------------------------------------------------------------------
def comma_data():
    c = pickle.load(open(CACHE / "s2b_comma.pkl", "rb"))
    setup = c["setup"]
    routes = c["routes"][c["routes"]["part"].isin(["train", "val"])]
    eps = c["episodes"]
    assert set(eps["part"]) <= {"train", "val"}
    edges = [CS.Edge(*n.split(" ")[0].split("-"), n.split(" ")[1], n) for n in SC.EDGE_NAMES]
    cls = {n: ("g10" if s["gyro_hz"] <= 20 else "g100") for n, s in setup.items()}
    data = {}
    for n, rr in routes.groupby("route"):
        fit = routes[(routes["route"] != n) & (routes["route"].map(cls) == cls[n])]
        models = oof_models(fit, edges)
        rr = rr.sort_values("t").reset_index(drop=True)
        e = eps[eps["route"] == n]
        epis = []
        for run, idx in e.groupby("run").indices.items():
            x = e.iloc[np.sort(idx)]
            r0 = x.iloc[0]
            if r0["attack"] == "none":
                continue
            t = x["t"].to_numpy(float)
            epis.append({"run": run, "t": t, "Z": z_of(x, edges, models), "attack": r0["attack"], "target": r0["target"], "onset_t": float(r0["onset_t"]),
                         "i0": int(np.searchsorted(rr["t"].to_numpy(float), t[0]))})
        data[n] = {"t": rr["t"].to_numpy(float), "Z": z_of(rr, edges, models), "episodes": epis, "part": setup[n]["part"], "class": cls[n]}
    return edges, data, cls


def clean_states(Z, c):
    """Statistic of a clean route and the state before every row (to continue an attack episode from it)."""
    out, states, st = np.full(Z.shape, np.nan), [], None
    for i in range(len(Z)):
        states.append(st)
        o, st = stats(Z[i:i + 1], c, st)
        out[i] = o[0]
    return out, states


def eval_comma(edges, data, c):
    clean, states = {}, {}
    for n, d in data.items():
        if c["k"] == "inst" and "warmup" not in c:
            clean[n], states[n] = np.abs(d["Z"]), None
        else:
            clean[n], states[n] = clean_states(d["Z"], c)
    per, fa = [], {}
    for n, d in data.items():
        cal = CS.Calibration(BUDGET).fit(np.vstack([clean[h] for h in data if h != n]))
        res = outcome_rows(clean[n], cal, edges, SC.DOMAIN_OF)
        fa[n] = (int(res["layer_alarm"].sum()), len(d["t"]), d["part"])
        for ep in d["episodes"]:
            st = None if states[n] is None else states[n][ep["i0"]]
            s, _ = stats(ep["Z"], c, st)
            o = CS.run_outcome(ep["t"], ep["onset_t"], outcome_rows(s, cal, edges, SC.DOMAIN_OF))
            per.append({"group": n, "part": d["part"], "attack": ep["attack"], "target": ep["target"], **o})
    return per, fa


# ---------------------------------------------------------------------------------------------------------------------
def summarise(per, fa, ds):
    df = pd.DataFrame(per)
    n_al = sum(v[0] for v in fa.values())
    n = sum(v[1] for v in fa.values())
    out = {"fa_rows": n_al / n, "clean_rows": n, "fa_per_group": {g: v[0] / max(v[1], 1) for g, v in fa.items()},
           "fa_val_groups": sum(v[0] for v in fa.values() if v[2] == "val") / max(sum(v[1] for v in fa.values() if v[2] == "val"), 1),
           "attacks": {}}
    out["worst_group"] = max(out["fa_per_group"].items(), key=lambda x: x[1])
    for a in SINGLE[ds] + COORD[ds]:
        g = df[df["attack"] == a]
        det = g[g["detected"]]
        bd = det["blame"].where(det["blame"] != CS.UNDECIDED)
        s = {"runs": int(len(g)), "detection": float(g["detected"].mean()), "detected": int(len(det)),
             "detection_val_groups": float(g[g["part"] == "val"]["detected"].mean()) if (g["part"] == "val").any() else None,
             "median_delay_s": float(det["delay"].median()) if len(det) else None,
             "undecided": float((det["blame"] == CS.UNDECIDED).mean()) if len(det) else None,
             "blame_counts": {str(k): int(v) for k, v in det["blame"].value_counts().items()}}
        td = TARGET_DOMAIN.get(g["target"].iloc[0]) if len(g) else None
        if td and len(det):
            s["correct_blame"] = float((bd == td).mean())
            s["wrong_blame"] = float((bd.notna() & (bd != td)).mean())
        out["attacks"][a] = s
    sg = [out["attacks"][a] for a in SINGLE[ds]]
    nd = sum(s["detected"] for s in sg)
    out["mean_detection_single"] = float(np.mean([s["detection"] for s in sg]))
    out["selection_mean_detection"] = float(np.mean([out["attacks"][a]["detection"] for a in SELECTION[ds]]))
    out["pooled_single"] = {k: float(sum((s.get(k) or 0) * s["detected"] for s in sg) / max(nd, 1)) for k in ("correct_blame", "wrong_blame", "undecided")}
    out["pooled_single"]["detected"] = nd
    return out


def main():
    rnd = sys.argv[1] if len(sys.argv) > 1 else "1"
    cands = CANDS if rnd == "1" else CANDS_R2
    sfx = "" if rnd == "1" else "_r2"
    res, choice = {"note": f"S2b round {rnd}, DEV groups only (train + val), leave-one-group-out; no test data", "candidates": cands}, {}
    ke, kr = kitti_runs()
    ce, cd, cls = comma_data()
    res["comma_setup_class"] = cls
    for ds, fn, args in (("kitti", eval_kitti, (ke, kr)), ("comma", eval_comma, (ce, cd))):
        res[ds] = {}
        for c in cands:
            per, fa = fn(*args, c)
            s = summarise(per, fa, ds)
            res[ds][c["name"]] = s
            print(ds, c["name"], "FA", round(s["fa_rows"], 4), "worst", s["worst_group"][0][-8:], round(s["worst_group"][1], 3), "sel", round(s["selection_mean_detection"], 3),
                  "mean", round(s["mean_detection_single"], 3), {k: round(v, 3) for k, v in s["pooled_single"].items()}, flush=True)
        allres = dict(res[ds])
        if rnd != "1":                          # round 2 chooses among round-1 + round-2 candidates together
            allres.update(json.loads((OUT / "s2b_dev.json").read_text())[ds])
        ok = [n for n in allres if allres[n]["fa_rows"] <= 0.015]
        pool = ok if ok else [min(allres, key=lambda n: allres[n]["fa_rows"])]
        choice[ds] = max(pool, key=lambda n: allres[n]["selection_mean_detection"])
        choice[f"{ds}_rule_note"] = "FA <= 1.5% then max selection detection" if ok else "no candidate met FA <= 1.5%: lowest FA taken"
    (OUT / f"s2b_dev{sfx}.json").write_text(json.dumps(res, indent=1, default=str))
    (OUT / f"s2b_choice{sfx}.json").write_text(json.dumps(choice, indent=1))
    print(choice)


if __name__ == "__main__":
    main()
