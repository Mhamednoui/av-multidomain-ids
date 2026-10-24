"""WP6 S4 shared code for tools/WP6_S4_dev.py (validation) and tools/WP6_S4_test.py (the one test run): held-out definitions, layer tiers, zero-day tick
packs with evidence-novelty columns, system variants (entries, fusion fit, scoring), composite evaluation by family category, tier table.
Construction and acceptance rule: notes/WP6_crossdomain.md "S4 start" (written before any S4 result). Builds on the S3 lib (composites, halves, bootstrap).
"""
import pickle
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.config import SEED  # noqa: E402,F401
from common.metrics import auc, budget_threshold  # noqa: E402
from fusion import composite as CP  # noqa: E402
from fusion import novelty as NV  # noqa: E402
from fusion.system import SystemFusion, alarm_events  # noqa: E402
import WP6_S3_lib as L3  # noqa: E402

CACHE = L3.CACHE
BUDGET_TIER = 0.01

# ---------------------------------------------------------------- held-out types (fixed in notes before any result)
GPS_HELD = {"doppler_spoof", "meaconing"}
NET_HELD = {"PortScan", "Web-BruteForce", "Web-XSS"}
V2X_HELD = {"06_ConstSpeedOffset", "17_DataReplaySybil"}
CATS = ["heldout", "seen", "lidar_labelfree", "choice_seen"]


def category(fam, attacked):
    if fam == "none":
        return None
    if attacked == "gps":
        return "heldout" if fam in GPS_HELD else "seen"
    if attacked == "can":
        return "heldout" if fam.endswith("_masquerade") else "seen"
    if attacked == "network":
        return "heldout" if fam in NET_HELD else "seen"
    if attacked == "v2x":
        return "heldout" if fam in V2X_HELD else "seen"
    if attacked == "lidar":
        return "lidar_labelfree"
    return "choice_seen"                         # cross-domain-only families and coordinated scenarios


def domain_category_fn(d):
    """Family name -> category for the tick-level tier table of domain d (tick families of that domain)."""
    if d == "gps":
        return lambda f: "choice_seen" if f == "gps_can" else category(f, "gps")
    if d == "cross":                              # the motion witnesses see the GPS families (held out for the GPS domain) and the vehicle families
        return lambda f: category(f, "gps") if f in ("drift", "accel_drift") or f in GPS_HELD else "choice_seen"
    return lambda f: category(f, d)


# ---------------------------------------------------------------- layer tiers (fixed a priori)
NET_H = ["net.tcp_flags", "net.scan", "net.trw", "net.bruteforce"]
NET_L3 = ["net.l3_service", "net.l3_ae"]
NET_ZD = NET_H + NET_L3
GROUPS = {
    "gps": {"l3": ["gps.ekf_nis", "gps.cusum_ekf", "gps.cusum_dr"]},
    "can": {"rules": ["can.l1_spec_rules"], "l3": ["can.l3c_signal_predictors", "can.l3d_reverse_state"]},
    "network": {"rules": NET_H, "l3": NET_L3},
    "v2x": {"l3": ["v2x.kf_nis", "v2x.kf_cusum_hi", "v2x.track_birth"]},
    "lidar": {"rules": ["lidar.l1_union"]},
}
NOV_KINDS = ["mcd", "iforest"]
NOV_COL = {k: f"nov.{k}" for k in NOV_KINDS}
UNIQUE = ["gps", "lidar", "can", "network", "v2x", "cross_kitti", "cross_comma"]
DOM_OF = {"cross_kitti": "cross", "cross_comma": "cross"}


def rules_of(d, names):
    g = GROUPS.get(d, {})
    if "rules" in g:
        return list(g["rules"])
    return [n for n in names if n not in g.get("l3", []) and not n.startswith("nov.")]


def l3_of(d):
    return list(GROUPS.get(d, {}).get("l3", []))


# ---------------------------------------------------------------- packs
def load_unique(part):
    raw = {s: pickle.load(open(CACHE / f"s3_{s}.pkl", "rb"))[part] for s in UNIQUE}
    raw["network"] = pickle.load(open(CACHE / "s4_network.pkl", "rb"))[part]          # stack O layers; first four columns = S3 network pack
    return raw


def assemble(u):
    K = {d: u[d] for d in ("gps", "lidar", "can", "network", "v2x")}
    K["cross"] = u["cross_kitti"]
    C = {d: u[d] for d in ("can", "network", "v2x")}
    C["cross"] = u["cross_comma"]
    return {"K": K, "C": C}


def feature_idx(key, names):
    if key == "network":
        return [names.index(n) for n in NET_ZD]
    return [i for i, n in enumerate(names) if not n.startswith("nov.")]


def halves_unique(u):
    H = L3.halves(assemble(u))
    gA = {"gps": H["A"]["K"]["gps"], "can": H["A"]["K"]["can"], "network": H["A"]["K"]["network"], "v2x": H["A"]["K"]["v2x"],
          "cross_kitti": H["A"]["K"]["cross"], "cross_comma": H["A"]["C"]["cross"]}
    gB = {"gps": H["B"]["K"]["gps"], "lidar": H["B"]["K"]["lidar"], "can": H["B"]["K"]["can"], "network": H["B"]["K"]["network"],
          "v2x": H["B"]["K"]["v2x"], "cross_kitti": H["B"]["K"]["cross"], "cross_comma": H["B"]["C"]["cross"]}
    return H, gA, gB


def _blocks(series, size=30):
    out, off = [], 0
    for s in series:
        n = len(s["score"])
        out.append(off + np.arange(n) // size)
        off += int(np.ceil(n / size)) + 1
    return out


def fit_novelty(u_val, gA):
    """Detectors fitted on CLEAN validation half-A ticks (per unique pack and kind) + out-of-fold raw scores of those ticks."""
    dets, oof = {}, {}
    for key in ("gps", "can", "network", "v2x", "cross_kitti", "cross_comma"):
        p = u_val[key]
        idx = feature_idx(key, p["layer_names"])
        names = [p["layer_names"][i] for i in idx]
        ser = [s for s in p["series"] if s["kind"] == "clean" and s["group"] in gA[key]]
        X = np.concatenate([s["layers"][:, idx] for s in ser])
        bl = np.concatenate(_blocks(ser))
        cut = np.r_[0, np.cumsum([len(s["score"]) for s in ser])]
        for kind in NOV_KINDS:
            dets[(key, kind)] = (NV.EvidenceNovelty(kind, layer_names=names).fit(X), idx)
            o = NV.fit_oof(kind, X, bl)
            for s, a, b in zip(ser, cut[:-1], cut[1:]):
                oof[(key, kind, s["name"])] = o[a:b]
    return dets, oof


def attach_novelty(u, dets, oof=None):
    """New packs with the novelty columns appended to layers / layer_names / layer_thr (original packs untouched)."""
    out = {}
    for key, p in u.items():
        if key == "lidar":
            out[key] = p
            continue
        q = dict(p)
        q["layer_names"] = list(p["layer_names"]) + [NOV_COL[k] for k in NOV_KINDS]
        q["layer_thr"] = np.r_[np.asarray(p["layer_thr"], float), [0.99] * len(NOV_KINDS)]
        ser = []
        for s in p["series"]:
            cols = []
            for kind in NOV_KINDS:
                det, idx = dets[(key, kind)]
                v = det.score(s["layers"][:, idx])
                if oof is not None and (key, kind, s["name"]) in oof:
                    v = oof[(key, kind, s["name"])]
                cols.append(v)
            t = dict(s)
            t["layers"] = np.column_stack([s["layers"]] + cols).astype(np.float32)
            if "layer_alarm" in s:                                       # cross-domain series carry their own alarm flags
                t["layer_alarm"] = np.column_stack([s["layer_alarm"], np.zeros((len(s["score"]), len(NOV_KINDS)), bool)])
            ser.append(t)
        q["series"] = ser
        out[key] = q
    return out


# ---------------------------------------------------------------- system variants
def variant(fam, method="noisy_or", net="H", nov=None, groups="full"):
    """entries: list of (name, domain, spec); spec None = the domain's own combined tick score, list = max over the named layers,
    ("rules"|"l3", d) = the tier group of the domain."""
    doms = CP.K_DOMAINS if fam == "K" else CP.C_DOMAINS
    ent = []
    for d in doms:
        if groups == "full":
            if d == "lidar":
                ent.append((d, d, ["lidar.l1_union"]))
            elif d == "network":
                ent.append((d, d, None if net == "H" else NET_ZD))
            else:
                ent.append((d, d, None))
        elif groups == "rules":
            ent.append((d, d, ("rules", d)))
        elif groups == "l3":
            if l3_of(d):
                ent.append((d, d, ("l3", d)))
    if nov and groups == "full":
        for d in doms:
            if d != "lidar":
                ent.append((f"{d}.nov", d, [NOV_COL[nov]]))
    return {"fam": fam, "method": method, "net": net, "nov": nov, "groups": groups, "entries": ent}


def var_key(v):
    return f"{v['fam']}|{v['method']}|net={v['net']}|nov={v['nov']}|groups={v['groups']}"


def _cols(spec, d, names):
    if spec is None:
        return None
    if isinstance(spec, tuple):
        return rules_of(d, names) if spec[0] == "rules" else l3_of(d)
    return spec


def values(obj, d, spec, names):
    cols = _cols(spec, d, names)
    if cols is None:
        return np.asarray(obj["score"], np.float32)
    return obj["layers"][:, [names.index(c) for c in cols]].max(axis=1)


def entry_raw_clean(var, packs_fam, groupsA):
    out = {}
    for name, d, spec in var["entries"]:
        p = packs_fam[d]
        ser = [s for s in p["series"] if s["kind"] == "clean" and s["group"] in groupsA[d]]
        out[name] = np.concatenate([values(s, d, spec, p["layer_names"]) for s in ser])
    return out


def entry_raw_comps(var, comps, packs_fam):
    out = {}
    for name, d, spec in var["entries"]:
        names = packs_fam[d]["layer_names"]
        out[name] = np.concatenate([values(c["parts"][d], d, spec, names) for c in comps])
    return out


def fit_variant(var, packs_fam, groupsA, comps_B_clean):
    """packs_fam: packs[fam] (domain -> pack); groupsA: half-A groups of that family (domain -> set)."""
    fus = SystemFusion([e[0] for e in var["entries"]], var["method"])
    fus.fit_calibration(entry_raw_clean(var, packs_fam, groupsA))
    fus.fit_threshold(fus.scores(fus.matrix(entry_raw_comps(var, comps_B_clean, packs_fam))))
    return fus


def score_variant(var, fus, comps, packs_fam):
    X = fus.matrix(entry_raw_comps(var, comps, packs_fam))
    return X, fus.scores(X)


# ---------------------------------------------------------------- evaluation
def evaluate(comps, s, thr):
    idx = L3.index_of(comps)
    al = s >= thr
    outs = []
    ct = ca = ce = 0
    for ci, c in enumerate(comps):
        a = al[idx[ci]:idx[ci + 1]]
        if c["family"] == "none":
            ct += c["n"]
            ca += int(a.sum())
            ce += alarm_events(a)
            outs.append({"family": "none", "attacked": None, "vehicle": c["vehicle"], "alarm_ticks": int(a.sum()), "n": c["n"], "events": alarm_events(a), "detected": False})
            continue
        hit = np.flatnonzero(a & c["label"])
        r = {"family": c["family"], "attacked": c["attacked"], "vehicle": c["vehicle"], "n": c["n"], "detected": bool(len(hit)), "alarm_ticks": int(a.sum())}
        if len(hit):
            r["delay"] = float(hit[0] - c["onset"])
        outs.append(r)
    return {"clean_ticks": ct, "fa_tick": ca / max(ct, 1), "fa_events_per_hour": ce / max(ct / 3600.0, 1e-9), "threshold": float(thr)}, outs


def family_table(outs):
    fams = {}
    for r in outs:
        if r["family"] != "none":
            fams.setdefault(r["family"], []).append(r)
    tab = {}
    for f, rs in fams.items():
        det = [r for r in rs if r["detected"]]
        tab[f] = {"attacked": rs[0]["attacked"], "category": category(f, rs[0]["attacked"]), "n": len(rs), "detection": float(np.mean([r["detected"] for r in rs])),
                  "median_delay_s": float(np.median([r["delay"] for r in det])) if det else None}
    return tab


def cat_means(tab):
    out = {}
    for c in CATS:
        v = [x["detection"] for x in tab.values() if x["category"] == c]
        out[c] = float(np.mean(v)) if v else None
    return out


def domain_cat_means(tab):
    out = {}
    for f, x in tab.items():
        out.setdefault((x["category"], x["attacked"]), []).append(x["detection"])
    return {f"{c}|{d}": float(np.mean(v)) for (c, d), v in out.items()}


def selection_families(tab):
    """Families that may drive a validation choice: everything that is not a held-out type."""
    return [f for f, x in tab.items() if x["category"] != "heldout"]


def ci_for(outs, tab, cat):
    fams = [f for f, x in tab.items() if x["category"] == cat]
    return L3.cluster_ci(outs, fams) if fams else None


def summarize(comps, s, thr):
    m, outs = evaluate(comps, s, thr)
    tab = family_table(outs)
    m["by_category"] = cat_means(tab)
    m["by_category_domain"] = domain_cat_means(tab)
    m["families"] = tab
    return m, outs, tab


# ---------------------------------------------------------------- tier table (tick level, per domain)
def group_cols(key, names):
    d = DOM_OF.get(key, key)
    rows = {}
    rules = rules_of(d, names)
    l3 = l3_of(d)
    if rules:
        rows["rules (physics / rule)"] = rules
    if l3:
        rows["L3 (normal-only model)"] = l3
    if rules and l3:
        rows["rules + L3"] = rules + l3
    return rows


def tier_rows(key, p_val, p_test, groupsB, extra=None):
    """rows: name -> dict(thr, fa_test, families {f: {det, n_ticks, auc}}). Group score = max of the calibrated layers; threshold = tie-safe 1% of the clean
    validation HALF-B ticks. extra: row name -> (fn_val(series), fn_test(series)) for columns that are not in the pack (S7 L3)."""
    names = p_test["layer_names"]
    spec = {}
    for r, cols in group_cols(key, names).items():
        ix = [names.index(c) for c in cols]
        spec[r] = (lambda s, ix=ix: s["layers"][:, ix].max(axis=1))
    if key != "lidar":
        for k in NOV_KINDS:
            j = names.index(NOV_COL[k])
            spec[f"novelty {k} (evidence vectors)"] = (lambda s, j=j: s["layers"][:, j])
    spec["frozen domain score (S3)"] = lambda s: s["score"]
    vclean = [s for s in p_val["series"] if s["kind"] == "clean" and s["group"] in groupsB]
    tclean = [s for s in p_test["series"] if s["kind"] == "clean"]
    fns = {r: (fn, fn) for r, fn in spec.items()}
    fns.update(extra or {})
    out = {}
    for r, (fv, ft) in fns.items():
        cv = np.concatenate([fv(s) for s in vclean])
        cv = cv[np.isfinite(cv)]
        thr = budget_threshold(cv, BUDGET_TIER)
        ct = np.concatenate([ft(s) for s in tclean])
        ct = ct[np.isfinite(ct)]
        row = {"thr": float(thr), "fa_test": float((ct >= thr).mean()), "clean_ticks": int(len(ct)), "families": {}}
        fams = {}
        for s in p_test["series"]:
            if s["kind"] != "attack":
                continue
            v = ft(s)
            for f in set(s["fam"][s["label"]].astype(str)):
                m = s["label"] & (s["fam"].astype(str) == f) & np.isfinite(v)
                if m.any():
                    fams.setdefault(f, []).append(v[m])
        for f, lst in fams.items():
            a = np.concatenate(lst)
            row["families"][f] = {"det": float((a >= thr).mean()), "n_ticks": int(len(a)),
                                  "auc": float(auc(np.r_[np.zeros(len(ct)), np.ones(len(a))], np.r_[ct, a]))}
        out[r] = row
    return out


def tier_summary(rows, d):
    cf = domain_category_fn(d)
    for r, row in rows.items():
        for c in ("heldout", "seen", "lidar_labelfree", "choice_seen"):
            fs = [x for f, x in row["families"].items() if cf(f) == c]
            row[f"mean_det_{c}"] = float(np.mean([x["det"] for x in fs])) if fs else None
            row[f"mean_auc_{c}"] = float(np.mean([x["auc"] for x in fs])) if fs else None
    return rows


def fast_ci(outs, fams, seed=SEED, n_boot=1000):
    """Vectorised version of WP6_S3_lib.cluster_ci (same cluster bootstrap over vehicle groups; same quantities)."""
    veh = sorted({r["vehicle"] for r in outs})
    vi = {v: i for i, v in enumerate(veh)}
    V, F = len(veh), len(fams)
    cn, ca = np.zeros(V), np.zeros(V)
    det, cnt = np.zeros((V, F)), np.zeros((V, F))
    fi = {f: j for j, f in enumerate(fams)}
    for r in outs:
        i = vi[r["vehicle"]]
        if r["family"] == "none":
            cn[i] += r["n"]
            ca[i] += r["alarm_ticks"]
        elif r["family"] in fi:
            det[i, fi[r["family"]]] += r["detected"]
            cnt[i, fi[r["family"]]] += 1
    w = np.random.default_rng(seed).multinomial(V, np.full(V, 1.0 / V), size=n_boot).astype(float)
    fa = (w @ ca) / np.maximum(w @ cn, 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        d = (w @ det) / (w @ cnt)
    md = np.nanmean(d, axis=1)
    q = lambda v: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))]
    return {"fa_tick": q(fa), "mean_detection": q(md), "n_vehicle_groups": V}
