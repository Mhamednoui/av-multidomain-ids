"""WP6 S3 shared code for tools/WP6_S3_dev.py (validation) and tools/WP6_S3_test.py (the one test run): load the tick-series packs, group
halves, build composite sets, score a SystemFusion on composites, metrics (FA per tick / per hour, detection, delay, attribution, blame),
cluster bootstrap over vehicle groups. Construction: notes/WP6_crossdomain.md "S3 start"."""
import pickle
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from common.config import DATA_EXTRA, SEED  # noqa: E402
from common.splits import group_halves  # noqa: E402
from fusion import composite as CP  # noqa: E402
from fusion.system import SystemFusion, alarm_events  # noqa: E402

CACHE = DATA_EXTRA / "cache_v3" / "WP6"
STAGES = ["gps", "lidar", "can", "network", "v2x", "cross_kitti", "cross_comma"]
N_BOOT = 1000


def load_packs(part):
    raw = {s: pickle.load(open(CACHE / f"s3_{s}.pkl", "rb"))[part] for s in STAGES}
    K = {d: raw[d] for d in ("gps", "lidar", "can", "network", "v2x")}
    K["cross"] = raw["cross_kitti"]
    C = {d: raw[d] for d in ("can", "network", "v2x")}
    C["cross"] = raw["cross_comma"]
    return {"K": K, "C": C}


def halves(packs, seed=SEED):
    """Group-aware validation halves per domain: KITTI drives shared by gps / cross / lidar; ROAD capture; D10 (day, period) block; VeReMi time
    block; comma route."""
    groups = lambda p: sorted({s["group"] for s in p["series"]})
    kd = sorted(set(groups(packs["K"]["gps"])) | set(groups(packs["K"]["cross"])))
    ka, kb = group_halves(kd, seed)
    out = {"A": {"K": {}, "C": {}}, "B": {"K": {}, "C": {}}}
    for d in ("gps", "lidar", "cross"):
        out["A"]["K"][d], out["B"]["K"][d] = set(ka), set(kb)
    for d in ("can", "network", "v2x"):
        a, b = group_halves(groups(packs["K"][d]), seed)
        for f in ("K", "C"):
            out["A"][f][d], out["B"][f][d] = set(a), set(b)
    a, b = group_halves(groups(packs["C"]["cross"]), seed)
    out["A"]["C"]["cross"], out["B"]["C"]["cross"] = set(a), set(b)
    return out


def clean_ticks(packs, groups, domains):
    """domain -> concatenated tick scores of the clean series of the allowed groups (present ticks only)."""
    out = {}
    for d in domains:
        ser = [s for s in packs[d]["series"] if s["kind"] == "clean" and (groups is None or s["group"] in groups[d])]
        out[d] = np.concatenate([s["score"] for s in ser])
    return out


def build_set(fam, packs, groups, seed, n_clean, n_att):
    B = CP.Builder(fam, packs, groups, seed)
    comps = B.clean_composites(n_clean)
    vf = CP.K_VEHICLE_FAMILIES if fam == "K" else CP.C_VEHICLE_FAMILIES
    for f in vf + CP.COORDINATED[fam]:
        comps += B.vehicle_attacks(f, n_att)
    for d in B.domains:
        if d == "cross":
            continue
        if fam == "K" and d == "gps":
            continue
        for f in B.domain_families(d):
            comps += B.domain_attacks(d, f, n_att)
    return comps


def raw_of(comps, domains):
    return {d: np.concatenate([c["parts"][d]["score"] for c in comps]) for d in domains}


def index_of(comps):
    lens = np.array([c["n"] for c in comps])
    return np.r_[0, np.cumsum(lens)]


def system_scores(fus, comps):
    X = fus.matrix(raw_of(comps, fus.domains))
    return X, fus.scores(X)


def named_domains(fus, X_row, comp, i):
    """Domains named by the explanation of tick i (own alarm, plus the strongest contributor)."""
    order = np.argsort(-X_row)
    out = [fus.domains[order[0]]]
    out += [fus.domains[j] for j in order[1:] if comp["parts"][fus.domains[j]]["dom_alarm"][i]]
    return out


def attributed(attacked, named):
    if attacked == "gps":
        return bool({"gps", "cross"} & set(named))
    if attacked == "gps+can":
        return bool({"gps", "cross"} & set(named))
    return attacked in named


def evaluate(fus, comps, thr=None, explain_all=False, layer_names=None):
    """Per composite: alarms; returns dict of metrics + per-composite outcomes."""
    thr = fus.threshold if thr is None else thr
    X, s = system_scores(fus, comps)
    al = s >= thr
    idx = index_of(comps)
    out, n_alarm, n_expl = [], 0, 0
    clean_ticks_n = clean_alarm = clean_events = 0
    clean_dur = 0
    examples = []
    for ci, c in enumerate(comps):
        a = al[idx[ci]:idx[ci + 1]]
        Xc = X[idx[ci]:idx[ci + 1]]
        if explain_all and a.any():
            for i in np.flatnonzero(a):
                e = fus.explain(i, Xc[i], c["parts"], layer_names, s[idx[ci] + i])
                n_alarm += 1
                n_expl += int(bool(e.reason) and len(e.domains) > 0)
                if len(examples) < 6 and (c["family"] != "none" and (len(examples) < 4 or c["family"] == "none")):
                    examples.append({"family": c["family"], "attacked": c["attacked"], "tick": int(i), "reason": e.reason})
        if c["family"] == "none":
            clean_ticks_n += c["n"]
            clean_alarm += int(a.sum())
            clean_events += alarm_events(a)
            clean_dur += c["n"]
            out.append({"family": "none", "vehicle": c["vehicle"], "alarm_ticks": int(a.sum()), "n": c["n"], "events": alarm_events(a)})
            continue
        hit = np.flatnonzero(a & c["label"])
        r = {"family": c["family"], "attacked": c["attacked"], "vehicle": c["vehicle"], "detected": bool(len(hit)), "n": c["n"],
             "any_alarm_after_onset": bool(a[max(c["onset"], 0):].any())}
        if len(hit):
            i = int(hit[0])
            r["delay"] = float(i - c["onset"])
            nm = named_domains(fus, Xc[i], c, i)
            r["named"] = nm
            r["attributed"] = attributed(c["attacked"], nm)
            if "cross" in c["parts"] and c["parts"]["cross"]["blame"] is not None:
                b = c["parts"]["cross"]["blame"][i]
                r["blame"] = None if b is None else str(b)
        out.append(r)
    res = {"clean_ticks": clean_ticks_n, "fa_tick": clean_alarm / max(clean_ticks_n, 1), "fa_events_per_hour": clean_events / max(clean_dur / 3600.0, 1e-9),
           "clean_hours": clean_dur / 3600.0}
    if explain_all:
        res["alarms"] = n_alarm
        res["alarms_with_explanation"] = n_expl
        res["examples"] = examples
    return res, out


def family_table(outs):
    fams = {}
    for r in outs:
        if r["family"] == "none":
            continue
        fams.setdefault(r["family"], []).append(r)
    tab = {}
    for f, rs in fams.items():
        det = [r for r in rs if r["detected"]]
        d = {"attacked": rs[0]["attacked"], "n": len(rs), "detection": float(np.mean([r["detected"] for r in rs])),
             "median_delay_s": float(np.median([r["delay"] for r in det])) if det else None,
             "attributed": float(np.mean([r["attributed"] for r in det])) if det else None}
        bl = [r.get("blame") for r in det if "blame" in r]
        if bl:
            d["cross_blame_counts"] = {str(k): int(v) for k, v in zip(*np.unique(np.array([str(b) for b in bl]), return_counts=True))}
        tab[f] = d
    return tab


def single_families(tab, fam):
    coord = set(CP.COORDINATED[fam])
    return [f for f in tab if f not in coord and f not in CP.V2_COMPARISON]


def mean_detection(tab, fams):
    return float(np.mean([tab[f]["detection"] for f in fams])) if fams else None


def cluster_ci(outs, fams, seed=SEED, n_boot=N_BOOT):
    """95% cluster bootstrap over vehicle groups: FA per tick (clean composites) and mean detection over `fams`."""
    rng = np.random.default_rng(seed)
    veh = sorted({r["vehicle"] for r in outs})
    by = {v: [r for r in outs if r["vehicle"] == v] for v in veh}
    fa, md = [], []
    for _ in range(n_boot):
        pick = rng.choice(len(veh), len(veh), replace=True)
        rs = [r for j in pick for r in by[veh[j]]]
        cl = [r for r in rs if r["family"] == "none"]
        fa.append(sum(r["alarm_ticks"] for r in cl) / max(sum(r["n"] for r in cl), 1))
        dets = [np.mean([r["detected"] for r in rs if r["family"] == f]) for f in fams if any(r["family"] == f for r in rs)]
        md.append(np.mean(dets) if dets else np.nan)
    q = lambda v: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))]
    return {"fa_tick": q(fa), "mean_detection": q(md), "n_vehicle_groups": len(veh)}


def make_fusion(domains, method, packs_val, halves_, fam):
    fus = SystemFusion(domains, method)
    fus.fit_calibration(clean_ticks(packs_val[fam], halves_["A"][fam], domains))
    return fus


def threshold_on(fus, comps_clean):
    _, s = system_scores(fus, comps_clean)
    return fus.fit_threshold(s)


def logistic_fit(fus, comps_a):
    X, _ = system_scores_raw(fus, comps_a)
    y = np.concatenate([c["label"] for c in comps_a])
    return fus.fit_logistic(X, y)


def system_scores_raw(fus, comps):
    X = fus.matrix(raw_of(comps, fus.domains))
    return X, None
