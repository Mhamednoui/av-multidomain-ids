"""WP4 S3 development on D10 VALIDATION only: choose the window W in {1, 5} minutes per L2a layer.
Rule (fixed in notes/WP4_network.md before any score): W with the larger mean flow-unit detection over the layer's target families on
the val MIXED stream, at the 1% budget set on the benign-only val stream; tie -> smaller W. Test is never read.
Also records (diagnostics, not choices): TRW classic threshold ln(99), dos_rate absolute-count variant.
Usage: python -u -W ignore tools/WP4_S3_dev.py
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from network import l2a
from tools.WP4_S3_lib import RES, add_scores, fit_calibrate, flow_eval, load, log, stream, window_eval

FAMS = ["Bot", "DDoS-LOIC-HTTP", "DoS-GoldenEye", "DoS-Hulk", "DoS-SlowHTTPTest", "DoS-Slowloris", "FTP-Patator", "SSH-Patator",
        "PortScan", "Web-BruteForce", "Web-XSS"]


def main():
    d = load("D10")
    tr, vb, vm = stream(d, "train", True), stream(d, "val", True), stream(d, "val")
    log("train benign", len(tr), "val benign", len(vb), "val mixed", len(vm))
    res = {"W": {}, "chosen": {}}
    for W in (1, 5):
        layers = l2a.all_layers({L.name: W for L in l2a.all_layers()})
        fit_calibrate(layers, tr, vb)
        add_scores(vm, layers)
        res["W"][W] = {}
        for L in layers:
            fe = flow_eval(L, vm, FAMS)
            we = window_eval(L, vm, FAMS)
            tg = [f for f in L.targets if f in fe["detection"]]
            res["W"][W][L.name] = {"flow": fe, "window": we, "target_mean": float(np.mean([fe["detection"][f] for f in tg])),
                                   "target_mean_window": float(np.mean([we["detection"][f] for f in tg if f in we["detection"]]))}
            log(W, L.name, "FA %.4f" % fe["fa_benign"], {k: round(v, 2) for k, v in fe["detection"].items()}, "target %.3f" % res["W"][W][L.name]["target_mean"])
        if W == 1:
            r = vm[layers[1].score_col].to_numpy()
            res["trw_classic_val"] = {"threshold": l2a.TRW_CLASSIC, "note": "W=1; detection per family at ln(99)", "detection": {
                f: float((r[(vm["family"].astype(str) == f).to_numpy()] >= l2a.TRW_CLASSIC).mean()) for f in ("PortScan", "SSH-Patator", "FTP-Patator")},
                "fa_benign": float((r[(vm["family"].astype(str) == "BENIGN").to_numpy()] >= l2a.TRW_CLASSIC).mean())}
            log(res["trw_classic_val"])
    for n in res["W"][1]:
        a, b = res["W"][1][n]["target_mean"], res["W"][5][n]["target_mean"]
        res["chosen"][n] = 5 if b > a + 1e-9 else 1
    log("chosen", res["chosen"])
    json.dump(res, open(os.path.join(RES, "s3_dev_val.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
