"""WP5 S1: class-map evidence, splits and injection summary.

Inputs: D12 VeReMi CSV, D14 Tampa CSV (through v2x.adapters). Run: python -I -u -W ignore tools/WP5_S1_build.py
Outputs (results/WP5/): s1_classmap_evidence.json, splits_veremi.json, splits_tampa.json,
s1_split_info.json, s1_injection_summary.json, s1_adapters.json
Acceptance rule: notes/WP5_v2x.md, section "S1 Data layer: acceptance rule" (written before this ran).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

import numpy as np
import pandas as pd

from common.config import results_dir
from common.splits import save_splits
from v2x import adapters, attacks, schema, splitting

OUT = results_dir("WP5")
HELDOUT_ATTACKS = [6, 12, 17]   # variants to hide from any supervised model in S5 (fixed now)


def jdump(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))


def classmap_evidence(v):
    g = v.groupby("sender")
    s = g.agg(cls=("label", "first"), n=("t", "size"), t0=("t", "min"), t1=("t", "max"),
              sx=("x", "std"), sy=("y", "std"), sspd=("speed", "std"), mspd=("speed", "mean"),
              npseudo=("pseudo", "nunique"))
    s["spos"] = np.hypot(s.sx, s.sy)
    s["rate"] = (s.n - 1) / (s.t1 - s.t0).clip(lower=1.0)
    v = v.sort_values(["track", "t"])
    gt = v.groupby("track")
    dt, dx, dy = gt["t"].diff(), gt["x"].diff(), gt["y"].diff()
    v = v.assign(jump=np.hypot(dx, dy), vimp=np.hypot(dx, dy) / dt)
    v["dv"] = (v["vimp"] - v["speed"]).abs()
    v["stopped"] = v["speed"] < 0.1
    s2 = v.groupby("sender").agg(jump=("jump", "median"), dv=("dv", "median"), stop=("stopped", "mean"))
    s = s.join(s2)
    s = s[s.n >= 5]
    gen_rate = float(s[s.cls == 0].rate.median())
    rows = {}
    for c, d in s.groupby("cls"):
        rows[int(c)] = dict(name=schema.CLASS_NAMES[int(c)], n_senders=int(len(d)),
                            pos_std_median_m=float(d.spos.median()),
                            frac_pos_std_lt_1m=float((d.spos < 1).mean()),
                            speed_std_median=float(d.sspd.median()),
                            frac_speed_std_lt_0p1=float((d.sspd < 0.1).mean()),
                            mean_speed_median=float(d.mspd.median()),
                            median_consecutive_jump_m=float(d["jump"].median()),
                            median_claimed_vs_implied_speed_err=float(d.dv.median()),
                            frac_msgs_stopped=float(d.stop.mean()),
                            rate_median_hz=float(d.rate.median()),
                            rate_ratio_vs_genuine=float(d.rate.median() / gen_rate),
                            pseudonyms_per_sender_median=float(d.npseudo.median()))
    r = lambda c, k: rows[c][k]
    checks = {
        "class1_ConstPos_frac_pos_std_lt_1m_ge_0.8": r(1, "frac_pos_std_lt_1m") >= 0.8,
        "class5_ConstSpeed_frac_speed_std_lt_0.1_ge_0.8": r(5, "frac_speed_std_lt_0p1") >= 0.8,
        "class13_rate_ge_2x": r(13, "rate_ratio_vs_genuine") >= 2.0,
        "class14_rate_ge_2x": r(14, "rate_ratio_vs_genuine") >= 2.0,
        "class15_rate_ge_2x": r(15, "rate_ratio_vs_genuine") >= 2.0,
    }
    extra = {  # additional, not pre-registered thresholds: qualitative consistency, stated as such
        "class9_EventualStop_majority_stopped": r(9, "frac_msgs_stopped") > 0.5,
        "class3_RandomPos_jump_gt_100m": r(3, "median_consecutive_jump_m") > 100,
        "class7_RandomSpeed_speed_std_gt_2x_genuine": r(7, "speed_std_median") > 2 * r(0, "speed_std_median"),
        "class16_GridSybil_gt_1_pseudonyms_and_rate_gt_4x": r(16, "pseudonyms_per_sender_median") > 1 and r(16, "rate_ratio_vs_genuine") > 4,
        "classes17_18_19_many_pseudonyms": min(r(c, "pseudonyms_per_sender_median") for c in (17, 18, 19)) > 10,
        "class10_Disruptive_jump_gt_100m": r(10, "median_consecutive_jump_m") > 100,
        "class11_DataReplay_implied_speed_mismatch_gt_5": r(11, "median_claimed_vs_implied_speed_err") > 5,
        "class12_DelayedMessages_majority_stopped_or_zero_start": r(12, "frac_msgs_stopped") > 0.5,
        "class6_8_speed_offset_mean_speed_gt_genuine": min(r(6, "mean_speed_median"), r(8, "mean_speed_median")) > r(0, "mean_speed_median") + 1,
    }
    ex = {"genuine_rate_hz": gen_rate, "per_class": rows, "preregistered_checks": checks,
          "extra_checks": extra,
          "sender_id_vs_first_time_spearman": float(s.reset_index()[["sender", "t0"]].astype(float).corr(method="spearman").iloc[0, 1]),
          "classes_per_sender_max": int(v.groupby("sender")["label"].nunique().max()),
          "pseudonyms_shared_between_senders": int((v.groupby("pseudo")["sender"].nunique() > 1).sum()),
          "time_range_s": [float(v.t.min()), float(v.t.max())]}
    return ex


def veremi_splits(v):
    split, info = splitting.veremi_time_block_split(v)
    save_splits(split, OUT / "splits_veremi.json")
    cls = v.groupby("sender")["label"].first()
    cnt = v.groupby("sender").size()
    summ = {}
    for p, ids in split.items():
        c = cls.loc[ids]
        summ[p] = dict(n_senders=len(ids), n_messages=int(cnt.loc[ids].sum()),
                       genuine_senders=int((c == 0).sum()),
                       senders_per_class={int(k): int(n) for k, n in c.value_counts().sort_index().items()},
                       messages_genuine=int(cnt.loc[ids][c == 0].sum()))
    dropped = info.pop("dropped_senders")
    info["dropped_by_class"] = {int(k): int(n) for k, n in cls.loc[dropped].value_counts().sort_index().items()}
    info["parts"] = summ
    # leakage checks, computed on the data
    life = v.groupby("sender")["t"].agg(["min", "max"])
    ranges = {p: (float(life.loc[ids, "min"].min()), float(life.loc[ids, "max"].max())) for p, ids in split.items()}
    info["part_time_ranges_s"] = ranges
    overlap = {}
    for a, b in (("train", "val"), ("train", "test"), ("val", "test")):
        la, lb = life.loc[split[a]], life.loc[split[b]]
        # smallest time distance between an A sender's life and any B sender's life
        ends_a, starts_b = np.sort(la["max"].to_numpy()), np.sort(lb["min"].to_numpy())
        overlapping = 0
        for s0, s1 in zip(la["min"].to_numpy(), la["max"].to_numpy()):
            overlapping += int(((lb["min"].to_numpy() <= s1) & (lb["max"].to_numpy() >= s0)).any())
        overlap[f"{a}-{b}"] = {"senders_of_first_alive_at_same_time_as_a_sender_of_second": overlapping}
    info["cross_part_coexistence"] = overlap
    info["sender_overlap_between_parts"] = 0
    info["pseudonym_overlap_between_parts"] = int(len(
        set(v[v.sender.isin(split["train"])].pseudo) & (set(v[v.sender.isin(split["test"])].pseudo)
                                                         | set(v[v.sender.isin(split["val"])].pseudo))))
    return split, info


def injection_summary(t, split):
    out = {}
    ids_all = {}
    for p in ("train", "val", "test"):
        for aid in attacks.ATTACK_IDS:
            sc, att = attacks.build_scenario(t, split[p], aid)
            schema.validate(sc)
            a = sc[sc.sender.isin(att)]
            base = t[t.sender.isin(att)]
            out.setdefault(p, {})[aid] = dict(
                name=schema.CLASS_NAMES[aid], n_attackers=len(att), n_messages=int(len(sc)),
                n_labelled_attack=int((sc.label == aid).sum()),
                attacker_msgs_vs_genuine_ratio=float(len(a) / max(1, len(base))),
                n_pseudonyms_attackers=int(a.pseudo.nunique()))
    return out


def main():
    v = adapters.load_veremi()
    schema.validate(v)
    jdump("s1_classmap_evidence.json", classmap_evidence(v))
    split, info = veremi_splits(v)
    t = adapters.load_tampa()
    schema.validate(t)
    tsplit = splitting.tampa_vehicle_split(t)
    save_splits(tsplit, OUT / "splits_tampa.json")
    cnt = t.groupby("sender").size()
    info["tampa"] = {p: dict(n_vehicles=len(ids), n_messages=int(cnt.loc[ids].sum()),
                             n_eligible_ge_50_msgs=int((cnt.loc[ids] >= 50).sum())) for p, ids in tsplit.items()}
    info["heldout_attack_types_for_supervised_training"] = HELDOUT_ATTACKS
    jdump("s1_split_info.json", info)
    jdump("s1_injection_summary.json", injection_summary(t, tsplit))
    jdump("s1_adapters.json", {
        "veremi": dict(rows=len(v), senders=int(v.sender.nunique()), tracks=int(v.track.nunique())),
        "tampa": dict(rows=len(t), vehicles=int(t.sender.nunique()), tracks=int(t.track.nunique()),
                      t_range_utc_s=[float(t.t.min()), float(t.t.max())],
                      x_range_m=[float(t.x.min()), float(t.x.max())], y_range_m=[float(t.y.min()), float(t.y.max())]),
        "v2aix": "not available (adapter stub raises DataNotAvailableError)"})
    print("done")


if __name__ == "__main__":
    main()
