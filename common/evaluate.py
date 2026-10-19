"""Evaluation harness: per-layer + combined + ablation -> results/<WP>/<name>.json and .md table.

Inputs: two EvalSets (validation, test), each holding the Evidence of every layer of one domain
(aligned by sample), labels y (1 = attack), attack_type ("normal" for y == 0), group ids and times.
Per layer and combined: AUC, detection at the budget (threshold from validation normal scores
with the tie-safe rule), detection per attack type, false alarms on test normal data, detection
delay per attack segment. Ablation: each layer alone, all layers, all-but-one (combiner refitted
on validation each time). Nothing here looks at test labels to choose anything.

Stateful layers: use `score_groups`, which calls layer.reset() before every group, so state never
leaks from one drive / capture into the next (S1 report, item 8).
Reference: ARCHITECTURE.md section 4, RULES.md section 5.
"""
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from common.combiner import DomainCombiner
from common.config import BUDGET_DOMAIN, results_dir
from common.metrics import (auc, budget_threshold, detection_at_budget, detection_delay, merge_delays)


@dataclass
class EvalSet:
    evidence: dict          # layer name -> list[Evidence] (same sample order for all layers)
    y: np.ndarray
    attack_type: np.ndarray
    group: np.ndarray
    t: np.ndarray


def score_groups(layer, samples_by_group: dict) -> list:
    """Score each group's samples after layer.reset(); returns the concatenated Evidence list."""
    out = []
    for g in samples_by_group:
        layer.reset()
        out.extend(layer.score(samples_by_group[g]))
    return out


def _scores(evs):
    return np.array([e.score for e in evs], dtype=float)


def _summarize(val_scores, test_scores, vs: EvalSet, ts: EvalSet, budget) -> dict:
    y_v, y_t = np.asarray(vs.y).astype(bool), np.asarray(ts.y).astype(bool)
    d = detection_at_budget(val_scores[~y_v], test_scores, y_t, ts.attack_type, budget)
    alarm = test_scores >= d["threshold"]
    parts = []
    for g in sorted(set(map(str, ts.group))):
        m = np.array([str(x) == g for x in ts.group])
        parts.append(detection_delay(ts.t[m], y_t[m], alarm[m]))
    d["auc"] = auc(y_t, test_scores)
    d["delay"] = merge_delays(parts)
    d["n_test"] = int(len(y_t)); d["n_test_attack"] = int(y_t.sum())
    return d


def _combined(val: EvalSet, test: EvalSet, names, method, budget):
    sub_v = {n: val.evidence[n] for n in names}
    sub_t = {n: test.evidence[n] for n in names}
    comb = DomainCombiner(method=method, budget=budget).fit(sub_v, val.y, val.group)
    return comb, _scores(comb.combine(sub_v)), _scores(comb.combine(sub_t))


def evaluate_domain(name: str, val: EvalSet, test: EvalSet, wp: str = "WP0", budget: float = BUDGET_DOMAIN,
                    method: str = "auto", out_dir=None) -> dict:
    names = sorted(val.evidence)
    yv = np.asarray(val.y).astype(bool)
    res = {"name": name, "budget": budget, "layers": {}, "ablation": {}, "layer_names": names}
    for n in names:
        res["layers"][n] = _summarize(_scores(val.evidence[n]), _scores(test.evidence[n]), val, test, budget)
    comb, sv, st = _combined(val, test, names, method, budget)
    res["combined"] = _summarize(sv, st, val, test, budget)
    res["combined"]["method"] = comb.method
    res["combined"]["method_selection"] = comb.selection
    res["ablation"]["all"] = res["combined"]
    for n in names:
        res["ablation"][f"only_{n}"] = res["layers"][n]
    if len(names) > 2:
        for n in names:
            rest = [m for m in names if m != n]
            c, sv2, st2 = _combined(val, test, rest, method, budget)
            r = _summarize(sv2, st2, val, test, budget); r["method"] = c.method
            res["ablation"][f"all_but_{n}"] = r
    out = Path(out_dir) if out_dir else results_dir(wp)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.json").write_text(json.dumps(res, indent=1, default=_clean))
    (out / f"{name}.md").write_text(markdown_table(res))
    return res


def _clean(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    raise TypeError(type(o))


def markdown_table(res: dict) -> str:
    attacks = sorted({a for r in res["ablation"].values() for a in r["detection_by_attack"]})
    head = ["configuration", "AUC", "detection", "false alarms"] + [f"det {a}" for a in attacks] + ["median delay (s)"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for k, r in res["ablation"].items():
        row = [k, f"{r['auc']:.3f}", f"{100 * r['detection']:.1f}%", f"{100 * r['false_alarm_rate']:.2f}%"]
        row += [f"{100 * r['detection_by_attack'].get(a, float('nan')):.1f}%" for a in attacks]
        row += [f"{r['delay']['median_delay_s']:.1f}"]
        lines.append("| " + " | ".join(row) + " |")
    return f"Budget {100 * res['budget']:.1f}% false alarms on validation normal data. Domain: {res['name']}.\n\n" + "\n".join(lines) + "\n"
