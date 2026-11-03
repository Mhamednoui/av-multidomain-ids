"""WP8 S6 evaluation: blame candidates V3 / A1 / A2 / A3 on the V31_val vehicle-block runs (notes/WP8_v31.md "S6 round 1").

Inputs (built by tools/WP8_S6_kitti.py, tools/WP8_S6_comma.py): residual tables of 13 TRAIN drives / 13 TRAIN routes (fits) and the 10 + 8 V31_val drives / routes (judged).
Fits (train only): SigmaModel(bias="linear") per edge on the clean phase-0 rows (K: all train drives, out-of-fold for the calibration; C: per gyro-rate class, out-of-fold), per-edge ECDF
+ tie-safe 1 % tau (crossdomain.consistency.Calibration) on the out-of-fold clean |z|, inertial sigma / tau on the clean train runs (K).
Outcome per run: the vehicle block alone: tick alarm = own alarm of the vehicle domains (K: GPS domain or cross; C: cross); v3 correlator (m 2, w 5, gap 15, majority_decided),
v3 tick_blame (cross verdict overrides on cross-alarm ticks, fallback to the strongest own alarm); detected event = the first confirmed event holding a labelled alarm tick; blame correct
if in the true-sensor set, wrong if another domain, else undecided. Detection is identical across candidates by construction (alarms do not depend on blame): B4 is checked.
Usage: python -I -u -W ignore tools/WP8_S6_eval.py <tag> [--round r1]   Output: results/WP8/S6/<tag>_eval.json, results/WP8/scores/S6/{kitti,comma}_val_<tag>.npz
"""
import json
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True

import numpy as np

import WP6_S2_comma as SC
import WP8_lib as L8
from common.config import DATA_EXTRA
from crossdomain import blame31 as B
from crossdomain import consistency as CS
from crossdomain import witness as W
from fusion import correlator as CR
from system.cross_runner import DOMAIN_OF as K_DOMAIN_OF
from system.cross_runner import edge_list

CACHE = DATA_EXTRA / "cache_v3" / "WP8" / "S6"
OUT = ROOT / "results" / "WP8" / "S6"
SCORES = ROOT / "results" / "WP8" / "scores" / "S6"
BUDGET = 0.01
T0 = time.time()
K_TYPES_SINGLE = ["drift", "accel_drift", "doppler_spoof", "meaconing", "lidar_scale", "lidar_bias", "lidar_yaw", "can_scale", "can_offset", "can_freeze"]
C_RULE_TYPES = ["drift", "meaconing", "doppler_spoof"]
C_CAN_TYPES = ["can_scale", "can_offset", "can_freeze", "can_bus", "gnss_can"]
TRUTH = {"drift": {"gps"}, "accel_drift": {"gps"}, "doppler_spoof": {"gps"}, "meaconing": {"gps"}, "gps_can": {"gps", "can"}, "gnss_can": {"gps", "can"},
         "lidar_scale": {"lidar"}, "lidar_bias": {"lidar"}, "lidar_yaw": {"lidar"}, "can_scale": {"can"}, "can_offset": {"can"}, "can_freeze": {"can"}, "can_bus": {"can"}}
CANDS_K = ["V3", "A1", "A2", "A3"]
CANDS_C = ["V3", "A1", "A2"]


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


# ------------------------------------------------------------------------------------------------ fits
def models_of(R, V, edges):
    out = {}
    for j, e in enumerate(edges):
        r, v = R[:, j], V[:, j]
        ok = np.isfinite(r) & np.isfinite(v)
        out[e.name] = W.SigmaModel(bias="linear").fit(r[ok], v[ok])
    return out


def z_of(R, V, edges, models):
    return np.column_stack([models[e.name].z(R[:, j], V[:, j]) for j, e in enumerate(edges)])


def load_k():
    train, val = {}, {}
    for f in sorted(CACHE.glob("kitti_*.pkl")):
        d = pickle.load(open(f, "rb"))
        (train if d["split"] == "train" else val)[d["drive"]] = d["records"]
    lock = json.loads((ROOT / "locks" / "V31_val.json").read_text())["domains"]["kitti_vehicle_block"]
    assert sorted(train) == sorted(lock["train"]) and sorted(val) == sorted(lock["val"])
    L8.assert_not_h31(list(val) and [str(CACHE / f"kitti_{d}.pkl") for d in val])
    return train, val


def fit_k(train):
    edges = edge_list()
    clean = {d: [r for r in rs if r["family"] == "none"] for d, rs in train.items()}
    clean = {d: rs for d, rs in clean.items() if rs}
    p0 = {d: [r for r in rs if r["phase"] == 0] for d, rs in clean.items()}
    stack = lambda rs, k: np.vstack([r[k] for r in rs])
    oof = {}
    for d in clean:
        rs = [r for e, x in p0.items() if e != d for r in x]
        oof[d] = models_of(stack(rs, "R"), stack(rs, "V"), edges)
    allp0 = [r for x in p0.values() for r in x]
    models = models_of(stack(allp0, "R"), stack(allp0, "V"), edges)
    Sall = np.vstack([np.abs(z_of(r["R"], r["V"], edges, oof[d])) for d, rs in clean.items() for r in rs])
    cal = CS.Calibration(BUDGET).fit(Sall)
    inertial = B.InertialModel().fit([(r["speed"], r["A"]) for rs in clean.values() for r in rs])
    return {"edges": edges, "models": models, "cal": cal, "inertial": inertial}


def load_c():
    train, val = {}, {}
    for f in sorted(CACHE.glob("comma_*.pkl")):
        d = pickle.load(open(f, "rb"))
        (train if d["split"] == "train" else val)[d["route"]] = d
    lock = json.loads((ROOT / "locks" / "V31_val.json").read_text())["domains"]["comma"]["rav4_chunk1"]
    assert sorted(train) == sorted(lock["train"]) and sorted(val) == sorted(lock["val"])
    return train, val


def fit_c(train):
    edges = [CS.Edge(*n.split(" ")[0].split("-"), n.split(" ")[1], n) for n in SC.EDGE_NAMES]
    cls = {n: ("g10" if d["gyro_hz"] <= 20 else "g100") for n, d in train.items()}
    models, S = {}, []
    for k in ("g10", "g100"):
        names = [n for n in train if cls[n] == k]
        stack = lambda ns, key: np.vstack([train[n][key] for n in ns])
        models[k] = models_of(stack(names, "route_R"), stack(names, "route_V"), edges)
        for n in names:
            rest = [m for m in names if m != n]
            if rest:
                mo = models_of(stack(rest, "route_R"), stack(rest, "route_V"), edges)
                S.append(np.abs(z_of(train[n]["route_R"], train[n]["route_V"], edges, mo)))
    cal = CS.Calibration(BUDGET).fit(np.vstack(S))
    return {"edges": edges, "models": models, "cal": cal}


# ------------------------------------------------------------------------------------------------ run outcome
def event_outcome(alarm, own, names, X, cross_blame, cross_alarm, t, onset_t, truth):
    blame = CR.tick_blame(names, X, own, cross_blame, cross_alarm)
    cor = CR.TemporalCorrelator(m=2, w=5, gap=15, corroborate=False, blame_rule="majority_decided", safe_stop_min_domains=2)
    ev = cor.events(alarm, own, names, blame)
    lab = (t >= onset_t) if np.isfinite(onset_t) else np.zeros(len(t), bool)
    conf = np.zeros(len(alarm), bool)
    for e in ev:
        conf[np.flatnonzero(alarm[e.start:e.end + 1]) + e.start] = True
    hit = np.flatnonzero(conf & lab)
    out = {"events": len(ev), "alarm_ticks": int(alarm.sum()), "detected": False, "blamed": None, "blame": None}
    if len(hit):
        e0 = next(e for e in ev if e.start <= hit[0] <= e.end)
        out.update(detected=True, blamed=e0.blamed, delay=int(hit[0] - np.flatnonzero(lab)[0]),
                   blame="undecided" if e0.blamed == "undecided" else ("correct" if e0.blamed in truth else "wrong"))
    return out, blame


def cross_arrays(Z, cal):
    S = np.abs(Z)
    es = cal.edge_scores(S)
    al = es >= cal.tau
    return S, es, al, np.isfinite(S)


def eval_k(fit, val):
    edges, inert = fit["edges"], fit["inertial"]
    graphs = {"A1": (B.Blame31(B.graph_k(False), B.EQUAL_COST), False), "A2": (B.Blame31(B.graph_k(False), B.PRIOR_COST), False),
              "A3": (B.Blame31(B.graph_k(True), B.PRIOR_COST), True)}
    rows, store = [], []
    for d, rs in val.items():
        for r in rs:
            Z = z_of(r["R"], r["V"], edges, fit["models"])
            S, es, al, ob = cross_arrays(Z, fit["cal"])
            cross_alarm = al.any(axis=1)
            cross_score = es.max(axis=1)
            gps_alarm = np.asarray(r["gps_alarm"], bool)
            alarm = cross_alarm | gps_alarm
            own = np.column_stack([gps_alarm, cross_alarm])
            X = np.column_stack([r["gps_score"], cross_score])
            names = ["gps", "cross"]
            truth = TRUTH.get(r["family"], set())
            ia, io = inert.edges(r["speed"], r["A"], cross_alarm)
            cb = {"V3": CS.blame(edges, al, ob, K_DOMAIN_OF)}
            for c, (bl, use) in graphs.items():
                cb[c] = B.blame_run(bl, al, ob, cross_alarm, ia if use else None, io if use else None)
            cbs = {c: np.array([None if x is None else str(x) for x in v], object) for c, v in cb.items()}
            row = {"drive": d, "phase": r["phase"], "family": r["family"], "n": len(r["t"]), "inertial_alarm_ticks": int(ia.any(axis=1).sum())}
            blame_ticks = {}
            for c in CANDS_K:
                o, bt = event_outcome(alarm, own, names, X, cbs[c], cross_alarm, r["t"], r["onset_t"], truth)
                row[c] = o
                blame_ticks[c] = bt
            if r["family"] != "none":
                assert len({(row[c]["detected"], row[c]["events"], row[c]["alarm_ticks"]) for c in CANDS_K}) == 1
            rows.append(row)
            store.append({"id": f"{d}/p{r['phase']}/{r['family']}", "group": d, "family": r["family"], "t": r["t"], "es": es.astype(np.float32), "alarm": al, "gps_alarm": gps_alarm,
                          "label": (r["t"] >= r["onset_t"]) if np.isfinite(r["onset_t"]) else np.zeros(len(r["t"]), bool),
                          **{f"blame_{c}": np.array([("" if x is None else str(x)) for x in blame_ticks[c]]) for c in CANDS_K}})
    return rows, store


def eval_c(fit, val):
    edges = fit["edges"]
    blamers = {"A1": B.Blame31(B.graph_c(), B.EQUAL_COST), "A2": B.Blame31(B.graph_c(), B.PRIOR_COST)}
    rows, store = [], []
    for n, d in val.items():
        k = "g10" if d["gyro_hz"] <= 20 else "g100"
        for ep in d["episodes"]:
            Z = z_of(ep["R"], ep["V"], edges, fit["models"][k])
            S, es, al, ob = cross_arrays(Z, fit["cal"])
            cross_alarm = al.any(axis=1)
            names = ["cross"]
            own = cross_alarm[:, None]
            X = es.max(axis=1)[:, None]
            truth = TRUTH.get(ep["family"], set())
            cb = {"V3": CS.blame(edges, al, ob, SC.DOMAIN_OF)}
            for c, bl in blamers.items():
                cb[c] = B.blame_run(bl, al, ob, cross_alarm)
            cbs = {c: np.array([None if x is None else str(x) for x in v], object) for c, v in cb.items()}
            row = {"route": n, "window": ep["window"], "rep": ep["rep"], "family": ep["family"], "n": len(ep["t"])}
            blame_ticks = {}
            for c in CANDS_C:
                o, bt = event_outcome(cross_alarm, own, names, X, cbs[c], cross_alarm, ep["t"], ep["onset_t"], truth)
                row[c] = o
                blame_ticks[c] = bt
            if ep["family"] != "none":
                assert len({(row[c]["detected"], row[c]["events"], row[c]["alarm_ticks"]) for c in CANDS_C}) == 1
            rows.append(row)
            store.append({"id": f"{n}/w{ep['window']}/{ep['family']}/{ep['rep']}", "group": n, "family": ep["family"], "t": ep["t"], "es": es.astype(np.float32), "alarm": al,
                          "label": (ep["t"] >= ep["onset_t"]) if np.isfinite(ep["onset_t"]) else np.zeros(len(ep["t"]), bool),
                          **{f"blame_{c}": np.array([("" if x is None else str(x)) for x in blame_ticks[c]]) for c in CANDS_C}})
    return rows, store


# ------------------------------------------------------------------------------------------------ metrics
def rates(rows, fam, cand):
    det = [r[cand] for r in rows if r["family"] == fam and r[cand]["detected"]]
    n_all = sum(1 for r in rows if r["family"] == fam)
    if not det:
        return {"runs": n_all, "detected": 0, "correct": None, "wrong": None, "undecided": None}
    b = [x["blame"] for x in det]
    return {"runs": n_all, "detected": len(det), "correct": b.count("correct") / len(det), "wrong": b.count("wrong") / len(det), "undecided": b.count("undecided") / len(det)}


def mean_over(rows, fams, cand):
    rs = [rates(rows, f, cand) for f in fams]
    rs = [r for r in rs if r["detected"]]
    if not rs:
        return {"types": 0, "correct": None, "wrong": None}
    return {"types": len(rs), "correct": float(np.mean([r["correct"] for r in rs])), "wrong": float(np.mean([r["wrong"] for r in rs]))}


def detection_rate(rows, fams, cand):
    return float(np.mean([r[cand]["detected"] for r in rows if r["family"] in fams]))


def summary(rows, cand, kind):
    if kind == "K":
        s = {"gps_can": rates(rows, "gps_can", cand), "B3": mean_over(rows, K_TYPES_SINGLE, cand),
             "types": {f: rates(rows, f, cand) for f in K_TYPES_SINGLE + ["gps_can"]}, "detection_single": detection_rate(rows, K_TYPES_SINGLE, cand),
             "detection_gps_can": detection_rate(rows, ["gps_can"], cand)}
    else:
        s = {"B2": mean_over(rows, C_RULE_TYPES, cand), "C3": mean_over(rows, C_CAN_TYPES, cand),
             "types": {f: rates(rows, f, cand) for f in SC.ATTACKS}, "detection_gnss": detection_rate(rows, C_RULE_TYPES, cand)}
    return s


def boot(rows, groupkey, fn, B_=2000, seed=31):
    groups = sorted({r[groupkey] for r in rows})
    by = {g: [r for r in rows if r[groupkey] == g] for g in groups}
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(B_):
        pick = rng.integers(0, len(groups), len(groups))
        rs = [r for i in pick for r in by[groups[i]]]
        v = fn(rs)
        if v is not None and np.all(np.isfinite(v)):
            vals.append(v)
    if not vals:
        return None
    return np.percentile(np.asarray(vals), [2.5, 97.5], axis=0).tolist()


def cis(rows, kind, cand):
    if kind == "K":
        def f1(rs):
            r = rates(rs, "gps_can", cand)
            return None if not r["detected"] else [r["correct"], r["wrong"]]

        def f3(rs):
            m = mean_over(rs, K_TYPES_SINGLE, cand)
            return None if not m["types"] else [m["correct"], m["wrong"]]
        return {"gps_can_correct_wrong": boot(rows, "drive", f1), "B3_correct_wrong": boot(rows, "drive", f3)}

    def f2(rs):
        m = mean_over(rs, C_RULE_TYPES, cand)
        return None if not m["types"] else [m["correct"], m["wrong"]]
    return {"B2_correct_wrong": boot(rows, "route", f2)}


def judge(sk, sc, ref_k, ref_c):
    """Pre-registered rules on point estimates; ref_* = the V3 summaries."""
    r = {}
    g = sk["gps_can"]
    r["B1"] = bool(g["detected"] and g["wrong"] <= 0.25 and g["correct"] >= 0.40)
    r["B3"] = bool(sk["B3"]["types"] and sk["B3"]["correct"] >= 0.75 and sk["B3"]["wrong"] <= 0.10)
    b2 = sc["B2"]
    r["B2"] = bool(b2["types"] == 3 and b2["correct"] >= 0.60 and b2["wrong"] <= 0.15 and all(sc["types"][t]["detected"] and sc["types"][t]["wrong"] <= 0.25 for t in C_RULE_TYPES))
    c3, c3v = sc["C3"], ref_c["C3"]
    r["C3"] = bool(c3["types"] and c3v["types"] and c3["correct"] >= c3v["correct"] - 0.05)
    r["B4"] = bool(abs(sk["detection_single"] - ref_k["detection_single"]) <= 0.005 and abs(sk["detection_gps_can"] - ref_k["detection_gps_can"]) <= 0.005
                   and abs(sc["detection_gnss"] - ref_c["detection_gnss"]) <= 0.005)
    r["n_met"] = int(sum(r[k] for k in ("B1", "B2", "B3", "C3", "B4")))
    return r


def save_scores(store, name):
    SCORES.mkdir(parents=True, exist_ok=True)
    lens = np.array([len(s["t"]) for s in store])
    arr = {"ids": np.array([s["id"] for s in store]), "groups": np.array([s["group"] for s in store]), "families": np.array([s["family"] for s in store]), "lens": lens,
           "t": np.concatenate([s["t"] for s in store]), "es": np.vstack([s["es"] for s in store]), "alarm": np.vstack([s["alarm"] for s in store]),
           "label": np.concatenate([s["label"] for s in store])}
    for k in store[0]:
        if k.startswith("blame_"):
            arr[k] = np.concatenate([s[k] for s in store])
    np.savez_compressed(SCORES / name, **arr)


def main(tag):
    OUT.mkdir(parents=True, exist_ok=True)
    out = {"tag": tag, "candidates_K": CANDS_K, "candidates_C": CANDS_C}
    tk, vk = load_k()
    fk = fit_k(tk)
    out["K_fit"] = {"tau_cross": float(fk["cal"].tau), "inertial_tau": fk["inertial"].tau, "inertial_sigma": fk["inertial"].sigma.tolist(), "train_drives": sorted(tk)}
    log("K fitted", out["K_fit"]["tau_cross"], out["K_fit"]["inertial_tau"])
    rk, sk = eval_k(fk, vk)
    save_scores(sk, f"kitti_val_{tag}.npz")
    tc, vc = load_c()
    fc = fit_c(tc)
    out["C_fit"] = {"tau_cross": float(fc["cal"].tau), "train_routes": sorted(tc)}
    log("C fitted", out["C_fit"]["tau_cross"])
    rc, sc = eval_c(fc, vc)
    save_scores(sc, f"comma_val_{tag}.npz")
    out["K"] = {c: {**summary(rk, c, "K"), "ci": cis(rk, "K", c)} for c in CANDS_K}
    out["C"] = {c: {**summary(rc, c, "C"), "ci": cis(rc, "C", c)} for c in CANDS_C}
    out["rules"] = {c: judge(out["K"][c], out["C"][c if c in CANDS_C else "A2"], out["K"]["V3"], out["C"]["V3"]) for c in CANDS_K}
    out["runs"] = {"K": len(rk), "C": len(rc)}
    (OUT / f"{tag}_eval.json").write_text(json.dumps(out, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)))
    pickle.dump({"K": rk, "C": rc}, open(CACHE / f"{tag}_rows.pkl", "wb"), protocol=4)
    log("done", {c: out["rules"][c] for c in CANDS_K})


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "r1")
