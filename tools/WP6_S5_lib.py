"""WP6 S5 shared code for tools/WP6_S5_dev.py (validation) and tools/WP6_S5_test.py (the one M2 test run): M2 packs, 3 group folds over validation, fold
composites, per-fold calibrations with the density transform, calibration procedures (halves / LOGO) with nested held-out estimates, correlator evaluation
(events, event detection, delay, blame, response), cluster bootstrap. Plan and acceptance rule: notes/WP6_crossdomain.md "S5 start" (written before any result).
"""
import pickle
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import combiner as cb  # noqa: E402
from common.config import SEED  # noqa: E402
from common.metrics import budget_threshold  # noqa: E402
from fusion import composite as CP  # noqa: E402
from fusion.correlator import TemporalCorrelator, tick_blame  # noqa: E402
from fusion.system import BUDGET_SYSTEM, DensityTransform, SystemFusion, alarm_events  # noqa: E402
import WP6_S3_lib as L3  # noqa: E402
import WP6_S4_lib as L4  # noqa: E402

CACHE = L3.CACHE
FILES = {"gps": "s3_gps", "lidar": "s5_lidar", "can": "s3_can", "network": "s5_network", "v2x": "s5_v2x", "cross_kitti": "s3_cross_kitti", "cross_comma": "s5_cross_comma"}
DOMS = {"K": CP.K_DOMAINS, "C": CP.C_DOMAINS}
DENSITY = ("v2x", "network")
N_FOLDS = 3
category = L4.category


def load_unique(part):
    return {k: pickle.load(open(CACHE / f"{f}.pkl", "rb"))[part] for k, f in FILES.items()}


assemble = L4.assemble


def ukey(fam, d):
    return ("cross_kitti" if fam == "K" else "cross_comma") if d == "cross" else d


# ---------------------------------------------------------------- folds and composites
def make_folds(u, seed=SEED):
    """unique pack key -> {group: fold}. KITTI drives (gps / cross_kitti / lidar share them): one val drive per fold. Others: seeded round-robin, clean groups and
    attack-only groups dealt separately so every fold has clean material."""
    rng = np.random.default_rng([seed, 5, 5])
    out = {}
    kd = sorted({s["group"] for k in ("gps", "cross_kitti", "lidar") for s in u[k]["series"]})
    kf = {kd[i]: j % N_FOLDS for j, i in enumerate(rng.permutation(len(kd)))}
    for k in ("gps", "cross_kitti", "lidar"):
        out[k] = kf
    for k in ("can", "network", "v2x", "cross_comma"):
        clean = sorted({s["group"] for s in u[k]["series"] if s["kind"] == "clean"})
        other = sorted({s["group"] for s in u[k]["series"]} - set(clean))
        f = {}
        for lst in (clean, other):
            off = int(rng.integers(N_FOLDS))
            for j, i in enumerate(rng.permutation(len(lst))):
                f[lst[i]] = (j + off) % N_FOLDS
        out[k] = f
    return out


def groups_of(folds, F, fam):
    return {d: {g for g, f in folds[ukey(fam, d)].items() if f in F} for d in DOMS[fam]}


def fold_composites(packs, folds, fam, n_clean, n_att, tag=65):
    return {f: L3.build_set(fam, packs[fam], groups_of(folds, {f}, fam), [SEED, tag, f, ord(fam)], n_clean, n_att) for f in range(N_FOLDS)}


# ---------------------------------------------------------------- calibration
def fit_cal(u, folds, F, fam, alphas, domains=None):
    """Density transforms + per-entry ECDFs on the clean ticks of the groups of folds F (folds None = all groups)."""
    domains = domains or DOMS[fam]
    dens, raw = {}, {}
    for d in domains:
        k = ukey(fam, d)
        p = u[k]
        gs = None if folds is None else {g for g, f in folds[k].items() if f in F}
        ser = [s for s in p["series"] if s["kind"] == "clean" and (gs is None or s["group"] in gs)]
        t = DensityTransform(alphas.get(d, 0.0))
        if t.alpha > 0:
            t.fit(np.concatenate([v for g, v in p["clean_samples"].items() if gs is None or g in gs]))
        dens[d] = t
        raw[d] = np.concatenate([t.transform(s["score"], s.get("count", np.ones(len(s["score"])))) for s in ser])
    fus = SystemFusion(domains, "noisy_or")
    fus.fit_calibration(raw)
    return dens, fus


def matrix(dens, fus, comps):
    raw = {d: np.concatenate([dens[d].transform(c["parts"][d]["score"], c["parts"][d]["count"]) for c in comps]) for d in fus.domains}
    return fus.matrix(raw)


def clean_mask(comps):
    return np.concatenate([np.full(c["n"], c["family"] == "none") for c in comps])


def combine(method, X, cols=None):
    return cb._combine(method, X if cols is None else X[:, cols])


class FoldScores:
    """Calibrated matrices X[(g, F)] = fold g composites scored with calibrations fitted on folds F, for one family and one alpha setting."""

    def __init__(self, u, folds, comps, fam, alphas):
        self.comps, self.X, self.cal = comps, {}, {}
        sets = [frozenset({h}) for h in range(N_FOLDS)] + [frozenset(set(range(N_FOLDS)) - {g}) for g in range(N_FOLDS)] + [frozenset(range(N_FOLDS))]
        for F in sets:
            self.cal[F] = fit_cal(u, folds, F, fam, alphas)
        for g in range(N_FOLDS):
            for F in sets:
                if g not in F:
                    self.X[(g, F)] = matrix(*self.cal[F], comps[g])
        self.clean = {g: clean_mask(comps[g]) for g in range(N_FOLDS)}


def procedure_threshold(fs, method, proc, train, cols=None):
    """Threshold of procedure `proc` run on the folds `train` (sorted tuple) -> (threshold, calibration fold set used to score new data)."""
    if proc == "logo":
        s = np.concatenate([combine(method, fs.X[(g, frozenset(set(train) - {g}))], cols)[fs.clean[g]] for g in train])
        return budget_threshold(s, BUDGET_SYSTEM), frozenset(train)
    a, rest = train[0], train[1:]                                    # halves: ECDF on the first fold, threshold on the others
    if len(rest) == 1:
        s = combine(method, fs.X[(rest[0], frozenset({a}))], cols)[fs.clean[rest[0]]]
        return budget_threshold(s, BUDGET_SYSTEM), frozenset({a})
    F = frozenset(train[:-1])                                        # deployment with 3 folds: ECDF on folds 0-1, threshold on fold 2
    s = combine(method, fs.X[(train[-1], F)], cols)[fs.clean[train[-1]]]
    return budget_threshold(s, BUDGET_SYSTEM), F


def heldout_scores(fs, method, proc, cols=None):
    """Nested held-out: for every fold f, the procedure on the other folds; fold f scored with that procedure's calibration. -> {f: (scores, threshold)}"""
    out = {}
    for f in range(N_FOLDS):
        train = tuple(g for g in range(N_FOLDS) if g != f)
        T, F = procedure_threshold(fs, method, proc, train, cols)
        out[f] = (combine(method, fs.X[(f, F)], cols), T)
    return out


# ---------------------------------------------------------------- evaluation
def true_sensor(fam, attacked):
    if attacked == "gps":
        return {"gps"}
    if attacked == "gps+can":
        return {"gps", "can"}
    if attacked == "cross":
        return {"lidar"} if fam.startswith("lidar_") else {"can"}
    return {attacked}


def comp_arrays(c, X, domains):
    own = np.column_stack([np.asarray(c["parts"][d]["dom_alarm"], bool) for d in domains])
    cr = c["parts"].get("cross")
    bl = tick_blame(domains, X, own, None if cr is None else cr["blame"], None if cr is None else cr["dom_alarm"])
    return own, bl


def evaluate(comps, X, s, thr, domains, corr=None):
    """Per composite outcome at threshold thr (alarm = s >= thr): raw tick alarms (S3 metrics) and, with a correlator, events / event detection / delay / blame /
    response. corr None = S3 alarm events (maximal runs of alarm ticks)."""
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
            own, bl = comp_arrays(c, Xc, domains)
            ev = corr.events(a, own, domains, bl)
            conf = np.zeros(c["n"], bool)
            for e in ev:
                t = np.flatnonzero(a[e.start:e.end + 1]) + e.start
                conf[t] = True
            r["events"] = len(ev)
            r["levels"] = [e.response for e in ev]
            r["log_ticks"] = int(a.sum() - conf.sum())
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


def summary(outs):
    cl = [r for r in outs if r["family"] == "none"]
    ticks = sum(r["n"] for r in cl)
    hours = ticks / 3600.0
    m = {"clean_ticks": ticks, "clean_hours": hours, "fa_tick": sum(r["alarm_ticks"] for r in cl) / max(ticks, 1),
         "events_per_hour": sum(r["events"] for r in cl) / max(hours, 1e-9)}
    if cl and "levels" in cl[0]:
        lv = [x for r in cl for x in r["levels"]]
        m["clean_response_per_hour"] = {k: lv.count(k) / max(hours, 1e-9) for k in ("WARN", "DEGRADE", "SAFE_STOP")}
        m["log_ticks_per_hour"] = sum(r["log_ticks"] for r in cl) / max(hours, 1e-9)
    tab = family_table(outs)
    m["families"] = tab
    m["by_category"] = {c: _mean([x["detection"] for x in tab.values() if x["category"] == c]) for c in L4.CATS}
    m["by_category_tick"] = {c: _mean([x["tick_detection"] for x in tab.values() if x["category"] == c]) for c in L4.CATS}
    return m


def _mean(v):
    return float(np.mean(v)) if len(v) else None


def family_table(outs):
    fams = {}
    for r in outs:
        if r["family"] != "none":
            fams.setdefault(r["family"], []).append(r)
    tab = {}
    for f, rs in fams.items():
        det = [r for r in rs if r["detected"]]
        x = {"attacked": rs[0]["attacked"], "category": category(f, rs[0]["attacked"]), "n": len(rs), "detection": float(np.mean([r["detected"] for r in rs])),
             "tick_detection": float(np.mean([r["tick_detected"] for r in rs])),
             "median_delay_s": float(np.median([r["delay"] for r in det])) if det else None,
             "median_tick_delay_s": float(np.median([r["tick_delay"] for r in rs if r["tick_detected"]])) if any(r["tick_detected"] for r in rs) else None}
        if det and "blame" in det[0]:
            for k in ("correct", "wrong", "undecided"):
                x[f"blame_{k}"] = float(np.mean([r["blame"] == k for r in det]))
            x["blamed_counts"] = {b: sum(r["blamed"] == b for r in det) for b in sorted({r["blamed"] for r in det})}
            x["response_max"] = {k: float(np.mean([r["response_max"] == k for r in det])) for k in ("WARN", "DEGRADE", "SAFE_STOP")}
        tab[f] = x
    return tab


def selection_families(tab):
    """Families allowed in a validation choice: not an S4 held-out type, not the v2-comparison GhostCluster."""
    return [f for f, x in tab.items() if x["category"] != "heldout" and f not in CP.V2_COMPARISON]


def single_families(tab, fam):
    coord = set(CP.COORDINATED[fam])
    return [f for f in tab if f not in coord and f not in CP.V2_COMPARISON]


def cluster_ci(outs, fams, key="detected", seed=SEED, n_boot=1000):
    """95% cluster bootstrap over vehicle groups: clean tick FA, clean events per hour, mean of `key` over the families `fams`."""
    veh = sorted({r["vehicle"] for r in outs})
    vi = {v: i for i, v in enumerate(veh)}
    V, Fn = len(veh), len(fams)
    cn, ca, ce = np.zeros(V), np.zeros(V), np.zeros(V)
    det, cnt = np.zeros((V, Fn)), np.zeros((V, Fn))
    fi = {f: j for j, f in enumerate(fams)}
    for r in outs:
        i = vi[r["vehicle"]]
        if r["family"] == "none":
            cn[i] += r["n"]
            ca[i] += r["alarm_ticks"]
            ce[i] += r["events"]
        elif r["family"] in fi:
            det[i, fi[r["family"]]] += r[key]
            cnt[i, fi[r["family"]]] += 1
    w = np.random.default_rng(seed).multinomial(V, np.full(V, 1.0 / V), size=n_boot).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        fa = (w @ ca) / (w @ cn)
        eh = (w @ ce) / (w @ cn / 3600.0)
        d = (w @ det) / (w @ cnt)
        md = np.nanmean(d, axis=1) if Fn else np.full(n_boot, np.nan)
    q = lambda v: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))]
    return {"fa_tick": q(fa), "events_per_hour": q(eh), "mean": q(md) if Fn else None, "n_vehicle_groups": V}


# ---------------------------------------------------------------- grids
CORR_GRID = [(m, w, g, c) for (m, w) in [(1, 1), (2, 3), (2, 5), (3, 5), (3, 10)] for g in (5, 15) for c in (False, True) if not ((m, w) == (1, 1) and c)]


def corr_simplicity(k):
    m, w, g, c = k
    return (m * w, g, int(c))
