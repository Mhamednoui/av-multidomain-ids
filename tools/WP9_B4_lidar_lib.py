"""WP9 B4 LiDAR library: load the descriptor rows built by tools/WP9_B4_lidar_build.py, class map, metrics at fixed FPR, drive-cluster bootstrap.
Rules: notes/WP9_B4.md (pre-registration 2026-11-05). Classes: 0 Normal, 1 PointDrop, 2 IntensitySpoof, 3 Phantom (ph_* + cmp_*).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from common.config import DATA_EXTRA
from common.metrics import budget_threshold

CACHE = DATA_EXTRA / "cache_v3" / "WP9" / "B4" / "lidar"
LOCK = json.loads((ROOT / "locks" / "WP9_kitti.json").read_text())
KINDS = ["ph_replace_near", "ph_replace_far", "ph_budget_near", "ph_budget_far", "PointDrop", "IntensitySpoof", "cmp_boxcloud", "cmp_mradd_near", "cmp_mradd_far"]
NAIVE = ["cmp_boxcloud", "cmp_mradd_near", "cmp_mradd_far"]
PHYSICAL = [k for k in KINDS if k not in NAIVE]
CLASS_OF = {"clean": 0, "PointDrop": 1, "IntensitySpoof": 2}
CLASSES = ["Normal", "PointDrop", "IntensitySpoof", "Phantom"]
N_DESCR = 211


def cls_of(name):
    return CLASS_OF.get(name, 3)


def load(part, with_attack=True, with_clean=True):
    """(meta, X) of a part: clean rows + attack rows of its drives; meta has drive, base, i, attack, n_inj, cls."""
    ms, xs = [], []
    for d in LOCK["parts"][part]["drives"]:
        for kind, on in (("clean", with_clean), ("attack", with_attack)):
            if not on:
                continue
            z = pd.read_pickle(CACHE / f"{kind}_{d}.pkl")
            ms.append(z["meta"])
            xs.append(z["X"])
    meta = pd.concat(ms, ignore_index=True)
    meta["cls"] = [cls_of(a) for a in meta.attack]
    return meta, np.vstack(xs)


def thr_at(s_clean, fpr):
    return budget_threshold(s_clean, fpr)


def tpr_by_kind(meta, s, thr):
    out = {}
    for k in KINDS:
        m = (meta.attack == k).to_numpy()
        out[k] = float((s[m] >= thr).mean()) if m.any() else float("nan")
    return out


def val_objective(meta, s, fpr=0.10):
    clean = (meta.attack == "clean").to_numpy()
    thr = thr_at(s[clean], fpr)
    t = tpr_by_kind(meta, s, thr)
    return float(np.mean(list(t.values()))), t, thr


def auc_any(meta, s):
    y = (meta.attack != "clean").to_numpy().astype(int)
    return float(roc_auc_score(y, s))


def drive_boot(num_den_by_drive, n=2000, seed=42):
    """num_den_by_drive: {drive: (k, n)} -> pooled-rate percentile 95% CI by resampling drives."""
    ds = sorted(num_den_by_drive)
    k = np.array([num_den_by_drive[d][0] for d in ds], float)
    m = np.array([num_den_by_drive[d][1] for d in ds], float)
    rng = np.random.default_rng(seed)
    v = np.empty(n)
    for i in range(n):
        s = rng.integers(0, len(ds), len(ds))
        v[i] = k[s].sum() / max(m[s].sum(), 1.0)
    return [float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))]
