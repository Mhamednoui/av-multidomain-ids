"""WP2 S3: experiment machinery for L2a (clock skew) on top of the S2 L1 experiment (can/l1_exp.py).

Purpose: one code path for ROAD, Car-Hacking and D11. Skew variants are fitted on clean fit frames (`fit_skew`), raw skew
scores of the 8 variants are stored next to the L1 raw scores of the validation captures (E.Store accepts any raw dict),
the variant is chosen on validation (`select_skew`), the skew rule is calibrated like an L1 rule (tie-safe budget on clean
val frames / windows) and added to the L1 regime (`extend_regime`). Test files are scored one at a time (`score_file2`),
the common harness gives per-layer / combined / ablation tables (`eval_windows2`), including L1 alone (all_but_skew)
and a per-capture detection table for L1, L2a, L1 + L2a.
Nothing here reads test labels to choose anything.
"""
import numpy as np
import pandas as pd

from can import l1 as L
from can import l1_exp as E
from can import l2a_skew as K
from common.combiner import DomainCombiner
from common.evaluate import EvalSet, evaluate_domain
from common.metrics import budget_threshold

SK = K.SkewLayer.name


def skew_key(v: int) -> str:
    return f"{SK}#{v}"


def fit_skew(l1_profile: L.Profile, loader, variants=range(len(K.VARIANTS))) -> dict:
    """loader() -> iterable of (F, fit mask) (called three times: periods, errors, CUSUM states). Returns variant -> SkewProfile."""
    b = K.SkewBuilder(l1_profile)
    for F, m in loader():
        b.add_periods(F, m)
    profs = {v: b.prof(v) for v in variants}
    bvs = {}
    for v in variants:
        bvs[v] = K.SkewBuilder(l1_profile)
        bvs[v].gsum, bvs[v].gcnt = b.gsum, b.gcnt
    for F, m in loader():
        for v in variants:
            bvs[v].add_errors(profs[v], F, m)
    for v in variants:
        bvs[v].finish(profs[v])
    for F, m in loader():
        for v in variants:
            bvs[v].add_stats(profs[v], F, m)
    return {v: bvs[v].finish_scale(profs[v]) for v in variants}


def skew_raws(profs: dict, F: dict, variants) -> dict:
    return {skew_key(v): K.run_pass(F, profs[v])[0] for v in variants}


def coverage(profs: dict, F: dict, mask=None, variant=0) -> dict:
    """Share of frames whose ID is a scored periodic ID."""
    pos = profs[variant].lookup(F["id"])
    m = np.ones(len(pos), bool) if mask is None else mask
    return {"frames": int(m.sum()), "frames_on_scored_ids": int(((pos >= 0) & m).sum())}


def select_skew(store: E.Store, codes: E.AttCodes, variants, budget=0.01, only_masquerade=True) -> dict:
    """Variant with the highest mean window recall over the validation attack types (masquerade ones if any and
    `only_masquerade`), calibrated on the clean validation windows. Ties -> first."""
    y, att, clean = store.mw["y"] == 1, store.mw["att"], store.mw["clean"]
    types = sorted({int(a) for a in np.unique(att[y])})
    masq = [a for a in types if "masquerade" in codes.names[a]]
    use = masq if (only_masquerade and masq) else types
    res = {}
    for v in variants:
        raw = store.wr[skew_key(v)]
        r = K.SkewLayer(None, "window").calibrate_from_raw(raw[clean], budget)
        al = r.alarms(raw)
        rec = {codes.names[a]: float(al[y & (att == a)].mean()) for a in use}
        res[v] = {"variant": K.VARIANT_NAMES[v], "mean_recall": float(np.mean(list(rec.values()))) if rec else 0.0,
                  "recall": rec, "val_fa_clean_windows": float(al[clean].mean()),
                  "recall_all_types": {codes.names[a]: float(al[y & (att == a)].mean()) for a in types}}
    best = max(res, key=lambda k: (res[k]["mean_recall"], -k))
    return {"chosen": int(best), "selected_on": [codes.names[a] for a in use], "variants": {str(k): v for k, v in res.items()}}


class Regime2:
    """L1 regime + the skew rule; names = L1 rule names + [SK]; thr_comb = frame noisy-or threshold over all of them."""

    def __init__(self, base: E.Regime, store: E.Store, profile: K.SkewProfile, variant: int, budget: float):
        self.name, self.base = base.name, base
        self.names = E.RULE_NAMES + [SK]
        self.fr, self.wr = dict(base.fr), dict(base.wr)
        key = skew_key(variant)
        fc, wc = store.mf["clean"], store.mw["clean"]
        self.fr[SK] = K.SkewLayer(profile, "frame").calibrate_from_raw(store.fr[key][fc], budget)
        self.wr[SK] = K.SkewLayer(profile, "window").calibrate_from_raw(store.wr[key][wc], budget)
        cal = []
        for n in self.names:
            k = f"{n}#{base.profile.variant}" if f"{n}#{base.profile.variant}" in store.fr else n
            cal.append(self.fr[n].calibrated(store.fr[key if n == SK else k][fc]))
        self.thr_comb = budget_threshold(L.noisy_or(cal), budget)
        self.profile = base.profile


def score_file2(R: Regime2, F: dict, gname: str, tally: E.Tally, wrows: list, codes: E.AttCodes):
    """Score one test file: frame tallies (each rule, skew, combined L1+L2a) and window rows (raw per layer)."""
    fm = F["role"] == E.ROLE_TEST
    wmeta = E.window_meta(F)
    wm = wmeta["role"] == E.ROLE_TEST
    raws = {n: R.fr[n].frame_raw(F).astype(np.float32) for n in R.names}
    cal = {n: R.fr[n].calibrated(raws[n][fm]) for n in R.names}
    comb = L.noisy_or(list(cal.values()))
    alarms = {n: cal[n] >= R.fr[n].threshold for n in R.names}
    alarms["combined"] = comb >= R.thr_comb
    tally.add(gname, F, fm, alarms, codes)
    rows = {k: v[wm] for k, v in wmeta.items()}
    rows["group"] = np.full(int(wm.sum()), gname, dtype=object)
    for n in R.names:
        rows[f"raw_{n}"] = L.window_reduce(F, raws[n])[wm]
    wrows.append(pd.DataFrame(rows))


def store_table2(store: E.Store, groups: dict, base_variant: int, skew_variant: int) -> pd.DataFrame:
    d = {k: v for k, v in store.mw.items()}
    d["group"] = np.array([groups[int(b)] for b in store.mw["base"]], dtype=object)
    for n in E.RULE_NAMES:
        key = f"{n}#{base_variant}" if f"{n}#{base_variant}" in store.wr else n
        d[f"raw_{n}"] = store.wr[key]
    d[f"raw_{SK}"] = store.wr[skew_key(skew_variant)]
    return pd.DataFrame(d)


def _evidence2(R: Regime2, tbl: pd.DataFrame, names, rows=None) -> dict:
    sub = tbl if rows is None else tbl[rows]
    return {n: R.wr[n].evidence(sub[f"raw_{n}"].to_numpy(), sub["w_end"].to_numpy(), sub["wkey"].to_numpy())
            for n in names}


def _evalset2(R, tbl, codes, names) -> EvalSet:
    keep = ((tbl["y"] == 1) | tbl["clean"]).to_numpy()
    sub = tbl[keep]
    at = np.array([codes.names[int(a)] if y else "normal" for a, y in zip(sub["att"], sub["y"])], dtype=object)
    return EvalSet(evidence=_evidence2(R, tbl, names, keep), y=sub["y"].to_numpy(), attack_type=at,
                   group=sub["group"].to_numpy(), t=sub["w_end"].to_numpy())


def eval_windows2(R: Regime2, val_tbl, test_tbl, codes, first_inj, name, out_dir, budget=0.01, method="auto") -> dict:
    """Harness on L1 rules + skew; per-capture detail for each layer, L1 combined (l1), L1 + L2a combined (combined)."""
    names = R.names
    vs, ts = _evalset2(R, val_tbl, codes, names), _evalset2(R, test_tbl, codes, names)
    res = evaluate_domain(name, vs, ts, wp="WP2", budget=budget, method=method, out_dir=out_dir)
    ev_all = _evidence2(R, test_tbl, names)
    comb = DomainCombiner(method=res["combined"]["method"], budget=budget).fit(vs.evidence, vs.y, vs.group)
    l1n = E.RULE_NAMES
    m1 = res["ablation"][f"all_but_{SK}"]["method"]
    comb1 = DomainCombiner(method=m1, budget=budget).fit({n: vs.evidence[n] for n in l1n}, vs.y, vs.group)
    alarms = {n: np.array([e.alarm for e in ev_all[n]]) for n in names}
    alarms["combined_l1_l2a"] = np.array([e.alarm for e in comb.combine(ev_all)])
    alarms["combined_l1"] = np.array([e.alarm for e in comb1.combine({n: ev_all[n] for n in l1n})])
    pg = E.per_group(test_tbl, alarms, first_inj, codes)
    y = (test_tbl["y"] == 1).to_numpy()
    clean = test_tbl["clean"].to_numpy() & ~y
    other = ~test_tbl["clean"].to_numpy() & ~y
    hours = clean.sum() / 3600.0
    summ = {}
    for n, a in alarms.items():
        summ[n] = {"fa_clean_rate": float(a[clean].mean()) if clean.any() else None,
                   "false_alerts_per_hour_clean": float(a[clean].sum() / hours) if hours else None,
                   "fa_other_normal_rate": float(a[other].mean()) if other.any() else None,
                   "attack_window_recall": float(a[y].mean()) if y.any() else None}
    return {"harness": res, "per_capture": pg, "summary": summ, "combined_method": comb.method,
            "combined_l1_method": m1,
            "n_windows": {"clean": int(clean.sum()), "attack": int(y.sum()), "other_normal": int(other.sum())}}
