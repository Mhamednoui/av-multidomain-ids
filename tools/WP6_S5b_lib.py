"""WP6 S5b shared code (M2 addendum): the S5 machinery (tools/WP6_S5_lib.py: folds, fold composites, LOGO, correlator evaluation, bootstrap) with
(1) the frozen LiDAR pack (s5b_lidar, tools/WP6_S5b_lidar.py) and the LiDAR entry variants "combined" / "layers" (entries lidar.L1 ... lidar.L2d = one domain),
(2) the label-free budget allocations noisy_or / max / wsplit (weights from out-of-fold clean-tick exceedance only),
(3) blame / corroboration / response on DOMAINS (fusion.system.entry_domain), correlator with blame_rule and safe_stop_min_domains (fusion/correlator.py).
Plan and acceptance rule: notes/WP6_crossdomain.md "S5b start" (written before any S5b result)."""
import pickle
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import combiner as cb  # noqa: E402
from common.metrics import budget_threshold  # noqa: E402
from fusion import composite as CP  # noqa: E402
from fusion.correlator import tick_blame  # noqa: E402
from fusion.system import BUDGET_SYSTEM, DensityTransform, SystemFusion, alarm_events, entry_domain, entry_part, wsplit_score  # noqa: E402
import WP6_S3_lib as L3  # noqa: E402
import WP6_S4_lib as L4  # noqa: E402
import WP6_S5_lib as L5  # noqa: E402

CACHE = L5.CACHE
FILES = dict(L5.FILES, lidar="s5b_lidar")
N_FOLDS = L5.N_FOLDS
ALPHAS = {"v2x": 1.0, "network": 0.0}                 # S5 choice, fixed a priori
LIDAR_LAYERS = ("L1", "L2a", "L2c", "L2d")
COMPARISON = set(CP.V2_COMPARISON) | {"cmp_boxcloud", "cmp_mradd_near", "cmp_mradd_far"}
METHODS = ("noisy_or", "max", "wsplit")              # simplest first (tie order of the validation rule)
VARIANTS = ("combined", "layers")
LIDAR_CALS = ("val", "trainval")                     # trainval = S5b round 2 (post-hoc, labelled)
RHO_CLIP = (0.5, 4.0)
make_folds, groups_of, clean_mask, cluster_ci, summary, family_table = L5.make_folds, L5.groups_of, L5.clean_mask, L5.cluster_ci, L5.summary, L5.family_table
CORR_GRID, corr_simplicity, assemble = L5.CORR_GRID, L5.corr_simplicity, L4.assemble


def load_unique(part):
    return {k: pickle.load(open(CACHE / f"{f}.pkl", "rb"))[part] for k, f in FILES.items()}


def entries(fam, variant="combined"):
    if fam == "C":
        return list(CP.C_DOMAINS)
    lid = ["lidar"] if variant == "combined" else [f"lidar.{x}" for x in LIDAR_LAYERS]
    return ["gps"] + lid + ["can", "network", "v2x", "cross"]


def domains_of(ents):
    return list(dict.fromkeys(entry_domain(e) for e in ents))


def is_episode(f):
    return f.startswith("ep_") or f.startswith("epW_")


def single_families(tab, fam):
    coord = set(CP.COORDINATED[fam])
    return [f for f in tab if f not in coord and f not in COMPARISON and not is_episode(f)]


def selection_families(tab, fam):
    return [f for f in single_families(tab, fam) if tab[f]["category"] != "heldout"]


def episode_families(tab):
    return [f for f in tab if is_episode(f)]


# ---------------------------------------------------------------- calibration
def entry_series_scores(p, entry, s):
    if "." in entry:
        return s["layers"][:, LIDAR_LAYERS.index(entry.split(".")[1])]
    return s["score"]


def fit_cal(u, folds, F, fam, ents, lidar_cal="val"):
    """Density transforms + per-entry ECDFs on the clean ticks of the groups of folds F (folds None = all groups). lidar_cal "trainval" (S5b round 2): the
    LiDAR entries also use the clean calibration-only series of the 13 train drives (pack key calib_series)."""
    dens, raw = {}, {}
    for e in ents:
        d = entry_domain(e)
        k = L5.ukey(fam, d)
        p = u[k]
        gs = None if folds is None else {g for g, f in folds[k].items() if f in F}
        ser = [s for s in p["series"] if s["kind"] == "clean" and (gs is None or s["group"] in gs)]
        if d == "lidar" and lidar_cal == "trainval":
            ser = ser + list(p["calib_series"])
        t = DensityTransform(ALPHAS.get(e, 0.0))
        if t.alpha > 0:
            t.fit(np.concatenate([v for g, v in p["clean_samples"].items() if gs is None or g in gs]))
        dens[e] = t
        raw[e] = np.concatenate([t.transform(entry_series_scores(p, e, s), s.get("count", np.ones(len(s["score"])))) for s in ser])
    fus = SystemFusion(ents, "noisy_or")
    fus.fit_calibration(raw)
    return dens, fus


def matrix(dens, fus, comps):
    raw = {}
    for e in fus.domains:
        v = [entry_part(c["parts"], e) for c in comps]
        raw[e] = np.concatenate([dens[e].transform(x["score"], x["count"]) for x in v])
    return fus.matrix(raw)


def combine(method, X, cols=None, w=None):
    Xc = X if cols is None else X[:, cols]
    if method == "wsplit":
        return wsplit_score(Xc, w if cols is None or w is None or len(w) == Xc.shape[1] else np.asarray(w)[cols])
    return cb._combine(method, Xc)


class FoldScores:
    """X[(g, F)] = fold g composites scored with calibrations fitted on folds F, for one family and one entry list."""

    def __init__(self, u, folds, comps, fam, ents, lidar_cal="val"):
        self.comps, self.X, self.cal, self.ents, self.lidar_cal = comps, {}, {}, list(ents), lidar_cal
        sets = [frozenset({h}) for h in range(N_FOLDS)] + [frozenset(set(range(N_FOLDS)) - {g}) for g in range(N_FOLDS)] + [frozenset(range(N_FOLDS))]
        for F in sets:
            self.cal[F] = fit_cal(u, folds, F, fam, self.ents, lidar_cal)
        for g in range(N_FOLDS):
            for F in sets:
                if g not in F:
                    self.X[(g, F)] = matrix(*self.cal[F], comps[g])
        self.clean = {g: clean_mask(comps[g]) for g in range(N_FOLDS)}


def wsplit_weights(fs, train, cols=None):
    """Label-free budget shares: w_d = 1 / clip(rho_d), rho_d = out-of-fold clean-tick exceedance of entry d at its calibrated 0.99 level / 0.01, pooled over the
    clean composite ticks of the folds `train` (each scored with calibrations fitted on the other training folds). No attack label."""
    tr = tuple(train)
    Xs = []
    for g in tr:
        F = frozenset(set(tr) - {g}) if len(tr) > 1 else None
        if F is None or F not in fs.cal:
            continue
        X = fs.X[(g, F)][fs.clean[g]]
        Xs.append(X if cols is None else X[:, cols])
    X = np.vstack(Xs)
    rho = (X >= 0.99).mean(axis=0) / 0.01
    return 1.0 / np.clip(rho, *RHO_CLIP), rho


def procedure_threshold(fs, method, train, cols=None):
    """LOGO on the folds `train`: threshold = tie-safe 2% of the pooled out-of-fold clean composite scores -> (threshold, calibration fold set, weights)."""
    w = wsplit_weights(fs, train, cols)[0] if method == "wsplit" else None
    s = np.concatenate([combine(method, fs.X[(g, frozenset(set(train) - {g}))], cols, w)[fs.clean[g]] for g in train])
    return budget_threshold(s, BUDGET_SYSTEM), frozenset(train), w


def heldout_scores(fs, method, cols=None):
    out = {}
    for f in range(N_FOLDS):
        train = tuple(g for g in range(N_FOLDS) if g != f)
        T, F, w = procedure_threshold(fs, method, train, cols)
        out[f] = (combine(method, fs.X[(f, F)], cols, w), T)
    return out


# ---------------------------------------------------------------- evaluation (domains, not entries)
def true_sensor(fam, attacked):
    return L5.true_sensor(fam, attacked)


def comp_arrays(c, X, ents):
    """-> own per DOMAIN (n, D), domain names, tick blame (n,)."""
    names = [entry_domain(e) for e in ents]
    own_e = np.column_stack([np.asarray(entry_part(c["parts"], e)["dom_alarm"], bool) for e in ents])
    doms = domains_of(ents)
    own = np.column_stack([own_e[:, [i for i, n in enumerate(names) if n == d]].any(axis=1) for d in doms])
    cr = c["parts"].get("cross")
    bl = tick_blame(names, X, own_e, None if cr is None or "cross" not in names else cr["blame"], None if cr is None or "cross" not in names else cr["dom_alarm"])
    return own, doms, bl


def evaluate(comps, X, s, thr, ents, corr=None, keep_events=False):
    """Per composite outcome (S5 metrics): raw tick alarms; with a correlator: events, event detection, delay, blame, response."""
    idx = L3.index_of(comps)
    al = s >= thr
    outs = []
    for ci, c in enumerate(comps):
        a, Xc = al[idx[ci]:idx[ci + 1]], X[idx[ci]:idx[ci + 1]]
        r = {"family": c["family"], "attacked": c["attacked"], "vehicle": c["vehicle"], "n": c["n"], "alarm_ticks": int(a.sum())}
        if corr is None:
            ev, conf = None, a
            r["events"] = alarm_events(a)
        else:
            own, doms, bl = comp_arrays(c, Xc, ents)
            ev = corr.events(a, own, doms, bl)
            conf = np.zeros(c["n"], bool)
            for e in ev:
                t = np.flatnonzero(a[e.start:e.end + 1]) + e.start
                conf[t] = True
            r["events"] = len(ev)
            r["levels"] = [e.response for e in ev]
            r["log_ticks"] = int(a.sum() - conf.sum())
            if keep_events:
                r["event_list"] = ev
        if c["family"] != "none":
            hit = np.flatnonzero(a & c["label"])
            r["tick_detected"] = bool(len(hit))
            r["tick_delay"] = float(hit[0] - c["onset"]) if len(hit) else None
            eh = np.flatnonzero(conf & c["label"])
            r["detected"] = bool(len(eh))
            if len(eh):
                t0 = int(eh[0])
                r["delay"] = float(t0 - c["onset"])
                if ev is not None:
                    e = next(e for e in ev if e.start <= t0 <= e.end)
                    ts = true_sensor(c["family"], c["attacked"])
                    r["blamed"] = e.blamed
                    r["blame"] = "undecided" if e.blamed == "undecided" else ("correct" if e.blamed in ts else "wrong")
                    r["response_first"] = e.response
                    r["response_max"] = max((x.response for x in ev if x.end >= c["onset"]), key=["LOG", "WARN", "DEGRADE", "SAFE_STOP"].index)
        outs.append(r)
    return outs


def blame_pool(outs, fams):
    det = [r for r in outs if r["family"] in fams and r["detected"]]
    if not det:
        return {"correct": None, "wrong": None, "undecided": None, "n_detected": 0}
    return {k: float(np.mean([r["blame"] == k for r in det])) for k in ("correct", "wrong", "undecided")} | {"n_detected": len(det)}


def per_domain(tab, fams, key):
    out = {}
    for f in fams:
        out.setdefault(tab[f]["attacked"], []).append(tab[f][key])
    return {d: float(np.mean(v)) for d, v in out.items()}
