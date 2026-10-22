"""WP3 S1: reproduce the v2 LiDAR numbers on the v3 data layer (acceptance A1-A4) and score the
WP3 ray-cast phantoms / persistent episodes with the v2 model (baseline for later steps).

Run from codes_v3/ after tools/WP3_S1_build.py. GPU used for the retraining (locks/gpu.lock).
Outputs: results/WP3/S1_reproduction.json (all numbers); the retrained models are cached under
../data_extra/cache_v3/WP3. The retraining stage is cached in results/WP3/cache/a3.json.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS, SEED
from common.metrics import classification_summary
from lidar.data import CACHE, DRIVES, SCENE, TEST, VAL, part_of
from lidar.features import feature_names, feature_names_temporal
from lidar.sequence import episode_detected, first_alarm_scan, rolling_logodds
from lidar.train_xgb import search

V2 = Path(__file__).resolve().parent.parent.parent / "codes_v2"
OUT = RESULTS / "WP3"
CLASSES = ["Normal", "PointDrop", "IntensitySpoof", "GhostCluster"]
NAMES, BASE = feature_names_temporal(), feature_names()


def load_kind(kind, drives):
    parts = [pd.read_pickle(CACHE / kind / f"{d}.pkl") for d in drives]
    return pd.concat([p["meta"] for p in parts], ignore_index=True), np.vstack([p["X"] for p in parts])


def train4():
    """v3 4-class frame per part (sorted as v2)."""
    frames = []
    for part in ("train", "val", "test"):
        meta, X = load_kind("train4", [d for d in DRIVES if part_of(d) == part])
        df = pd.DataFrame(X, columns=NAMES)
        for c in meta.columns:
            df[c] = meta[c].to_numpy()
        df["scene"] = df["drive"].map(SCENE)
        df["part"] = part
        frames.append(df)
    full = pd.concat(frames, ignore_index=True).sort_values(["drive", "scan", "cls"], kind="stable")
    full = full.reset_index(drop=True)
    return {p: full[full["part"] == p].reset_index(drop=True) for p in ("train", "val", "test")}


def a1_identity(frames):
    res = {}
    for part, df in frames.items():
        v2 = pd.read_pickle(V2 / "splits" / f"lidar_{part}.pkl")
        r = {"rows_v3": len(df), "rows_v2": len(v2)}
        if len(df) == len(v2):
            keys = all((df[c].to_numpy() == v2[c].to_numpy()).all() for c in ("drive", "scan", "cls", "mode"))
            a, b = df[NAMES].to_numpy(np.float64), v2[NAMES].to_numpy(np.float64)
            r.update(keys_equal=bool(keys), max_abs_diff=float(np.abs(a - b).max()),
                     allclose=bool(np.allclose(a, b, rtol=1e-5, atol=1e-6)))
        res[part] = r
    res["met"] = all(r.get("allclose") and r.get("keys_equal") for r in res.values())
    return res


def score(model, X):
    return 1 - model.predict_proba(X)[:, 0]


def ops(vs, vnorm, ts, tdf, rates=(0.01, 0.02)):
    out = {}
    normal = (tdf["cls"] == "Normal").to_numpy()
    for fpr in rates:
        thr = float(np.quantile(vs[vnorm], 1 - fpr))
        flag = ts > thr
        out[f"val_fpr_{fpr}"] = {
            "threshold": thr, "test_false_alarm_rate": float(flag[normal].mean()),
            "test_detection": {a: float(flag[(tdf["cls"] == a).to_numpy()].mean()) for a in CLASSES[1:]}}
    return out


def labels(frames):
    return {p: f["cls"].map({c: i for i, c in enumerate(CLASSES)}).to_numpy() for p, f in frames.items()}


def load_v2_models():
    meta = json.load(open(V2 / "lidar" / "meta.json"))
    m = xgb.XGBClassifier()
    m.load_model(str(V2 / "lidar" / "model.json"))
    m.set_params(device="cpu", n_jobs=4)
    return m, meta["features"], meta


def a2_v2_model(frames):
    m, feats, meta = load_v2_models()
    X = {p: f[feats].to_numpy(np.float32) for p, f in frames.items()}
    y = labels(frames)
    sv, st = score(m, X["val"]), score(m, X["test"])
    normal_t = (frames["test"]["cls"] == "Normal").to_numpy()
    res = {"deployed_temporal": bool(meta.get("temporal")),
           "test": classification_summary(y["test"], m.predict(X["test"]), CLASSES),
           "test_auc": float(roc_auc_score(~normal_t, st)),
           "ops": ops(sv, (frames["val"]["cls"] == "Normal").to_numpy(), st, frames["test"])}
    v2 = json.load(open(V2 / "results" / "lidar_operating_points.json"))
    res["v2_reference"] = {"test_auc": v2["test_auc_attack_vs_normal"],
                           "test_accuracy": json.load(open(V2 / "results" / "lidar.json"))["test"]["accuracy"],
                           "ops": {k: {"threshold": o["threshold"], "test_false_alarm_rate": o["test_false_alarm_rate"],
                                       "test_detection": o["test_detection"]}
                                   for k, o in v2["operating_points"].items() if k in ("val_fpr_0.01", "val_fpr_0.02")}}
    dacc = abs(res["test"]["accuracy"] - res["v2_reference"]["test_accuracy"])
    dauc = abs(res["test_auc"] - res["v2_reference"]["test_auc"])
    dd = max(abs(res["ops"][k]["test_detection"][a] - res["v2_reference"]["ops"][k]["test_detection"][a])
             for k in res["v2_reference"]["ops"] for a in CLASSES[1:])
    res["checks"] = {"acc_diff_pts": 100 * dacc, "auc_diff": dauc, "max_detection_diff_pts": 100 * dd,
                     "met": bool(dacc <= 0.0005 and dauc <= 0.001 and dd <= 0.005)}
    return res


def a3_retrain(frames):
    path = OUT / "cache" / "a3.json"
    if path.exists():
        return json.load(open(path))
    lock = Path(__file__).resolve().parent.parent / "locks" / "gpu.lock"
    lock.parent.mkdir(exist_ok=True)
    lock.write_text(f"WP3 S1 xgboost search {time.strftime('%Y-%m-%d %H:%M')}")
    try:
        y = labels(frames)
        res = {"variants": {}}
        models = {}
        for variant, feats in (("single_scan", BASE), ("temporal", NAMES)):
            X = {p: f[feats].to_numpy(np.float32) for p, f in frames.items()}
            model, sel = search(X["train"], y["train"], X["val"], y["val"], n_classes=4, n_iter=20, weight_power=0.5)
            models[variant] = (model, feats)
            v = {"n_features": len(feats), "selection": {k: x for k, x in sel.items() if k != "trials"}}
            for part in ("val", "test"):
                v[part] = classification_summary(y[part], model.predict(X[part]), CLASSES)
            res["variants"][variant] = v
            print(variant, v["val"]["f1_macro"], v["test"]["accuracy"], flush=True)
        chosen = max(models, key=lambda k: res["variants"][k]["val"]["f1_macro"])
        model, feats = models[chosen]
        res["deployed"] = chosen
        model.save_model(str(CACHE / "retrained_deployed.json"))
        models["single_scan"][0].save_model(str(CACHE / "retrained_single_scan.json"))
        model.set_params(device="cpu", n_jobs=4)
        X = {p: f[feats].to_numpy(np.float32) for p, f in frames.items()}
        sv, st = score(model, X["val"]), score(model, X["test"])
        normal_t = (frames["test"]["cls"] == "Normal").to_numpy()
        res["test"] = res["variants"][chosen]["test"]
        res["test_auc"] = float(roc_auc_score(~normal_t, st))
        res["ops"] = ops(sv, (frames["val"]["cls"] == "Normal").to_numpy(), st, frames["test"])
        path.parent.mkdir(exist_ok=True)
        json.dump(res, open(path, "w"))
        return res
    finally:
        lock.unlink(missing_ok=True)


def rayscore(model, feats, kind, drives):
    meta, X = load_kind(kind, drives)
    meta["score"] = score(model, X[:, [NAMES.index(f) for f in feats]])
    return meta


def a4_raycast(model, feats, thr_by_key):
    """Ray-cast detection with the v2 model: v2-protocol phantoms (A4) and WP3 near / far phantoms."""
    out = {"rayv2": {}, "rayw3": {}}
    m = rayscore(model, feats, "rayv2", TEST)
    m = m[m["n_spoofed"] > 0]
    w = rayscore(model, feats, "rayw3", TEST)
    w = w[w["n_spoofed"] > 0]
    for key, thr in thr_by_key.items():
        out["rayv2"][key] = {
            f"{mode}_{timing}": {"detection": float((g["score"] > thr).mean()), "n": int(len(g)),
                                 "median_points": float(g["n_spoofed"].median()),
                                 "by_range": {f"{lo}-{hi} m": float((g.loc[(g.range_m >= lo) & (g.range_m < hi), "score"] > thr).mean())
                                              for lo, hi in ((5, 15), (15, 25), (25, 40))}}
            for (mode, timing), g in m.groupby(["mode", "timing"])}
        out["rayw3"][key] = {
            f"{mode}_{band}_{timing}": {"detection": float((g["score"] > thr).mean()), "n": int(len(g)),
                                        "median_points": float(g["n_spoofed"].median())}
            for (mode, band, timing), g in w.groupby(["mode", "band", "timing"])}
    return out


def episodes(model, feats, single, sfeats):
    """Sequence baseline (v2 logic) on the cached persistent episodes."""
    parts = {}
    for part, drives in (("val", VAL), ("test", TEST)):
        meta, X = load_kind("episodes", drives)
        s_t = score(model, X[:, [NAMES.index(f) for f in feats]])
        s1 = score(single, X[:, [NAMES.index(f) for f in sfeats]])
        meta["scan_score"] = np.maximum(s_t, s1)
        meta["seq"] = np.nan
        for _, idx in meta.groupby(["drive", "name", "draw"]).groups.items():
            idx = np.array(sorted(idx, key=lambda i: meta.at[i, "k"]))
            meta.loc[idx, "seq"] = rolling_logodds(meta.loc[idx, "scan_score"].to_numpy())
        parts[part] = meta
    v = parts["val"]
    thr = float(np.quantile(v.loc[v["name"] == "Normal", "seq"], 0.99))
    t = parts["test"]
    normal = t["name"] == "Normal"
    out = {"threshold": thr, "test_normal_scan_fa": float((t.loc[normal, "seq"] > thr).mean()), "episodes": {}}
    for name, g in t[~normal].groupby("name"):
        al = [(e.sort_values("k")["seq"] > thr).to_numpy() for _, e in g.groupby(["drive", "draw"])]
        delays = [first_alarm_scan(a) for a in al]
        delays = [x / 10 for x in delays if x]
        out["episodes"][name] = {"n": len(al), "detected_3s": int(sum(episode_detected(a) for a in al)),
                                 "median_delay_s": float(np.median(delays)) if delays else None}
    return out


def main():
    OUT.mkdir(exist_ok=True)
    (OUT / "cache").mkdir(exist_ok=True)
    frames = train4()
    res = {"seed": SEED, "rows": {p: len(f) for p, f in frames.items()}}
    res["A1_identity"] = a1_identity(frames)
    print("A1", res["A1_identity"], flush=True)
    res["A2_v2_model_on_v3_layer"] = a2_v2_model(frames)
    r2 = res["A2_v2_model_on_v3_layer"]
    print("A2", r2["checks"], r2["test"]["accuracy"], r2["test_auc"], flush=True)
    res["A3_retrained"] = a3_retrain(frames)
    print("A3", res["A3_retrained"]["deployed"], res["A3_retrained"]["test"]["accuracy"],
          res["A3_retrained"]["test_auc"], flush=True)
    model, feats, _ = load_v2_models()
    res["A4_raycast"] = a4_raycast(model, feats, {k: o["threshold"] for k, o in r2["ops"].items()})
    single = xgb.XGBClassifier()
    single.load_model(str(CACHE / "retrained_single_scan.json"))
    single.set_params(device="cpu", n_jobs=4)
    res["episodes_v2model"] = episodes(model, feats, single, BASE)
    json.dump(res, open(OUT / "S1_reproduction.json", "w"), indent=1)
    print("done")


if __name__ == "__main__":
    main()
