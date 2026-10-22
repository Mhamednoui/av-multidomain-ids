"""WP2 S7: descriptive diagnostics (no design change follows).
  dev   threshold-LOCO false-alarm rate of the FROZEN stack on the 10 development folds (what the calibration predicts for a new session)
  test  POST-VERDICT description of the ROAD test false alarms: which layer / L1 rule fires on the clean test windows (labelled descriptive; ROAD test exposure 6 is not re-scored)
Usage: python -u -W ignore tools/WP2_S7_diag.py dev|test      -> results/WP2/s7_diag_dev.json | s7_diag_test.json
"""
import sys

import numpy as np

from WP2_S7_final import DOM, load_group
from WP2_S7_lib import BLOCKS, DYNO, FOLDS, OUT, TEST, TEST_AMB, TEST_ATTACK, dump_json
from WP2_S7_select import RULES, l1_key
from can.domain import CanDomain, layer_raws
from can.stack_eval import threshold_loco


def combined_max(dom, tab):
    cal = dom.calibrated(tab)
    return np.max(np.stack([cal[l] for l in dom.layers]), axis=0), cal


def dev():
    dom = CanDomain.load(DOM)
    assert dom.combiner.method == "max", dom.combiner.method
    F = load_group("folds", FOLDS)
    comb, per_layer = {}, {l: {} for l in dom.layers}
    for u in FOLDS:
        c, cal = combined_max(dom, F[u])
        ok = F[u]["ok"]
        comb[u] = c[ok]
        for l in dom.layers:
            per_layer[l][u] = cal[l][ok]
    out = {"combined_threshold_loco": {}, "per_layer_threshold_loco": {}}
    tl = threshold_loco(comb, FOLDS)
    out["combined_threshold_loco"] = {u: v[1] for u, v in tl.items()}
    for l in dom.layers:
        pool = DYNO if l == "L3c" else FOLDS
        out["per_layer_threshold_loco"][l] = {u: v[1] for u, v in threshold_loco(per_layer[l], pool).items()}
    n = {u: len(comb[u]) for u in FOLDS}
    for name, units in (("dyno", DYNO), ("road", BLOCKS), ("all", FOLDS)):
        out[f"combined_pooled_{name}"] = sum(tl[u][1] * n[u] for u in units) / sum(n[u] for u in units)
    dump_json(out, OUT / "s7_diag_dev.json")
    print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in out.items() if k.startswith("combined_pooled")})
    print({u: round(v, 3) for u, v in out["combined_threshold_loco"].items()})


def test():
    dom = CanDomain.load(DOM)
    T = load_group("test", TEST)
    des = dom.ecdf_rules
    out = {"note": "post-verdict description of the ROAD test false alarms; no design change follows"}
    for u in TEST_AMB + [n for n in TEST_ATTACK if not n.endswith("_masquerade")]:
        t = T[u]
        m = t["ok"] & t["clean"] & (t["y"] == 0)
        if not m.any():
            continue
        c, cal = combined_max(dom, t)
        al = (c >= dom.combiner.threshold) & m
        r = {"clean_windows": int(m.sum()), "combined_alarms": int(al.sum())}
        for l in dom.layers:
            r[f"{l}_alarm"] = int(((cal[l] >= dom.layer_thresholds[l]) & m).sum())
            r[f"{l}_is_max_in_combined_alarms"] = int(((cal[l] >= c - 1e-12) & al).sum())
        k = dom.cfg["l1_variant"]
        thr_rule = {}
        for rl in RULES:
            thr_rule[rl] = int((des[rl].transform(t[l1_key(rl, k)]) >= 0.99).__and__(m).sum())
        r["L1_rules_above_ECDF_0.99"] = thr_rule
        out[u] = r
    dump_json(out, OUT / "s7_diag_test.json")
    for u, r in out.items():
        if u != "note":
            print(u, r)


if __name__ == "__main__":
    {"dev": dev, "test": test}[sys.argv[1]]()
