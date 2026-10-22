"""WP2 S7: selection on LOCO folds + validation attack captures (NO test capture is read). Writes results/WP2/s7_select.json and
results/WP2/s7_select_tables.md, and the candidate frozen design (CACHE/design.pkl).
Rules (written before any result): notes/WP2_can.md "S7 start".
  1 L1 tolerance variant: period rule alone, mean window recall over the 5 non-masquerade attack families (train + val) at the pooled LOCO 1% threshold.
  2 L2b check set K0..K3: lead FA <= 3% (validation attack leads), threshold-LOCO fold FA <= 5% in every fold, then highest mean masquerade recall.
  3 L3c FA-transfer design (M0/M1 x P0/P1 x r_min 0/0.9): validation union recall >= 0.9 and lead FA <= 3%, then lowest regime-averaged threshold-LOCO FA.
  4 combiner: common.combiner.DomainCombiner(method="auto") on the LOCO normal windows + the validation attack windows.
Usage: python -u -W ignore tools/WP2_S7_select.py
"""
import itertools
import pickle

import numpy as np

from WP2_S7_lib import CACHE, DYNO, FOLDS, OUT, VAL_ATTACK, BLOCKS, dump_json
from can import l1 as L
from can.stack_eval import noisy_or_log, threshold_loco
from common.calibration import ECDFCalibrator
from common.metrics import budget_threshold

BUDGET = 0.01
K_SETS = {"K0": ["linear"], "K1": ["linear", "joint"], "K2": ["linear", "joint", "rate"], "K3": ["linear", "joint", "rate", "value"]}
DESIGNS = [(m, r, p) for p in ("P0", "P1") for r in (0.0, 0.9) for m in ("M0", "M1")]       # index order = tie-break order
RULES = ["can.l1_id_allow", "can.l1_dlc", "can.l1_period", "can.l1_bus_load", "can.l1_flood"]
FA_LEAD_MAX, FA_FOLD_MAX, RECALL_MIN = 0.03, 0.05, 0.9


def load_group(group, names):
    return {n: dict(np.load(CACHE / "tables" / group / (n + ".npz"))) for n in names}


def dname(d):
    return f"{d[0]}_r{d[1]}_{d[2]}"


def l1_key(rule, k):
    return f"l1_{rule}#{k}" if rule == "can.l1_period" else f"l1_{rule}"


def okwin(t, key):
    return t[key][t["ok"]]


def pooled(F, units, key):
    return np.concatenate([okwin(F[u], key) for u in units])


def family(n):
    return n.split("_attack")[0]


def val_sets(V):
    masq = [n for n in V if n.endswith("_masquerade")]
    plain = [n for n in V if not n.endswith("_masquerade")]
    return masq, plain


def lead_windows(t):
    return t["ok"] & t["clean"] & (t["y"] == 0)


def attack_windows(t):
    return t["ok"] & (t["y"] == 1)


# ------------------------------------------------------------------ builders of layer raws
def l1_stat(t, k, ecdf):
    cal = np.column_stack([ecdf[r].transform(t[l1_key(r, k)]) for r in RULES])
    return noisy_or_log(cal)


def build_layer_raws(t, cfg, ecdf_rules, l3d_floor):
    """Window raw of every layer for one table (all windows, not only ok)."""
    out = {"L1": l1_stat(t, cfg["l1_variant"], ecdf_rules)}
    if cfg.get("K"):
        out["L2b"] = np.max(np.stack([t[f"l2b_{x}"] for x in cfg["K"]]), axis=0)
    m, r, _ = cfg["l3c"]
    out["L3c"] = t[f"l3c_{m}@{r}"]
    out["L3d"] = np.where(t["l3d"] > l3d_floor, t["l3d"], 0.0).astype(np.float32)
    return out


def main():
    F = load_group("folds", FOLDS)
    V = load_group("val", VAL_ATTACK)
    masq, plain = val_sets(V)
    res = {"folds": FOLDS, "windows_per_fold": {u: int(F[u]["ok"].sum()) for u in FOLDS}}
    md = []

    # ---- 1. L1 tolerance variant -------------------------------------------------------------------
    fams = sorted({family(n) for n in plain})
    res["l1_variant"] = {}
    for k in range(len(L.VARIANTS)):
        thr = budget_threshold(pooled(F, FOLDS, l1_key("can.l1_period", k)), BUDGET)
        rec = {}
        for fam in fams:
            a = np.concatenate([okwin(V[n], l1_key("can.l1_period", k))[(V[n]["y"] == 1)[V[n]["ok"]]] for n in plain if family(n) == fam])
            rec[fam] = float((a >= thr).mean())
        res["l1_variant"][k] = {"variant": list(L.VARIANTS[k]), "threshold": thr, "mean_recall": float(np.mean(list(rec.values()))), "recall": rec}
    k_best = max(res["l1_variant"], key=lambda k: (res["l1_variant"][k]["mean_recall"], -k))
    res["l1_variant_chosen"] = int(k_best)
    ecdf_rules = {r: ECDFCalibrator().fit(pooled(F, FOLDS, l1_key(r, k_best))) for r in RULES}
    l1f = {u: l1_stat(F[u], k_best, ecdf_rules) for u in FOLDS}
    thr_l1 = budget_threshold(np.concatenate([l1f[u][F[u]["ok"]] for u in FOLDS]), BUDGET)
    md.append("L1 variant (period rule alone, mean window recall of the 5 non-masquerade families at pooled 1%):\n" +
              "\n".join(f"- variant {k} {v['variant']}: {v['mean_recall']:.3f} {({a: round(b, 2) for a, b in v['recall'].items()})}" for k, v in res["l1_variant"].items()))

    # ---- 2. L2b check set ----------------------------------------------------------------------------
    res["l2b"] = {}
    for kn, K in K_SETS.items():
        sc = {u: okwin({"x": np.max(np.stack([F[u][f"l2b_{x}"] for x in K]), axis=0), "ok": F[u]["ok"]}, "x") for u in FOLDS}
        tl = threshold_loco(sc, FOLDS, BUDGET)
        thr = budget_threshold(np.concatenate(list(sc.values())), BUDGET)
        raw = lambda t: np.max(np.stack([t[f"l2b_{x}"] for x in K]), axis=0)
        lead = np.concatenate([raw(V[n])[lead_windows(V[n])] for n in plain])
        rec = {n: float((raw(V[n])[attack_windows(V[n])] >= thr).mean()) for n in masq}
        det = {n: bool((raw(V[n])[attack_windows(V[n])] >= thr).any()) for n in masq}
        res["l2b"][kn] = {"types": K, "threshold": thr, "fold_fa_threshold_loco": {u: v[1] for u, v in tl.items()},
                          "max_fold_fa": max(v[1] for v in tl.values()), "lead_fa": float((lead >= thr).mean()), "lead_windows": int(len(lead)),
                          "masq_window_recall": rec, "masq_detected": int(sum(det.values())), "mean_masq_recall": float(np.mean(list(rec.values())))}
    qual = [kn for kn, v in res["l2b"].items() if v["lead_fa"] <= FA_LEAD_MAX and v["max_fold_fa"] <= FA_FOLD_MAX]
    if qual:
        kbest = max(qual, key=lambda kn: (res["l2b"][kn]["mean_masq_recall"], -len(K_SETS[kn])))
        res["l2b_chosen"] = kbest
    else:
        res["l2b_chosen"] = None
    md.append("\nL2b check sets: " + "; ".join(f"{kn}: lead FA {v['lead_fa']:.3f}, max fold FA {v['max_fold_fa']:.3f}, masq recall {v['mean_masq_recall']:.2f} ({v['masq_detected']}/8)"
                                             for kn, v in res["l2b"].items()) + f"; chosen {res['l2b_chosen']}")

    # ---- 3. L3c design -------------------------------------------------------------------------------
    l3d_pool = np.concatenate([okwin(F[u], "l3d") for u in FOLDS])
    floor = float(l3d_pool.max())
    res["l3d_floor"] = floor
    res["l3d_pool_nonzero"] = int((l3d_pool > 0).sum())
    d_alarm = {n: (V[n]["l3d"] > floor) for n in V}
    res["designs"] = {}
    for i, d in enumerate(DESIGNS):
        key = f"l3c_{d[0]}@{d[1]}"
        pool_units = DYNO if d[2] == "P0" else FOLDS
        sc = {u: okwin(F[u], key) for u in FOLDS}
        tl = threshold_loco(sc, pool_units, BUDGET)
        dy = sum(sc[u].size * tl[u][1] for u in DYNO) / sum(sc[u].size for u in DYNO)
        rd = sum(sc[u].size * tl[u][1] for u in BLOCKS) / sum(sc[u].size for u in BLOCKS)
        thr = budget_threshold(np.concatenate([sc[u] for u in pool_units]), BUDGET)
        rec, det = {}, {}
        for n in masq:
            a = (V[n][key] >= thr) | d_alarm[n]
            aw = attack_windows(V[n])
            rec[n], det[n] = float(a[aw].mean()), bool(a[aw].any())
        lead = np.concatenate([((V[n][key] >= thr) | d_alarm[n])[lead_windows(V[n])] for n in plain])
        res["designs"][i] = {"design": dname(d), "threshold": thr, "fa_dyno_threshold_loco": dy, "fa_road_threshold_loco": rd,
                             "fa_regime_avg": (dy + rd) / 2, "max_fold_fa": max(v[1] for v in tl.values()),
                             "fold_fa": {u: tl[u][1] for u in FOLDS}, "lead_fa_union": float((lead).mean()), "lead_windows": int(len(lead)),
                             "mean_masq_recall_union": float(np.mean(list(rec.values()))), "masq_detected": int(sum(det.values())),
                             "masq_recall": rec}
    ok_d = [i for i, v in res["designs"].items() if v["mean_masq_recall_union"] >= RECALL_MIN and v["lead_fa_union"] <= FA_LEAD_MAX]
    if ok_d:
        res["design_chosen"] = int(min(ok_d, key=lambda i: (res["designs"][i]["fa_regime_avg"], i)))
        res["design_rule"] = "qualifying designs: lowest regime-averaged threshold-LOCO FA"
    else:
        res["design_chosen"] = int(min(res["designs"], key=lambda i: (res["designs"][i]["fa_regime_avg"], i)))
        res["design_rule"] = "no design met recall >= 0.9 and lead FA <= 3%: lowest regime-averaged FA"
    md.append("\nL3c designs: dyno-avg FA / road-avg FA / regime avg / max fold / lead FA(union) / masq recall (detected of 8)\n" + "\n".join(
        f"- {i} {v['design']}: {v['fa_dyno_threshold_loco']:.3f} / {v['fa_road_threshold_loco']:.3f} / {v['fa_regime_avg']:.3f} / {v['max_fold_fa']:.3f} / "
        f"{v['lead_fa_union']:.3f} / {v['mean_masq_recall_union']:.2f} ({v['masq_detected']}/8)" for i, v in res["designs"].items()) +
        f"\nchosen: {res['design_chosen']} ({res['design_rule']})")
    dch = DESIGNS[res["design_chosen"]]

    cfg = {"l1_variant": int(k_best), "K": K_SETS.get(res["l2b_chosen"]) if res["l2b_chosen"] else None, "l3c": list(dch), "l3d_floor": floor,
           "pool_l3c": dch[2]}
    res["cfg"] = cfg

    # ---- 4. layer calibrators + combiner on LOCO normals / validation attack windows ------------------------
    layers = ["L1", "L2b", "L3c", "L3d"] if cfg["K"] else ["L1", "L3c", "L3d"]
    raws_f = {u: build_layer_raws(F[u], cfg, ecdf_rules, floor) for u in FOLDS}
    raws_v = {n: build_layer_raws(V[n], cfg, ecdf_rules, floor) for n in VAL_ATTACK}
    pool_l3c = DYNO if dch[2] == "P0" else FOLDS
    calib = {}
    for ly in layers:
        units = pool_l3c if ly == "L3c" else FOLDS
        calib[ly] = ECDFCalibrator().fit(np.concatenate([raws_f[u][ly][F[u]["ok"]] for u in units]))
    pickle.dump({"cfg": cfg, "ecdf_rules": ecdf_rules, "calib": calib, "layers": layers, "thr_l1": thr_l1}, open(CACHE / "design.pkl", "wb"))
    dump_json(res, OUT / "s7_select.json")
    open(OUT / "s7_select_tables.md", "w").write("\n".join(md))
    print("\n".join(md))
    print("cfg", cfg)


if __name__ == "__main__":
    main()
