"""WP9 B4 LiDAR: the ONE test scoring (7 test drives). Refuses to run unless the selection and control files are committed.
Rows: supervised 4-class XGBoost (chosen on validation), its "phys-only" variant (cmp_* kinds unseen), v3.1 stack (LODO scores of WP8 S3 on the same scans).
Thresholds: tie-safe 10% and 1% quantiles of the VALIDATION clean-scan scores of each detector (3 val drives), applied unchanged to the test drives.
Output: results/WP9/B4_lidar_test.json, scores results/WP9/scores/B4/lidar_test.npz, lidar_v31_scores.pkl.   Run: python -u -W ignore tools/WP9_B4_lidar_test.py
"""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
import xgboost as xgb

import WP9_B4_lidar_lib as L
from WP9_B4_lidar_fit import fit, score
from WP9_B4_lidar_v31 import v31_scores
from common.metrics import budget_threshold

OUT = L.ROOT / "results" / "WP9"
OPS = {"fpr10": 0.10, "fpr1": 0.01}


def committed(path):
    r = subprocess.run(["git", "status", "--porcelain", "--", str(path)], cwd=L.ROOT, capture_output=True, text=True)
    t = subprocess.run(["git", "ls-files", "--error-unmatch", str(path)], cwd=L.ROOT, capture_output=True, text=True)
    return t.returncode == 0 and r.stdout.strip() == ""


def rates(meta, alarm, kinds):
    """pooled rate over `kinds` and per-drive (k, n)."""
    m = meta.attack.isin(kinds).to_numpy()
    byd = {d: (int(alarm[m & (meta.drive == d).to_numpy()].sum()), int((m & (meta.drive == d).to_numpy()).sum())) for d in sorted(set(meta.drive))}
    k = sum(a for a, b in byd.values())
    n = sum(b for a, b in byd.values())
    return k / max(n, 1), byd


def table(meta, s, thr):
    """TPR per kind + pooled NAIVE / PHYSICAL / ALL with drive-bootstrap CI, test FPR with CI."""
    out = {"thr": float(thr), "kinds": {}}
    for k in L.KINDS + ["NAIVE", "PHYSICAL", "ALL_ATTACKS"]:
        kinds = {"NAIVE": L.NAIVE, "PHYSICAL": L.PHYSICAL, "ALL_ATTACKS": L.KINDS}.get(k, [k])
        r, byd = rates(meta, s >= thr, kinds)
        out["kinds"][k] = {"tpr": r, "ci_drive_boot": L.drive_boot(byd)}
    r, byd = rates(meta, s >= thr, ["clean"])
    out["fpr"] = {"fpr": r, "ci_drive_boot": L.drive_boot(byd), "by_drive": {d: v[0] / max(v[1], 1) for d, v in byd.items()}}
    return out


def auc_block(meta, s):
    clean = (meta.attack == "clean").to_numpy()
    from sklearn.metrics import roc_auc_score
    out = {}
    for k in L.KINDS + ["ALL_ATTACKS"]:
        m = (meta.attack.isin(L.KINDS) if k == "ALL_ATTACKS" else (meta.attack == k)).to_numpy()
        out[k] = float(roc_auc_score(np.r_[np.zeros(clean.sum()), np.ones(m.sum())], np.r_[s[clean], s[m]]))
    return out


def macro_f1(meta, s, proba, thr):
    """4-class decision (alarm if s >= thr, class = argmax over attack probabilities) with a prevalence-balanced weighting: every class has total weight 1."""
    y = meta.cls.to_numpy()
    pred = np.where(s >= thr, 1 + np.argmax(proba[:, 1:], axis=1), 0)
    cnt = np.bincount(y, minlength=4).astype(float)
    w = 1.0 / cnt[y]
    out = {}
    f1s = []
    for c in range(4):
        tp = w[(y == c) & (pred == c)].sum()
        fn = w[(y == c) & (pred != c)].sum()
        fp = w[(y != c) & (pred == c)].sum()
        p, r = tp / max(tp + fp, 1e-12), tp / max(tp + fn, 1e-12)
        f = 2 * p * r / max(p + r, 1e-12)
        out[L.CLASSES[c]] = {"precision": float(p), "recall": float(r), "f1": float(f)}
        f1s.append(f)
    out["macro_f1_balanced"] = float(np.mean(f1s))
    out["unweighted_recall"] = {L.CLASSES[c]: float((pred[y == c] == c).mean()) for c in range(4)}
    return out


def main():
    t0 = time.time()
    for f in ("B4_lidar_selection.json", "B4_lidar_controls.json", "B4_lidar_selection_static.json", "B4_lidar_controls_static.json"):
        assert committed(OUT / f), f"{f} must be committed before the test is scored"
    ctl = json.loads((OUT / "B4_lidar_controls_static.json").read_text())
    assert not ctl["red_flag"], "static candidate is red-flagged: not eligible"
    full_ctl = json.loads((OUT / "B4_lidar_controls.json").read_text())
    assert full_ctl["red_flag"], "full model was expected to be flagged (amendment 3); it is never scored here"
    sel = json.loads((OUT / "B4_lidar_selection_static.json").read_text())
    ch = sel["chosen"]
    nc = L.N_DESCR
    model_dir = L.CACHE.parent / "lidar_model"
    mva, Xva = L.load("val")
    mtr, Xtr = L.load("train")
    mte, Xte = L.load("test")
    Xtr, Xva, Xte = Xtr[:, :nc], Xva[:, :nc], Xte[:, :nc]
    assert not set(mte.drive) & (set(mva.drive) | set(mtr.drive))
    print("test rows", len(mte), "clean", int((mte.attack == "clean").sum()), flush=True)
    res = {"n_test_rows": int(len(mte)), "n_test_clean": int((mte.attack == "clean").sum()), "n_test_scans_attacked": int((mte.attack == "PointDrop").sum()), "ops": OPS, "variant": "static (first 211 columns; the full 429-column model is red-flagged and not test-scored)", "detectors": {}}
    sc = {}
    # ---- supervised (chosen) and phys-only
    m = xgb.XGBClassifier()
    m.load_model(str(model_dir / "chosen_static.json"))
    nocmp = ~mtr.attack.str.startswith("cmp_").to_numpy()
    mp = fit(ch["params"], ch["weight_power"], Xtr[nocmp], mtr.cls.to_numpy()[nocmp], Xva, mva.cls.to_numpy(), n_rounds=ch["trees"])
    for name, mod in (("supervised", m), ("supervised_phys_only", mp)):
        pva, pte = mod.predict_proba(Xva), mod.predict_proba(Xte)
        sva, ste = 1 - pva[:, 0], 1 - pte[:, 0]
        cleanv = (mva.attack == "clean").to_numpy()
        det = {"auc": auc_block(mte, ste), "ops": {}}
        for op, fpr in OPS.items():
            thr = budget_threshold(sva[cleanv], fpr)
            t = table(mte, ste, thr)
            t["val_fpr_at_thr"] = float((sva[cleanv] >= thr).mean())
            t["four_class"] = macro_f1(mte, ste, pte, thr)
            det["ops"][op] = t
        res["detectors"][name] = det
        sc[name] = ste
        print(name, {op: round(det["ops"][op]["kinds"]["NAIVE"]["tpr"], 3) for op in OPS}, {op: round(det["ops"][op]["fpr"]["fpr"], 4) for op in OPS}, flush=True)
    np.savez_compressed(OUT / "scores" / "B4" / "lidar_test.npz", drive=mte.drive.to_numpy(), i=mte.i.to_numpy(), attack=mte.attack.to_numpy(), **sc)
    # ---- v3.1 (LODO over the 10 V31_val drives, WP8 S3 config)
    drives = L.LOCK["parts"]["val"]["drives"] + L.LOCK["parts"]["test"]["drives"]
    v31, cfg = v31_scores(drives)
    v31.to_pickle(OUT / "scores" / "B4" / "lidar_v31_scores.pkl")
    vv = v31[v31.drive.isin(L.LOCK["parts"]["val"]["drives"])]
    vt = v31[v31.drive.isin(L.LOCK["parts"]["test"]["drives"])]
    key = lambda d: d.drive + "|" + d.i.astype(str) + "|" + d.attack
    sv = pd.Series(vt.score.values, index=key(vt))
    av = pd.Series(vt.alarm.values, index=key(vt))
    mk = mte.drive + "|" + mte.i.astype(str) + "|" + mte.attack
    missing = (~mk.isin(sv.index)).sum()
    keep = mk.isin(sv.index).to_numpy()
    print("v3.1 rows matched", int(keep.sum()), "of", len(mte), "(missing:", int(missing), ")", flush=True)
    mte_k = mte[keep].reset_index(drop=True)
    s31 = sv.loc[mk[keep]].to_numpy()
    a31 = av.loc[mk[keep]].to_numpy()
    det = {"auc": auc_block(mte_k, s31), "ops": {}, "config": cfg, "n_rows_matched": int(keep.sum())}
    cleanv = (vv.attack == "clean").to_numpy()
    for op, fpr in OPS.items():
        thr = budget_threshold(vv.score.to_numpy()[cleanv], fpr)
        t = table(mte_k, s31, thr)
        t["val_fpr_at_thr"] = float((vv.score.to_numpy()[cleanv] >= thr).mean())
        det["ops"][op] = t
    nat = {"fpr": rates(mte_k, a31, ["clean"])[0]}
    for k in L.KINDS + ["NAIVE", "PHYSICAL", "ALL_ATTACKS"]:
        kinds = {"NAIVE": L.NAIVE, "PHYSICAL": L.PHYSICAL, "ALL_ATTACKS": L.KINDS}.get(k, [k])
        r, byd = rates(mte_k, a31, kinds)
        nat[k] = {"tpr": r, "ci_drive_boot": L.drive_boot(byd)}
    det["native_alarm_1pct"] = nat
    res["detectors"]["v31"] = det
    # ---- paired supervised minus v3.1 (same scans), per kind, same operating points
    ss = pd.Series(sc["supervised"], index=mk.values)
    paired = {}
    sva = 1 - m.predict_proba(Xva)[:, 0]
    for op, fpr in OPS.items():
        thr_s = budget_threshold(sva[(mva.attack == "clean").to_numpy()], fpr)
        thr_v = budget_threshold(vv.score.to_numpy()[cleanv], fpr)
        paired[op] = {}
        for k in L.KINDS + ["NAIVE", "PHYSICAL"]:
            kinds = {"NAIVE": L.NAIVE, "PHYSICAL": L.PHYSICAL}.get(k, [k])
            msk = mte_k.attack.isin(kinds).to_numpy()
            a_s = (ss.loc[mk[keep]].to_numpy() >= thr_s)
            a_v = (s31 >= thr_v)
            byd = {d: (int(a_s[msk & (mte_k.drive == d).to_numpy()].sum()), int(a_v[msk & (mte_k.drive == d).to_numpy()].sum()), int((msk & (mte_k.drive == d).to_numpy()).sum())) for d in sorted(set(mte_k.drive))}
            ds = sorted(byd)
            ks, kv, nn = (np.array([byd[d][j] for d in ds], float) for j in range(3))
            rng = np.random.default_rng(42)
            diffs = []
            for _ in range(2000):
                q = rng.integers(0, len(ds), len(ds))
                diffs.append(ks[q].sum() / max(nn[q].sum(), 1) - kv[q].sum() / max(nn[q].sum(), 1))
            paired[op][k] = {"diff": float(ks.sum() / nn.sum() - kv.sum() / nn.sum()), "ci": [float(np.quantile(diffs, 0.025)), float(np.quantile(diffs, 0.975))]}
    res["paired_supervised_minus_v31"] = paired
    (OUT / "B4_lidar_test.json").write_text(json.dumps(res, indent=1))
    print("done", f"{time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
