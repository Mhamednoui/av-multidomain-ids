"""WP3 S7: out-of-fold (leave-one-drive-out) clean scores of L3 and of the three L4 variants over the 16 train+val drives, plus the final
models fitted on all 16 drives (cached in ../data_extra/cache_v3/WP3/S7/models). No test data is read here.
Reads the validation choices of dev_l3.json / dev_l4.json. Resumable (one pickle per fold).
Usage: python -u -W ignore tools/WP3_S7_oof.py [l3 l4 l4_nophantom l4_v2]"""
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from WP3_S7_lib import *  # noqa
from common.config import RESULTS
from lidar import learned as L
from lidar import learned_eval as LE
from lidar.data import cache_size_gb

RES = RESULTS / "WP3" / "S7"
MODELS = L4.ROOT / "models"
TYPES_NOPH = ["PointDrop", "IntensitySpoof"]


def oof_l3():
    ch = json.loads((RES / "dev_l3.json").read_text())["choice"]
    feats = L.BASE_FEATS + (L.TRK_FEATS if ch["features"] == "base+track" else [])
    tv = drives_of("train") + drives_of("val")
    F, S = LE.load_l3("clean", tv)
    dr = S.set_index("scan").drive
    drv = dr.loc[F["scan"].astype(str).to_numpy()].to_numpy()
    out = []
    for d in tv:
        f = MODELS / f"oof_l3_{d}.pkl"
        if f.exists():
            out.append(pd.read_pickle(f))
            continue
        t0 = time.time()
        m = L.NormalModel(ch["model"]).fit(F.loc[drv != d, feats].to_numpy())
        sd = S[S.drive == d]
        fr = L.scan_frame(m, F.loc[drv == d, feats].to_numpy(np.float32), F.loc[drv == d, "scan"].astype(str).to_numpy(), sd)
        pd.to_pickle(fr, f)
        out.append(fr)
        print("l3 fold", d, f"{time.time() - t0:.0f}s", flush=True)
    m = L.NormalModel(ch["model"]).fit(F[feats].to_numpy())
    with open(MODELS / "l3_final.pkl", "wb") as fh:
        pickle.dump({"model": m, "feats": feats, "choice": ch}, fh)
    pd.concat(out, ignore_index=True).to_pickle(MODELS / "oof_l3.pkl")


def variant_data(name, tv):
    """(X, y, drive of every row) of the training rows of a variant over the 16 drives."""
    if name == "l4":
        X, y, m = train_set(tv)
        nm, _ = L4.normal_rows(tv)
        drv = np.r_[nm.drive.to_numpy(), m.drive.to_numpy()]
    elif name == "l4_nophantom":
        X, y, m = train_set(tv, TYPES_NOPH)
        nm, _ = L4.normal_rows(tv)
        drv = np.r_[nm.drive.to_numpy(), m.drive.to_numpy()]
    else:
        m, X, y = L4.v2_rows(tv)
        drv = m.drive.to_numpy()
    return X, y, drv


def oof_l4(name):
    ch = json.loads((RES / "dev_l4.json").read_text())["choice"]
    prm, n_trees = ch["params"], ch["n_trees"]
    tv = drives_of("train") + drives_of("val")
    X, y, drv = variant_data(name, tv)
    nm, nx = L4.normal_rows(tv)
    out = []
    for d in tv:
        f = MODELS / f"oof_{name}_{d}.pkl"
        if f.exists():
            out.append(pd.read_pickle(f))
            continue
        t0 = time.time()
        m = L4.fit_xgb(X[drv != d], y[drv != d], prm, n_trees)
        k = (nm.drive == d).to_numpy()
        fr = nm[k].assign(raw=L4.attack_score(m, nx[k]))
        pd.to_pickle(fr, f)
        out.append(fr)
        print(name, "fold", d, f"{time.time() - t0:.0f}s", flush=True)
    m = L4.fit_xgb(X, y, prm, n_trees)
    with open(MODELS / f"{name}_final.pkl", "wb") as fh:
        pickle.dump(m, fh)
    pd.concat(out, ignore_index=True).to_pickle(MODELS / f"oof_{name}.pkl")


if __name__ == "__main__":
    MODELS.mkdir(parents=True, exist_ok=True)
    todo = sys.argv[1:] or ["l3", "l4", "l4_nophantom", "l4_v2"]
    for t in todo:
        t0 = time.time()
        oof_l3() if t == "l3" else oof_l4(t)
        print("done", t, f"{time.time() - t0:.0f}s cache {cache_size_gb():.2f} GB", flush=True)
