"""WP3 S7 analysis of a score store (frames with raw_<layer> columns, see WP3_S7_stack.py): single layers, stacks with a label-free
combiner, "adds beyond physics" paired bootstrap, persistent episodes. A pure function of the frames (reads no raw data), so it can be
exercised on the validation frames before the one verdict run.
frames: dict with 'ref' (clean out-of-fold reference), 'clean' (clean scans to report FA on), 'att' (attacked scans), optional 'ep'."""
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from lidar import learned_eval as LE
from lidar.sequence import EPISODE_SCANS, rolling_logodds

PHYSICS = ["raw_L1", "raw_L2a", "raw_L2c", "raw_L2d"]
STACKS = {"physics": PHYSICS, "physics+L3": PHYSICS + ["raw_L3"], "physics+L4": PHYSICS + ["raw_L4"], "physics+L3+L4": PHYSICS + ["raw_L3", "raw_L4"]}
EXTRA = {"physics+L4_v2 (comparison)": PHYSICS + ["raw_L4_V2"], "physics+L4_nophantom (comparison)": PHYSICS + ["raw_L4_NOPHANTOM"]}
OTHER = "noisy_or"


def layer_auc(clean_raw, att, col):
    out = {}
    for a, g in att.groupby("attack"):
        s = np.r_[clean_raw, g[col].to_numpy()]
        out[a] = float(roc_auc_score(np.r_[np.zeros(len(clean_raw)), np.ones(len(g))], s))
    return out


def episodes(ref, clean, ep, cols, method, sc_ref):
    """Episode detection within 3 s for one layer / stack. Statistic threshold = 99th percentile of the rolling log-odds over clean out-of-fold
    windows of the reference; false-episode rate on non-overlapping clean windows of the `clean` scans."""
    sc_clean, _ = LE.stack_scores(ref, clean, cols, method)
    sc_ep, _ = LE.stack_scores(ref, ep, cols, method)
    cal = lambda s: LE.ecdf_rank(sc_ref, s)  # noqa
    r = ref.assign(cal=cal(sc_ref)).sort_values(["drive", "idx"])
    thr = LE.episode_stat_threshold({d: g.cal.to_numpy() for d, g in r.groupby("drive")})
    c = clean.assign(cal=cal(sc_clean)).sort_values(["drive", "idx"])
    wins = LE.clean_windows({d: g.cal.to_numpy() for d, g in c.groupby("drive")}, EPISODE_SCANS)
    fer = float(np.mean([(rolling_logodds(w) >= thr).any() for w in wins]))
    thr_alarm = LE.threshold(cal(sc_ref), 0.01)
    return {"stat_threshold": thr, "false_episode_rate": fer, "n_clean_windows": len(wins),
            "kinds": LE.episode_table(ep, cal(sc_ep), thr, thr_alarm)}


def analyse(fr, combiner):
    ref, clean, att, ep = fr["ref"], fr["clean"], fr["att"], fr.get("ep")
    layers = [c for c in ref.columns if c.startswith("raw_")]
    other = "max" if combiner == OTHER else OTHER
    res = {"combiner": combiner, "n_ref": int(len(ref)), "n_clean": int(len(clean)), "n_att": att.attack.value_counts().to_dict(), "layers": {}, "stacks": {},
           "adds": {}}
    lstore = {}
    for c in layers:
        r = LE.evaluate_stack(ref, clean, att, [c], "max")
        lstore[c] = r
        res["layers"][c] = {"fa": r["fa"], "fa_per_drive": r["fa_per_drive"], "fa_ref_lodo": r["fa_ref_lodo"], "det": r["det"],
                            "auc": layer_auc(clean[c].to_numpy(), att, c)}
        if ep is not None:
            res["layers"][c]["episodes"] = episodes(ref, clean, ep, [c], "max", r["ref_scores"])
    store = {}
    stacks = {k: v for k, v in {**STACKS, **EXTRA}.items() if all(c in ref.columns for c in v)}
    for name, cols in stacks.items():
        for method in (combiner, other):
            r = LE.evaluate_stack(ref, clean, att, cols, method)
            store[(name, method)] = r
            entry = {k: v for k, v in r.items() if k not in ("alarm", "ref_scores")}
            entry["mean_phys"] = float(np.mean([r["det"][a] for a in LE.PHYS]))
            if method == combiner and ep is not None:
                entry["episodes"] = episodes(ref, clean, ep, cols, method, r["ref_scores"])
            res["stacks"][f"{name}/{method}"] = entry
    base = store[("physics", combiner)]
    for name in stacks:
        if name == "physics":
            continue
        r = store[(name, combiner)]
        d = {}
        for a in LE.PHYS + LE.CMP:
            k = (att.attack == a).to_numpy()
            m, lo, hi = LE.paired_bootstrap(base["alarm"][k], r["alarm"][k])
            d[a] = {"physics": float(base["alarm"][k].mean()), "with_X": float(r["alarm"][k].mean()), "diff": m, "ci95": [lo, hi]}
        gain = [a for a in LE.PHYS if d[a]["diff"] >= 0.03 and d[a]["ci95"][0] > 0]
        res["adds"][name] = {"per_attack": d, "attacks_with_gain": gain, "fa": r["fa"], "adds": bool(gain and r["fa"] <= 0.025)}
    res["vs_best_physics_layer"] = {}
    for x in [c for c in layers if c not in PHYSICS]:
        d = {}
        for a in LE.PHYS + LE.CMP:
            k = (att.attack == a).to_numpy()
            best = max(PHYSICS, key=lambda c: lstore[c]["alarm"][k].mean())
            m, lo, hi = LE.paired_bootstrap(lstore[best]["alarm"][k], lstore[x]["alarm"][k])
            d[a] = {"best_physics_layer": best, "best_physics": float(lstore[best]["alarm"][k].mean()), "X_alone": float(lstore[x]["alarm"][k].mean()),
                    "diff": m, "ci95": [lo, hi]}
        res["vs_best_physics_layer"][x] = d
    return res
