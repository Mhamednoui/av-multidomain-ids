"""WP3 S7 object-level view of L3: AUC of phantom objects (clusters with >= 50 % injected returns) against clean objects of the same
minimum size (n >= 50 points), and the share of phantom objects above the clean 99th-percentile object score. Model: the validation
choice of dev_l3.json (dev: fitted on the train drives, validation sets; final: the final model, test sets, part of the one verdict run).
Usage: python -u -W ignore tools/WP3_S7_objects.py dev|final"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS
from lidar import learned as L
from lidar import learned_eval as LE
from lidar.data import CACHE, TEST, drives_of

RES = RESULTS / "WP3" / "S7"


def main(mode):
    ch = json.loads((RES / "dev_l3.json").read_text())["choice"]
    feats = L.BASE_FEATS + (L.TRK_FEATS if ch["features"] == "base+track" else [])
    if mode == "dev":
        va = drives_of("val")
        Ftr, _ = LE.load_l3("clean", drives_of("train"))
        m = L.NormalModel(ch["model"]).fit(Ftr[feats].to_numpy())
        Fc, _ = LE.load_l3("clean", va)
        Fa, Sa = LE.load_l3("att_val", va)
    else:
        with open(CACHE / "S7" / "models" / "l3_final.pkl", "rb") as fh:
            m = pickle.load(fh)["model"]
        Fc, _ = LE.load_l3("clean", TEST)
        Fa, Sa = LE.load_l3("att_test", TEST)
    att = Sa.set_index("scan").attack.loc[Fa.scan.astype(str).to_numpy()].to_numpy()
    sc_c = m.score(Fc[feats].to_numpy(np.float32))
    sc_a = m.score(Fa[feats].to_numpy(np.float32))
    big = Fc.n_points.to_numpy() >= 50
    q99 = float(np.quantile(sc_c, 0.99))
    out = {"mode": mode, "model": ch, "n_clean_objects": int(len(sc_c)), "q99_clean_object_score": q99, "attacks": {}}
    for a in LE.PHYS[:4] + LE.CMP:
        g = (att == a) & (Fa.ph_n.to_numpy() >= 0.5 * Fa.n_points.to_numpy())
        if g.sum() < 5:
            continue
        auc = roc_auc_score(np.r_[np.zeros(big.sum()), np.ones(g.sum())], np.r_[sc_c[big], sc_a[g]])
        out["attacks"][a] = {"n_phantom_objects": int(g.sum()), "auc_vs_clean_objects_n50": float(auc), "share_above_clean_q99": float((sc_a[g] > q99).mean()),
                             "median_points": float(np.median(Fa.n_points.to_numpy()[g]))}
    (RES / f"objects_{mode}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out["attacks"], indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
