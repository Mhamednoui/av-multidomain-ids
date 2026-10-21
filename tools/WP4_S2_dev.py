"""WP4 S2 development on VALIDATION only (D10): fit layers on benign train, threshold on benign val, per-family val detection.
Variants of the allow-list (rare-port pooling 1 / 5 / 50, host support 50 / 200 / 1000) are compared on validation (mean detection over the 11
evaluable families at the 1% budget). Writes results/WP4/s2_dev_val_grid2.json. Never touches the test split."""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common.metrics import auc
from network import l1
from tools.WP4_S2_lib import load_d10

EVAL = ["Bot", "DDoS-LOIC-HTTP", "DoS-GoldenEye", "DoS-Hulk", "DoS-SlowHTTPTest", "DoS-Slowloris", "FTP-Patator", "SSH-Patator", "PortScan",
        "Web-BruteForce", "Web-XSS"]


def run(L, tr, vb, va):
    L.fit(tr).calibrate(vb)
    sc = L.calibrator.transform(L.raw_scores(va))
    y = (va.family != "BENIGN").to_numpy()
    al = sc >= L.threshold
    out = {"fa_val": float(al[~y].mean()), "auc_val": auc(y, sc)}
    for f in EVAL:
        out[f] = float(al[(va.family == f).to_numpy()].mean())
    out["mean_det"] = float(np.mean([out[f] for f in EVAL]))
    return out


if __name__ == "__main__":
    d = load_d10()
    tr = d[(d.family == "BENIGN") & (d.split == "train")]
    vb = d[(d.family == "BENIGN") & (d.split == "val")]
    va = d[d.split == "val"]
    res = {}
    layers = []
    for rp in (50, 200, 1000):
        for ms in (1000, 3000, 10000):
            for cls, nm in ((l1.AllowPair, "pair"), (l1.AllowService, "service")):
                L = cls(rare_port=rp)
                L.min_support = ms
                L.name = "net.allow_%s[rare=%d,support=%d]" % (nm, rp, ms)
                layers.append(L)
    pass
    for L in layers:
        res[L.name] = run(L, tr, vb, va)
        print(L.name, {k: round(v, 3) for k, v in res[L.name].items() if k in ("fa_val", "auc_val", "mean_det", "PortScan", "DoS-Hulk")}, flush=True)
    json.dump(res, open("results/WP4/s2_dev_val_grid2.json", "w"), indent=1)
