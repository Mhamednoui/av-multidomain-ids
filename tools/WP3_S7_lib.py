"""WP3 S7 shared helpers for the L4 scripts: row loading, validation detection at the 1 % point, variant training sets."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lidar import learned_l4 as L4
from lidar.data import drives_of
from lidar.learned_eval import PHYS, CMP, threshold


def load_rows(kind, drives):
    zs = [pd.read_pickle(L4.ROOT / f"l4_{kind}_{d}.pkl") for d in drives]
    return pd.concat([z["meta"] for z in zs], ignore_index=True), np.vstack([z["X"] for z in zs])


def train_set(drives, types=None):
    """Normal rows (class 0) + physical attack rows of the drives. types: restrict the attack types (default all six)."""
    nm, nx = L4.normal_rows(drives)
    m, x = load_rows("tr", drives)
    if types is not None:
        k = m.type.isin(types).to_numpy()
        m, x = m[k], x[k]
    return np.vstack([nx, x]), np.r_[np.zeros(len(nx), int), m.cls.to_numpy()], m


def detection_at_budget(model, normal_X, ev_meta, ev_X, budget=0.01, score=None):
    """(threshold, FA on the given normal rows, {attack: detection}) with the threshold = tie-safe `budget` of the normal rows' scores."""
    score = score or L4.attack_score
    sn = score(model, normal_X)
    thr = threshold(sn, budget)
    se = score(model, ev_X)
    det = pd.Series(se >= thr).groupby(ev_meta.attack.to_numpy()).mean()
    return thr, float((sn >= thr).mean()), {a: float(det[a]) for a in PHYS + CMP if a in det.index}


def mean_phys(det):
    return float(np.mean([det[a] for a in PHYS]))
