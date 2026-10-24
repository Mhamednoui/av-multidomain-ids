"""WP3 S7 validation round for L3 (normal-only object statistics): 3 models x 2 feature sets fitted on the 13 train drives (clean
objects only), threshold = 1 % of the clean validation scans, criterion = mean detection of the six physical attacks on the
validation attack set. Writes results/WP3/S7/dev_l3.json. Usage: python -u -W ignore tools/WP3_S7_dev_l3.py"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS
from lidar import learned as L
from lidar import learned_eval as LE
from lidar.data import TEST, VAL, drives_of

RES = RESULTS / "WP3" / "S7"


def main():
    t0 = time.time()
    tr, va = drives_of("train"), drives_of("val")
    Ftr, _ = LE.load_l3("clean", tr)
    Fva, Sva = LE.load_l3("clean", va)
    Fat, Sat = LE.load_l3("att_val", va)
    out = {"candidates": {}}
    best = None
    for feats_name, feats in (("base", L.BASE_FEATS), ("base+track", L.BASE_FEATS + L.TRK_FEATS)):
        for kind in L.MODELS:
            t1 = time.time()
            m = L.NormalModel(kind).fit(Ftr[feats].to_numpy())
            cv = L.scan_frame(m, Fva[feats].to_numpy(np.float32), Fva["scan"].to_numpy(), Sva)
            lay = L.make_layer(cv)
            ca = L.scan_frame(m, Fat[feats].to_numpy(np.float32), Fat["scan"].to_numpy(), Sat)
            al = lay.calibrator.transform(lay.raw_scores(ca)) >= lay.threshold
            det = LE.det_by(al, ca.attack.to_numpy())
            fa = float((lay.calibrator.transform(lay.raw_scores(cv)) >= lay.threshold).mean())
            score = float(np.mean([det[a] for a in LE.PHYS]))
            r = {"val_fa": fa, "detection": {a: float(det[a]) for a in LE.PHYS + LE.CMP}, "mean_phys": score, "seconds": time.time() - t1}
            out["candidates"][f"{feats_name}/{kind}"] = r
            print(feats_name, kind, f"FA {fa:.3f} mean {score:.3f}", {a: round(float(det[a]), 3) for a in LE.PHYS}, f"{time.time() - t1:.0f}s", flush=True)
            if best is None or score > best[0]:
                best = (score, feats_name, kind)
    out["choice"] = {"features": best[1], "model": best[2], "mean_phys_val": best[0]}
    print("CHOICE", out["choice"])
    (RES / "dev_l3.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
