"""WP1 S8 shared helpers: raw-score frame, nested LODO fold states (CUSUM selection + calibration inside the fold), nested combiner loops,
compact summaries, bootstrap. Used by tools/WP1_S8_dev.py (train+val drives only), tools/WP1_S8_test.py (one test pass),
tools/WP1_S8_tables.py. Scores come from tools/WP1_S8_scores.py (results/WP1/cache/s8_raw.pkl).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from common.metrics import auc
from gps import stack as ST

import WP1_S4_lib as L

BUDGET = 0.01
RAW = L.OUT / "cache" / "s8_raw.pkl"
DEV_PARTS = ("train", "val")


def load_raw():
    return pd.read_pickle(RAW)


def candidates(raw):
    return ([c for c in raw.columns if c.startswith("cusum_ekf_")], [c for c in raw.columns if c.startswith("cusum_dr_")])


def select_cusum(frame, ri, cal_drives, cand_ekf, cand_dr):
    """S4 selection (criterion J at the pooled 1% threshold of `cal_drives`), restricted to the calibration drives. Returns names + J."""
    normal = (frame["label"] == 0).to_numpy() & np.isin(frame["drive"].to_numpy(), cal_drives)
    out = {}
    for key, cands in (("ekf", cand_ekf), ("dr", cand_dr)):
        js = {}
        for c in cands:
            r = frame[c].to_numpy(float)
            js[c] = ri.j(r >= ST.raw_threshold(r, normal, BUDGET), cal_drives)
        best = max(js, key=js.get)               # first maximum in column order (as S4)
        out[key], out["J_" + key] = best, js[best]
    return out


class FoldState:
    """Everything fitted from the calibration drives `cal_drives` only, evaluated on ALL rows of `frame`:
    CUSUM configuration (selected or given), per-layer ECDF calibrators, raw 1% thresholds, calibrated score matrix."""

    def __init__(self, frame, ri, cal_drives, names, cand, sel=None, optional=()):
        self.cal_drives = list(cal_drives)
        self.names = list(names)
        self.sel = sel or select_cusum(frame, ri, self.cal_drives, *cand)
        normal = (frame["label"] == 0).to_numpy() & np.isin(frame["drive"].to_numpy(), self.cal_drives)
        self.normal_cal = normal
        self.raw, self.thr, self.colmap = {}, {}, {}
        for n in list(names) + list(optional):
            col = {"gps.cusum_ekf": self.sel["ekf"], "gps.cusum_dr": self.sel["dr"]}.get(n, n)
            self.colmap[n] = col
            self.raw[n] = frame[col].to_numpy(float)
            self.thr[n] = ST.raw_threshold(self.raw[n], normal, BUDGET)
        self.cal, self.cals = ST.calibrate_columns(self.raw, normal)

    def flags(self, name):
        return self.raw[name] >= self.thr[name]

    def apply(self, frame):
        """Raw scores, calibrated scores and flags of ANOTHER frame (e.g. test rows) with what was fitted here."""
        raw = {n: frame[c].to_numpy(float) for n, c in self.colmap.items()}
        cal = {n: self.cals[n].transform(r) for n, r in raw.items()}
        flags = {n: raw[n] >= self.thr[n] for n in raw}
        return raw, cal, flags

    def matrix(self, names):
        return ST.stack_matrix(self.cal, names)


def nested_layer_flags(frame, folds, name):
    drive = frame["drive"].to_numpy()
    flag = np.zeros(len(frame), bool)
    for d, F in folds.items():
        m = drive == d
        flag[m] = F.flags(name)[m]
    return flag


def nested_raw(frame, folds, name):
    drive = frame["drive"].to_numpy()
    out = np.zeros(len(frame))
    for d, F in folds.items():
        m = drive == d
        out[m] = F.raw[name][m]
    return out


def nested_combine(frame, folds, names, method, fit_exclude=None):
    """Held-out combined scores and flags. Fold d: combiner method / weights / 1% threshold fitted on the other drives' calibrated scores
    (group halves by drive). fit_exclude (bool mask over rows): rows left out of the combiner fit (unseen-attack control)."""
    drive = frame["drive"].to_numpy()
    y = frame["label"].to_numpy()
    names = sorted(names)
    score = np.zeros(len(frame))
    flag = np.zeros(len(frame), bool)
    info = {}
    for d, F in folds.items():
        m = drive == d
        X = F.matrix(names)
        fm = ~m if fit_exclude is None else (~m & ~fit_exclude)
        c = ST.MatrixCombiner(method=method).fit_matrix(names, X[fm], y[fm], drive[fm])
        s = c.score_matrix(X[m])
        score[m] = s
        flag[m] = s >= c.threshold
        info[d] = {"method": c.method, "threshold": float(c.threshold), "selection": c.selection}
    return score, flag, info


def compact(frame, ri, flag, score=None, drives=None):
    """Run-level / row-level detection per attack, FA (clean runs, all normal rows), per-drive FA spread, mean run-level, AUC."""
    y = ri.y
    f = np.asarray(flag, bool)
    sel = np.ones(len(f), bool) if drives is None else np.isin(ri.row_drive, list(drives))
    run = ri.run_level(f, drives)
    row = {a: float(f[sel & (ri.row_attack == a) & y].mean()) for a in ST.ATTACKS}
    pd_fa = {str(d): float(f[sel & ri.normal & (ri.row_drive == d)].mean())
             for d in sorted(set(ri.row_drive[sel])) if (sel & ri.normal & (ri.row_drive == d)).any()}
    out = {"fa_clean_runs": ri.clean_fa(f, drives), "fa_all_normal_rows": float(f[sel & ri.normal].mean()),
           "run_detected": run, "row_detection": row, "mean_run_detected": float(np.mean(list(run.values()))),
           "mean_row_detection": float(np.mean(list(row.values()))),
           "per_drive_fa": pd_fa, "worst_drive_fa": max(pd_fa.values()), "n_drives_fa_gt_3pct": int(sum(v > 0.03 for v in pd_fa.values())),
           "n_drives": len(pd_fa)}
    if score is not None:
        out["auc_row_level"] = auc(y[sel].astype(int), np.minimum(np.asarray(score, float)[sel], 1e300))
    return out


# ---------------------------------------------------------------------------------------------------------------------------
# bootstrap (test)
# ---------------------------------------------------------------------------------------------------------------------------
def bootstrap_ci(ri, flag, score, n_boot=2000, seed=42, auc_boot=400):
    """95% percentile intervals for: clean-run FA, per-attack run-level detection, mean run-level detection, AUC.
    'drives' = cluster bootstrap over the test drives (all their runs and rows together); 'runs' = bootstrap over runs within each attack
    (clean-run FA: over clean runs)."""
    rng = np.random.default_rng(seed)
    f = np.asarray(flag, bool)
    det = ri.detected(f)
    drives = sorted(set(ri.row_drive))
    # per-run quantities
    run_att = ri.run_attack
    run_dr = ri.run_drive
    clean_runs = np.flatnonzero(run_att == "none")
    ends = np.r_[ri.start[1:], ri.n]
    clean_flag = np.add.reduceat((f & ri.clean_row).astype(np.int64), ri.start)      # flagged rows per run (clean rows only)
    clean_len = np.add.reduceat(ri.clean_row.astype(np.int64), ri.start)
    out = {"point": {}, "drives": {}, "runs": {}, "n_boot": n_boot, "seed": seed, "n_test_drives": len(drives)}

    def stats_from(det_a, fl, ln):
        return fl.sum() / max(ln.sum(), 1), [det_a[a].mean() if len(det_a[a]) else np.nan for a in ST.ATTACKS]

    out["point"]["fa_clean_runs"] = float(clean_flag.sum() / clean_len.sum())
    for a in ST.ATTACKS:
        out["point"][a] = float(det[run_att == a].mean())
    out["point"]["mean_run"] = float(np.mean([out["point"][a] for a in ST.ATTACKS]))
    out["point"]["auc"] = auc(ri.y.astype(int), np.minimum(score, 1e300))
    # ---- drive cluster ----
    dd = {d: {"det": {a: det[(run_dr == d) & (run_att == a)] for a in ST.ATTACKS}, "fl": clean_flag[(run_dr == d) & (run_att == "none")].sum(),
              "ln": clean_len[(run_dr == d) & (run_att == "none")].sum()} for d in drives}
    res = {"fa_clean_runs": [], "mean_run": [], **{a: [] for a in ST.ATTACKS}}
    for _ in range(n_boot):
        pick = rng.choice(len(drives), len(drives))
        fl = sum(dd[drives[i]]["fl"] for i in pick)
        ln = sum(dd[drives[i]]["ln"] for i in pick)
        res["fa_clean_runs"].append(fl / max(ln, 1))
        per = []
        for a in ST.ATTACKS:
            v = np.concatenate([dd[drives[i]]["det"][a] for i in pick])
            res[a].append(v.mean() if len(v) else np.nan)
            per.append(res[a][-1])
        res["mean_run"].append(np.nanmean(per))
    out["drives"] = {k: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))] for k, v in res.items()}
    # AUC: cluster bootstrap over drives (fewer resamples: roc_auc on all rows)
    idx = {d: np.flatnonzero(ri.row_drive == d) for d in drives}
    aucs = []
    for _ in range(auc_boot):
        pick = rng.choice(len(drives), len(drives))
        ii = np.concatenate([idx[drives[i]] for i in pick])
        yy = ri.y[ii].astype(int)
        if 0 < yy.sum() < len(yy):
            aucs.append(auc(yy, np.minimum(np.asarray(score, float)[ii], 1e300)))
    out["drives"]["auc"] = [float(np.percentile(aucs, 2.5)), float(np.percentile(aucs, 97.5))]
    # ---- runs ----
    res = {"fa_clean_runs": [], "mean_run": [], **{a: [] for a in ST.ATTACKS}}
    per_att = {a: det[run_att == a] for a in ST.ATTACKS}
    cf, cl = clean_flag[clean_runs], clean_len[clean_runs]
    for _ in range(n_boot):
        i = rng.integers(0, len(clean_runs), len(clean_runs))
        res["fa_clean_runs"].append(cf[i].sum() / max(cl[i].sum(), 1))
        per = []
        for a in ST.ATTACKS:
            v = per_att[a][rng.integers(0, len(per_att[a]), len(per_att[a]))]
            res[a].append(v.mean())
            per.append(v.mean())
        res["mean_run"].append(np.mean(per))
    out["runs"] = {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in res.items()}
    out["runs"]["auc"] = None
    return out


def bootstrap_diff(ri, flag_a, flag_b, n_boot=2000, seed=42):
    """Paired cluster bootstrap over test drives of (mean run-level detection of A) - (of B) and of the clean-run FA difference."""
    rng = np.random.default_rng(seed)
    da, db = ri.detected(np.asarray(flag_a, bool)), ri.detected(np.asarray(flag_b, bool))
    drives = sorted(set(ri.row_drive))
    ends = np.r_[ri.start[1:], ri.n]

    def fa_parts(f):
        cf = np.add.reduceat((np.asarray(f, bool) & ri.clean_row).astype(np.int64), ri.start)
        return cf
    ca, cb = fa_parts(flag_a), fa_parts(flag_b)
    cl = np.add.reduceat(ri.clean_row.astype(np.int64), ri.start)
    out_mean, out_fa = [], []
    for _ in range(n_boot):
        pick = rng.choice(len(drives), len(drives))
        m = np.concatenate([np.flatnonzero(ri.run_drive == drives[i]) for i in pick])
        per_a, per_b = [], []
        for a in ST.ATTACKS:
            mm = m[ri.run_attack[m] == a]
            per_a.append(da[mm].mean()); per_b.append(db[mm].mean())
        out_mean.append(np.mean(per_a) - np.mean(per_b))
        out_fa.append((ca[m].sum() - cb[m].sum()) / max(cl[m].sum(), 1))
    return {"mean_run_diff_ci": [float(np.percentile(out_mean, 2.5)), float(np.percentile(out_mean, 97.5))],
            "fa_diff_ci": [float(np.percentile(out_fa, 2.5)), float(np.percentile(out_fa, 97.5))],
            "mean_run_diff": float(np.mean([da[ri.run_attack == a].mean() for a in ST.ATTACKS]) - np.mean([db[ri.run_attack == a].mean() for a in ST.ATTACKS]))}
