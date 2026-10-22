"""WP3 S2 evaluation: v2 baseline on old vs calibrated phantoms (A5) and L1 sensor geometry (Part B).

Needs tools/WP3_S2_build.py (tables v2l1 and ray for val + test drives).
  dev    validation only: thresholds, detection per attack on VAL, no test row is read.
  final  ONE verdict run on test (refuses to run twice: delete results/WP3/S2/final_done.flag only with the supervisor's
         approval): L1 layers calibrated on clean VAL scans (1 %), test detection per attack, FA on clean test scans,
         harness ablation (common/evaluate.py), per-drive FA spread, v2 baseline on old and calibrated phantoms.
Outputs: results/WP3/S2/{dev,final}.json, results/WP3/S2/ablation.{json,md} (final).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS
from common.evaluate import EvalSet, evaluate_domain
from common.metrics import budget_threshold
from lidar import geometry as G
from lidar import l1 as L1
from lidar.data import CACHE, drives_of
from lidar.features import feature_names_temporal

OUT = CACHE / "S2"
RES = RESULTS / "WP3" / "S2"
V2 = Path(__file__).resolve().parent.parent.parent / "codes_v2"
NAMES = feature_names_temporal()
TYPE_V2 = {"PointDrop": "PointDrop", "IntensitySpoof": "IntensitySpoof", "GhostCluster": "BoxCloud"}


def v2_model():
    meta = json.load(open(V2 / "lidar" / "meta.json"))
    m = xgb.XGBClassifier()
    m.load_model(str(V2 / "lidar" / "model.json"))
    m.set_params(device="cpu", n_jobs=4)
    return m, [NAMES.index(f) for f in meta["features"]]


def load_part(part, model, cols):
    """(v2 rows, ray rows) as DataFrames with stats columns and the v2 score."""
    frames, rays = [], []
    for d in drives_of(part):
        a = pd.read_pickle(OUT / f"v2l1_{d}.pkl")
        c = pd.read_pickle(CACHE / "train4" / f"{d}.pkl")
        for col in ("scan", "cls", "mode"):
            assert (a["meta"][col].to_numpy() == c["meta"][col].to_numpy()).all(), (d, col)
        assert (c["X"][:, 0] == a["meta"]["n_pts"].to_numpy()).all(), d       # same attacked scans as the cached descriptors
        df = a["meta"].copy()
        for i, nme in enumerate(G.STAT_NAMES):
            df[nme] = a["stats"][:, i]
        df["v2"] = 1 - model.predict_proba(c["X"][:, cols])[:, 0]
        frames.append(df)
        b = pd.read_pickle(OUT / f"ray_{d}.pkl")
        rd = b["meta"].copy()
        for i, nme in enumerate(G.STAT_NAMES):
            rd[nme] = b["stats"][:, i]
        rd["v2"] = 1 - model.predict_proba(b["X"][:, cols])[:, 0]
        rays.append(rd)
    return pd.concat(frames, ignore_index=True), pd.concat(rays, ignore_index=True)


def evalset_rows(v2rows, rayrows):
    """One table of scans: normal + v2 attacks + ray-cast phantoms (onset timing), columns attack_type, y, group, t."""
    a = v2rows.copy()
    a["attack_type"] = a["cls"].map(lambda c: "normal" if c == "Normal" else TYPE_V2[c])
    a["t"] = a["scan"].str.split("/").str[1].str.replace(".bin", "").astype(float) * 0.1032
    r = rayrows[rayrows["timing"] == "onset"].copy()
    r = r[r["n_spoofed"] > 0]
    r["attack_type"] = r["variant"] + "_" + r["mode"] + "_" + r["band"]
    r["t"] = r["scan"].str.split("/").str[1].str.replace(".bin", "").astype(float) * 0.1032
    cols = ["drive", "scan", "attack_type", "t", "v2"] + G.STAT_NAMES
    df = pd.concat([a[cols], r[cols]], ignore_index=True)
    df["y"] = (df["attack_type"] != "normal").astype(int)
    return df


def make_layers(val):
    layers = {"v2": None}
    from common.layer import Layer

    class V2(Layer):
        domain, layer_id, kind, name = "lidar", "L4", "supervised", "v2_descriptor"
        def raw_scores(self, samples):
            return np.asarray(samples["v2"], float)
    layers["v2"] = V2()
    for r in L1.rules():
        layers[r.name] = r
    layers["union"] = L1.L1Union()
    normal = val[val["y"] == 0]
    for lay in layers.values():
        lay.calibrate(normal, 0.01)
    return layers


def evidence(layers, df):
    return {("v2" if k == "v2" else f"L1_{k}"): lay.score(df) for k, lay in layers.items()}


def to_set(df, ev):
    return EvalSet(evidence=ev, y=df["y"].to_numpy(), attack_type=df["attack_type"].to_numpy(),
                   group=df["drive"].to_numpy(), t=df["t"].to_numpy())


def s1_ops(model_scores, df, vnorm_scores, fprs=(0.01, 0.02)):
    """S1 convention (v2): threshold = quantile(1 - fpr) of val normal scores, alarm = score > threshold."""
    out = {}
    for fpr in fprs:
        thr = float(np.quantile(vnorm_scores, 1 - fpr))
        out[fpr] = thr
    return out


def phantom_table(rayrows, thr):
    """v2 detection per variant / mode / band / timing, with median injected points."""
    res = {}
    g = rayrows[rayrows["n_spoofed"] > 0].groupby(["variant", "mode", "band", "timing"])
    for key, x in g:
        res["|".join(key)] = {"n": int(len(x)), "median_points": float(x["n_spoofed"].median()),
                              "det": {str(f): float((x["v2"] > t).mean()) for f, t in thr.items()}}
    return res


def l1_phantom_table(rayrows, layers):
    res = {}
    ev = layers["union"].score(rayrows)
    alarm_u = np.array([e.alarm for e in ev])
    alarms = {k: np.array([e.alarm for e in layers[k].score(rayrows)]) for k in ("ring_total", "ring_sector", "single_return")}
    rayrows = rayrows.assign(a_union=alarm_u, **{f"a_{k}": v for k, v in alarms.items()})
    for key, x in rayrows[(rayrows["n_spoofed"] > 0) & (rayrows["timing"] == "onset")].groupby(["variant", "mode", "band"]):
        res["|".join(key)] = {"n": int(len(x)), "union": float(x["a_union"].mean()),
                              **{k: float(x[f"a_{k}"].mean()) for k in alarms}}
    return res


def main(mode):
    if mode == "final" and (RES / "final_done.flag").exists():
        sys.exit("final already run: the test verdict is taken once (RULES 5.2)")
    model, cols = v2_model()
    val_v2, val_ray = load_part("val", model, cols)
    val = evalset_rows(val_v2, val_ray)
    layers = make_layers(val)
    res = {"mode": mode, "thresholds": {k: {"score_thr": l.threshold, "raw_thr_quantile": None} for k, l in layers.items()},
           "val_normal": int((val["y"] == 0).sum())}
    ev_val = evidence(layers, val)
    # detection on VAL per attack type for each layer
    det_val = {}
    for k, evs in ev_val.items():
        al = np.array([e.alarm for e in evs])
        det_val[k] = {"FA": float(al[val["y"] == 0].mean()), **{t: float(al[(val["attack_type"] == t).to_numpy()].mean())
                                                              for t in sorted(set(val["attack_type"])) if t != "normal"}}
    res["val_detection"] = det_val
    vnorm = val_v2.loc[val_v2["cls"] == "Normal", "v2"].to_numpy()
    thr = {f: float(np.quantile(vnorm, 1 - f)) for f in (0.01, 0.02)}
    res["val_v2_phantoms"] = phantom_table(val_ray, thr)
    res["val_l1_phantoms"] = l1_phantom_table(val_ray, layers)
    if mode == "dev":
        (RES / "dev.json").write_text(json.dumps(res, indent=1, default=float))
        print(json.dumps({k: {t: round(v, 3) for t, v in d.items()} for k, d in det_val.items()}, indent=0))
        return
    # ---- final: test, once
    test_v2, test_ray = load_part("test", model, cols)
    test = evalset_rows(test_v2, test_ray)
    ev_test = evidence(layers, test)
    ab = evaluate_domain("L1_ablation", to_set(val, ev_val), to_set(test, ev_test), wp="WP3", out_dir=RES)
    res["test_normal"] = int((test["y"] == 0).sum())
    det = {}
    for k, evs in ev_test.items():
        al = np.array([e.alarm for e in evs])
        norm = (test["y"] == 0).to_numpy()
        det[k] = {"FA": float(al[norm].mean()),
                  "FA_by_drive": {d: float(al[norm & (test["drive"] == d).to_numpy()].mean()) for d in sorted(set(test["drive"]))},
                  **{t: float(al[(test["attack_type"] == t).to_numpy()].mean()) for t in sorted(set(test["attack_type"])) if t != "normal"}}
    res["test_detection"] = det
    res["test_v2_phantoms"] = phantom_table(test_ray, thr)
    res["test_l1_phantoms"] = l1_phantom_table(test_ray, layers)
    # v2 + L1 at the common 1 % (max of calibrated scores), per-drive FA
    sv = np.maximum(np.array([e.score for e in ev_val["v2"]]), np.array([e.score for e in ev_val["L1_union"]]))
    st = np.maximum(np.array([e.score for e in ev_test["v2"]]), np.array([e.score for e in ev_test["L1_union"]]))
    t_or = budget_threshold(sv[val["y"] == 0], 0.01)
    al = st >= t_or
    norm = (test["y"] == 0).to_numpy()
    res["v2_or_L1_1pct"] = {"FA": float(al[norm].mean()),
                            "FA_by_drive": {d: float(al[norm & (test["drive"] == d).to_numpy()].mean()) for d in sorted(set(test["drive"]))},
                            **{t: float(al[(test["attack_type"] == t).to_numpy()].mean()) for t in sorted(set(test["attack_type"])) if t != "normal"}}
    # clean-scan statistics of the L1 stats on val / test normals
    res["stat_summary"] = {p: {s: {"mean": float(d.loc[d.y == 0, s].mean()), "q99": float(d.loc[d.y == 0, s].quantile(0.99)),
                                   "max": float(d.loc[d.y == 0, s].max())} for s in G.STAT_NAMES} for p, d in (("val", val), ("test", test))}
    (RES / "final.json").write_text(json.dumps(res, indent=1, default=float))
    (RES / "final_done.flag").write_text("L1 + A5 verdict run on test executed once")
    print("final written", {k: round(v["FA"], 4) for k, v in det.items()})


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dev")
