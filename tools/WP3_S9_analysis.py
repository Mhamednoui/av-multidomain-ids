"""WP3 S9 analysis: a pure function of score frames (columns scan, drive, idx, attack, ep, step, raw_<layer>) -> one dict of results.
Used on the validation frames (dry run, tools/WP3_S9_dryrun.py) and on the test frames (the single verdict run, tools/WP3_S9_final.py).
frames: 'ref' (out-of-fold clean scores of the 16 train+val drives), 'clean' (clean scans to report FA on), 'att' (attacked scans),
        optional 'ep' (sensor-fixed persistent episodes), 'epw' (world-fixed persistent episodes).
Everything is label-free except the choice of which attacks to look at: detection is always at the stack alarm (threshold from ref)."""
import numpy as np
import pandas as pd
from scipy.stats import beta
from sklearn.metrics import roc_auc_score

from lidar import combine as K
from lidar.data import FRAME_DT
from lidar.sequence import EPISODE_SCANS, rolling_logodds

PHYS = ["ph_replace_near", "ph_replace_far", "ph_budget_near", "ph_budget_far", "PointDrop", "IntensitySpoof"]
CMP = ["cmp_boxcloud", "cmp_mradd_near", "cmp_mradd_far"]
HEAD = ["raw_L1", "raw_L2a", "raw_L2c", "raw_L2d"]


def clopper(k, n, a=0.05):
    if n == 0:
        return [float("nan")] * 2
    lo = 0.0 if k == 0 else float(beta.ppf(a / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - a / 2, k + 1, n - k))
    return [lo, hi]


def per_drive(alarm, drives):
    a = pd.Series(np.asarray(alarm, float))
    return {d: float(v) for d, v in a.groupby(np.asarray(drives)).mean().items()}


def detection_block(alarm, att, names):
    out = {}
    for a in names:
        k = (att["attack"] == a).to_numpy()
        if not k.any():
            continue
        p, lo, hi = K.drive_bootstrap(alarm[k], att["drive"].to_numpy()[k])
        out[a] = {"det": p, "ci95": [lo, hi], "n": int(k.sum()), "per_drive": per_drive(alarm[k], att["drive"].to_numpy()[k])}
    return out


def run_stack(ref, clean, att, cols, method, budget=0.01, with_auc=True):
    st = K.Stack(cols, method, budget).fit(ref)
    ac = st.alarm(clean)
    p, lo, hi = K.drive_bootstrap(ac, clean["drive"].to_numpy())
    sizes = ref.groupby("drive").size().to_dict()
    lodo = K.lodo_fa(ref, cols, method, budget)
    mean, worst, who = K.lodo_summary(lodo, sizes)
    aa = st.alarm(att)
    names = [a for a in PHYS + CMP if (att["attack"] == a).any()]
    r = {"cols": list(cols), "method": method, "budget": budget, "threshold": float(st.threshold), "fa": p, "fa_ci95": [lo, hi],
         "fa_per_drive": per_drive(ac, clean["drive"].to_numpy()), "fa_ref": float(st.alarm(ref).mean()),
         "lodo_fa": lodo, "lodo_mean": mean, "lodo_worst": worst, "lodo_worst_drive": who,
         "det": detection_block(aa, att, names)}
    r["mean_phys"] = float(np.mean([r["det"][a]["det"] for a in PHYS if a in r["det"]]))
    if with_auc:
        sc, sa = st.stat(clean), st.stat(att)
        r["auc"] = {a: float(roc_auc_score(np.r_[np.zeros(len(sc)), np.ones(int((att.attack == a).sum()))], np.r_[sc, sa[(att.attack == a).to_numpy()]]))
                    for a in names}
        if len(cols) > 1:
            dom = st.dominant(att)
            r["dominant_layer_of_alarms"] = {}
            for a in names:
                k = (att["attack"] == a).to_numpy() & aa
                r["dominant_layer_of_alarms"][a] = {c: int((dom[k] == j).sum()) for j, c in enumerate(cols)}
    return r, st, aa


def episode_block(st, ref, clean, ep):
    """Rolling log-odds rule (v2): per-scan calibrated score = ECDF of the stack stat on the out-of-fold reference; threshold = 99th percentile
    of the rolling statistic over clean reference windows; detected = statistic over the threshold within 3 s (30 scans) of the onset."""
    r = ref.assign(cal=st.score(ref)).sort_values(["drive", "idx"])
    byd = {d: g.cal.to_numpy() for d, g in r.groupby("drive")}
    wref = [s[a:a + EPISODE_SCANS] for s in byd.values() for a in range(0, len(s) - EPISODE_SCANS + 1, 10)]
    thr = float(np.quantile(np.concatenate([rolling_logodds(w) for w in wref]), 0.99))
    c = clean.assign(cal=st.score(clean)).sort_values(["drive", "idx"])
    wins = [g.cal.to_numpy()[a:a + EPISODE_SCANS] for _, g in c.groupby("drive") for a in range(0, len(g) - EPISODE_SCANS + 1, EPISODE_SCANS)]
    fer = float(np.mean([(rolling_logodds(w) >= thr).any() for w in wins]))
    e = ep.assign(cal=st.score(ep), al=st.alarm(ep))
    kinds = {}
    for kind, g in e.groupby("attack"):
        det, delays = [], []
        for _, x in g.groupby(["drive", "ep"]):
            s = rolling_logodds(x.sort_values("step").cal.to_numpy())
            hit = np.flatnonzero(s >= thr)
            ok = len(hit) > 0 and hit[0] + 1 <= EPISODE_SCANS
            det.append(bool(ok))
            if ok:
                delays.append((hit[0] + 1) * FRAME_DT)
        k = int(sum(det))
        kinds[kind] = {"episodes": len(det), "detected_3s": k, "ci95_exact": clopper(k, len(det)),
                       "median_first_alert_s": float(np.median(delays)) if delays else None,
                       "onset_scan_alarm": float(g[g.step == 1].al.mean()), "sustained_scan_alarm": float(g[g.step >= 2].al.mean())}
    return {"stat_threshold": thr, "false_episode_rate": fer, "n_clean_windows": len(wins), "kinds": kinds}


def analyse(fr, method, optional=None, budgets=(0.02, 0.04)):
    """fr: frames. method: the combiner chosen on validation. optional: {row name: cols} extra stacks (L2b, L4, density, ...)."""
    ref, clean, att = fr["ref"], fr["clean"], fr["att"]
    res = {"method": method, "n_ref": int(len(ref)), "n_clean": int(len(clean)), "n_att": att.attack.value_counts().to_dict()}
    head, st, alarm = run_stack(ref, clean, att, HEAD, method)
    res["headline"] = head
    # each layer alone at its own 1 % (not budget matched: four layers add up to ~3-4 % FA)
    res["layers_alone"] = {c: run_stack(ref, clean, att, [c], "max")[0] for c in HEAD}
    # ablation, same combiner and same 1 % total budget
    res["all_but"] = {c: run_stack(ref, clean, att, [x for x in HEAD if x != c], method)[0] for c in HEAD}
    earn = {}
    for c in HEAD:
        gain = {a: head["det"][a]["det"] - res["all_but"][c]["det"][a]["det"] for a in PHYS if a in head["det"]}
        best = max(gain, key=gain.get)
        earn[c] = {"largest_loss_when_removed": gain[best], "attack": best, "earns_place": bool(gain[best] >= 0.03),
                   "loss_per_attack": gain}
    res["earns_place"] = earn
    # other combiners at the same budget (what the choice cost) and larger total budgets (descriptive, not chosen)
    res["other_combiners"] = {m: run_stack(ref, clean, att, HEAD, m, with_auc=False)[0] for m in K.METHODS if m != method}
    res["budgets"] = {f"{b:.2f}": run_stack(ref, clean, att, HEAD, method, b, with_auc=False)[0] for b in budgets}
    res["each_layer_at_own_1pct_union"] = run_stack(ref, clean, att, HEAD, "split", 0.01 * len(HEAD), with_auc=False)[0]
    # dilution: stack against the best single layer per attack, paired over scans
    res["dilution"] = {}
    for a in [x for x in PHYS if x in head["det"]]:
        k = (att["attack"] == a).to_numpy()
        best = max(HEAD, key=lambda c: res["layers_alone"][c]["det"][a]["det"])
        la = K.Stack([best], "max", 0.01).fit(ref).alarm(att)[k]
        res["dilution"][a] = {"best_layer": best, "best_layer_alone": float(la.mean()), "stack": float(alarm[k].mean()),
                              "loss": float(la.mean() - alarm[k].mean())}
    res["optional"] = {}
    for name, cols in (optional or {}).items():
        if all(c in ref.columns and c in att.columns for c in cols):
            res["optional"][name] = run_stack(ref, clean, att, cols, method, with_auc=False)[0]
    # persistent episodes
    res["episodes"] = {}
    for tag in ("ep", "epw"):
        if tag in fr:
            res["episodes"][tag] = {"stack": episode_block(st, ref, clean, fr[tag])}
            res["episodes"][tag]["layers"] = {c: episode_block(K.Stack([c], "max", 0.01).fit(ref), ref, clean, fr[tag]) for c in HEAD}
            for name, cols in (optional or {}).items():
                if all(c in ref.columns and c in fr[tag].columns for c in cols):
                    res["episodes"][tag].setdefault("optional", {})[name] = episode_block(K.Stack(cols, method, 0.01).fit(ref), ref, clean, fr[tag])
    # per-scan score table of the headline stack (for the freeze check and the long tables)
    res["_scores"] = {k: pd.DataFrame({"scan": v["scan"].to_numpy(), "drive": v["drive"].to_numpy(), "attack": v["attack"].to_numpy(), "stat": st.stat(v),
                                       "score": st.score(v), "alarm": st.alarm(v), **{c: v[c].to_numpy() for c in HEAD}})
                      for k, v in fr.items() if k != "ref"}
    return res, st
