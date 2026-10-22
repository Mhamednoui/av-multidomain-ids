"""WP4 S5 development on VALIDATION (D10): choose the hyper-parameters of the three L3 layers. Test is never read.
Selection rule (written in notes/WP4_network.md before this run): per layer the configuration with the highest mean detection over the four
rule-blind families (Bot, Web-XSS, Web-BruteForce, DoS-Slowloris) at the 1% tie-safe benign-validation budget; ties -> higher macro over the 11
evaluable families. Feature set: "clean" is the hygiene set decided a priori; "all" is run once with the chosen config as a recorded ablation.
Usage: python -u -W ignore tools/WP4_S5_dev.py"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from network import l3
from tools.WP4_S5_lib import RES, attack_mask, benign_mask, det_at_budget, frame, load_d10, log, summarise

EVAL = ["Bot", "DDoS-LOIC-HTTP", "DoS-GoldenEye", "DoS-Hulk", "DoS-SlowHTTPTest", "DoS-Slowloris", "FTP-Patator", "SSH-Patator", "PortScan",
        "Web-BruteForce", "Web-XSS"]
GRID = [
    ("service", dict(mode="hbos", bins=16)), ("service", dict(mode="hbos", bins=32)),
    ("service", dict(mode="rz_mean", floor=0.1)), ("service", dict(mode="rz_mean", floor=0.3)),
    ("service", dict(mode="rz_top3", floor=0.1)), ("service", dict(mode="rz_top3", floor=0.3)),
    ("service", dict(mode="maha", floor=0.1)), ("service", dict(mode="maha", floor=0.3)),
    ("iforest", dict(max_samples=256, max_features=1.0)), ("iforest", dict(max_samples=2048, max_features=1.0)),
    ("iforest", dict(max_samples=256, max_features=0.5)), ("iforest", dict(max_samples=2048, max_features=0.5)),
    ("ae", dict(hidden=(32, 12, 32))), ("ae", dict(hidden=(48, 16, 6, 16, 48))),
]
# pass 2 (run after pass 1 showed AUC 0.84-0.99 but 0-1% detection of Bot / Web at 1% FA: the pooled benign tail of busy services eats the budget): the same models with
# per-service normalisation of the score (-log10 of the share of the service's own benign train scores above it); same selection rule over the union of both passes.
GRID_NORM = [
    ("service", dict(mode="maha", floor=0.1, svc_norm=True)), ("service", dict(mode="maha", floor=0.3, svc_norm=True)),
    ("service", dict(mode="rz_mean", floor=0.3, svc_norm=True)),
    ("iforest", dict(max_samples=2048, max_features=0.5, svc_norm=True)), ("iforest", dict(max_samples=256, max_features=1.0, svc_norm=True)),
    ("ae", dict(hidden=(32, 12, 32), svc_norm=True)),
]
CLS = {"service": l3.ServiceProfile, "iforest": l3.IsoForest, "ae": l3.AutoEncoder}


def main():
    extra = len(sys.argv) > 1 and sys.argv[1] == "extra"
    d, X = load_d10()
    tr = frame(d, X, benign_mask(d, "train"))
    vb = frame(d, X, benign_mask(d, "val"))
    am = attack_mask(d, "val")
    va = frame(d, X, am)
    fam = d["family"].astype(str).to_numpy()[am]
    log("benign train", len(tr), "benign val", len(vb), "attack val", len(va), {f: int((fam == f).sum()) for f in sorted(set(fam))})
    out = {"n": {"train_benign": len(tr), "val_benign": len(vb), "val_attack": int(len(va))}, "grid": []}
    path = os.path.join(RES, "s5_dev_val.json")
    if extra:                                  # second pass: extra candidates appended to the recorded first grid, same selection rule over the union
        out = json.load(open(path))
        out["extra_grid_added"] = True
    best = {}
    runs = [(k, kw, "clean") for k, kw in (GRID_NORM if extra else GRID)]
    for rec in (out["grid"] if extra else []):
        key = rec["layer"]
        if key not in best or (rec["blind4"], rec["macro"]) > (best[key]["blind4"], best[key]["macro"]):
            best[key] = rec
    for key, kw, fs in runs:
        t0 = time.time()
        L = CLS[key](feature_set_name=fs, **kw).fit(tr)
        rb, ra = L.raw_scores(vb), L.raw_scores(va)
        r = det_at_budget(rb, ra, fam)
        s = summarise(r, EVAL)
        rec = {"layer": key, "params": {k: (list(v) if isinstance(v, tuple) else v) for k, v in kw.items()}, "feature_set": fs, **s,
               "detection": r["detection"], "auc": r["auc"], "auc_all": r["auc_all"], "seconds": round(time.time() - t0, 1),
               "detection_at_fa5": det_at_budget(rb, ra, fam, budget=0.05)["detection"]}
        out["grid"].append(rec)
        log(key, kw, fs, "blind4 %.3f macro %.3f macroAUC %.3f" % (s["blind4"], s["macro"], s["macro_auc"]),
            {k: round(v, 2) for k, v in r["detection"].items()}, "%.0fs" % rec["seconds"])
        if key not in best or (s["blind4"], s["macro"]) > (best[key]["blind4"], best[key]["macro"]):
            best[key] = rec
    out["chosen"] = {k: {"params": v["params"], "blind4": v["blind4"], "macro": v["macro"]} for k, v in best.items()}
    # hygiene ablation with the chosen configs: the 76-column set
    out["all_features"] = []
    for key, rec in best.items():
        kw = {k: (tuple(v) if isinstance(v, list) else v) for k, v in rec["params"].items()}
        L = CLS[key](feature_set_name="all", **kw).fit(tr)
        r = det_at_budget(L.raw_scores(vb), L.raw_scores(va), fam)
        s = summarise(r, EVAL)
        out["all_features"].append({"layer": key, "params": rec["params"], **s, "detection": r["detection"], "auc": r["auc"], "auc_all": r["auc_all"]})
        log("ALL76", key, "blind4 %.3f macro %.3f" % (s["blind4"], s["macro"]), {k: round(v, 2) for k, v in r["detection"].items()})
    json.dump(out, open(path, "w"), indent=1)


if __name__ == "__main__":
    main()
