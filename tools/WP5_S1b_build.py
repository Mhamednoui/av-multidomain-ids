"""WP5 S1b: Tampa deduplication, id linking (with controls), leakage of the old split, new time-block split.

Run from codes_v3/: python -I -u -W ignore tools/WP5_S1b_build.py
Inputs: D14 Tampa CSV (raw, through v2x.tampa_link), results/WP5/splits_tampa.json (old split, kept).
Outputs (results/WP5/): s1b_dedup_link.json (copies, tolerance rule, links, controls, old-split leakage),
splits_tampa_v2.json (new split), s1b_split_info.json (episodes, seeds tried, checks, counts), s1b_injection_summary.json.
Acceptance rule: notes/WP5_v2x.md, 'S1b ... acceptance rule' and its AMENDMENT (written before this ran).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True

import numpy as np
import pandas as pd

from common.config import SEED, results_dir
from common.splits import save_splits
from v2x import adapters, attacks, schema, splitting
from v2x import tampa_link as tl

OUT = results_dir("WP5")
WRONG_LINK_MAX = 0.05
SEED_TRIES = list(range(SEED, SEED + 30))
MIN_ELIGIBLE_EVAL, MIN_ATT_PER_TYPE = 3, 2
SHARE = {"train": (0.50, 0.70), "val": (0.10, 0.30), "test": (0.10, 0.30)}


def jdump(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))


def positive_control(u, rng, n_cuts=8, min_msgs=100):
    """Cut real tier-1 vehicles at random points with a hole of 0.5-5 s; does the continuity matcher re-link the halves
    among all other components? Counts: correct (unique mutual L->R), wrong (L end or R start uniquely linked to something else),
    ambiguous (L->R passes the gate but is not unique), missed (L->R fails the gate)."""
    starts, ends = tl.endpoints(u, "comp")
    sizes = u.groupby("comp").size()
    res = {"correct": 0, "wrong": 0, "ambiguous": 0, "missed": 0, "trials": 0}
    gaps = {"correct": [], "ambiguous": [], "missed": [], "wrong": []}
    for x in sorted(sizes.index[sizes >= min_msgs]):
        sx = u[u["comp"] == x].sort_values("t", kind="stable")
        n = len(sx)
        for _ in range(n_cuts):
            i = rng.randint(int(0.15 * n), int(0.85 * n))
            T, g = float(sx["t"].iloc[i]), float(rng.uniform(0.5, 5.0))
            left, right = sx[sx["t"] <= T], sx[sx["t"] >= T + g]
            if len(left) < 5 or len(right) < 5:
                continue
            e2 = {k: v for k, v in ends.items() if k != x}
            s2 = {k: v for k, v in starts.items() if k != x}
            s2["L"], e2["L"] = starts[x], tl._end_state(left.iloc[-1])
            s2["R"], e2["R"] = tl._end_state(right.iloc[0]), ends[x]
            cands = tl.candidate_table(e2, s2)
            uniq, _ = tl.mutual_unique(cands)
            true_pass = any(c["a"] == "L" and c["b"] == "R" for c in cands)
            wrong = any((c["a"] == "L" and c["b"] != "R") or (c["b"] == "R" and c["a"] != "L") for c in uniq)
            right_link = any(c["a"] == "L" and c["b"] == "R" for c in uniq)
            res["trials"] += 1
            k = "correct" if right_link else ("wrong" if wrong else ("ambiguous" if true_pass else "missed"))
            res[k] += 1
            gaps[k].append(g)
    link = res["correct"] + res["wrong"]
    res["recall"] = res["correct"] / max(res["trials"], 1)
    res["wrong_link_rate_of_accepted"] = res["wrong"] / max(link, 1)
    res["wrong_link_rate_of_trials"] = res["wrong"] / max(res["trials"], 1)
    res["mean_hole_s"] = {k: (float(np.mean(v)) if v else None) for k, v in gaps.items()}
    return res


def negative_control(u, rng, reps=30):
    """Same matcher with the msgCnt of every start shuffled (random 0..127): links that survive show what msgCnt contributes."""
    starts, ends = tl.endpoints(u, "comp")
    n_real = len(tl.mutual_unique(tl.candidate_table(ends, starts))[0])
    n_cand = len(tl.candidate_table(ends, starts))
    out = []
    for _ in range(reps):
        s2 = {k: dict(v, cnt=int(rng.randint(0, 128))) for k, v in starts.items()}
        c = tl.candidate_table(ends, s2)
        out.append((len(c), len(tl.mutual_unique(c)[0])))
    return {"unshuffled_candidates": n_cand, "unshuffled_unique_links": n_real,
            "shuffled_msgCnt_mean_candidates": float(np.mean([a for a, _ in out])),
            "shuffled_msgCnt_mean_unique_links": float(np.mean([b for _, b in out])),
            "shuffled_msgCnt_max_unique_links": int(max(b for _, b in out))}


def old_split_leakage(raw, u, comp, old):
    """How much the S1 split by coreData_id leaked."""
    part_of = {str(i): p for p, ids in old.items() for i in ids}
    r = raw.assign(part=raw["id"].astype(str).map(part_of))
    parts_per_msg = r.groupby("k")["part"].agg(lambda s: tuple(sorted(set(s))))
    multi = parts_per_msg.map(len) > 1
    # old-test unique messages (after the old id-level dedup): rows of test ids, one per (id, t)
    test_rows = r[r["part"] == "test"].drop_duplicates(["id", "t"])
    other = r[r["part"].isin(["train", "val"])].groupby("k").size()
    test_with_copy = test_rows["k"].isin(other.index)
    in_val = test_rows["k"].isin(r[r["part"] == "val"].groupby("k").size().index)
    # physical vehicles over the old parts
    comp_to_v = u.groupby("comp")["vlab"].first()
    idv = comp.map(comp_to_v)
    ids_part = pd.DataFrame({"id": comp.index.astype(str), "v": idv.to_numpy()})
    ids_part["part"] = ids_part["id"].map(part_of)
    vparts = ids_part.groupby("v")["part"].agg(lambda s: tuple(sorted(set(s))))
    spread = vparts.map(len) > 1
    cnt = r.drop_duplicates(["id", "t"]).groupby("id").size()
    ids_part["n"] = ids_part["id"].map(lambda i: int(cnt.get(int(i), 0)))
    ids_part["spread"] = ids_part["v"].map(spread)
    test_ids = ids_part[ids_part["part"] == "test"]
    return {"old_split_vehicles_ids": {p: len(v) for p, v in old.items()},
            "unique_messages_heard_under_ids_of_more_than_one_old_part": int(multi.sum()),
            "fraction_of_unique_messages": float(multi.mean()),
            "old_test_rows_(id,t)": int(len(test_rows)),
            "old_test_rows_with_a_bit_identical_copy_under_a_train_or_val_id": int(test_with_copy.sum()),
            "fraction_old_test_rows_with_copy_in_train_or_val": float(test_with_copy.mean()),
            "fraction_old_test_rows_with_copy_in_val": float(in_val.mean()),
            "physical_vehicles": int(len(vparts)),
            "physical_vehicles_with_ids_in_more_than_one_old_part": int(spread.sum()),
            "old_test_ids": int(len(test_ids)),
            "old_test_ids_whose_physical_vehicle_also_has_ids_in_train_or_val": int(test_ids["spread"].sum()),
            "fraction_old_test_ids_of_such_vehicles": float(test_ids["spread"].mean()),
            "old_test_row_share_of_such_vehicles": float(test_ids.loc[test_ids["spread"], "n"].sum() / max(test_ids["n"].sum(), 1))}


def split_candidates(t, vehicle_of):
    """Tries seeds in order (size criteria only). Returns (chosen split, info, tried)."""
    cnt = t.groupby("sender").size()
    total = cnt.sum()
    tried = []
    chosen = None
    for seed in SEED_TRIES:
        split, info = splitting.tampa_time_block_split(t, seed=seed, vehicle_of=vehicle_of)
        row = {"seed": seed, "parts": {}}
        ok = True
        for p, ids in split.items():
            c = cnt.loc[ids]
            elig = int((c >= 50).sum())
            share = float(c.sum() / total)
            n_att = int(round(0.5 * elig)) if elig else 0
            row["parts"][p] = {"passages": len(ids), "messages": int(c.sum()), "share": share,
                               "eligible_ge50": elig, "attackers_per_type": max(1, n_att) if elig else 0}
            lo, hi = SHARE[p]
            ok &= lo <= share <= hi
            if p != "train":
                ok &= elig >= MIN_ELIGIBLE_EVAL and n_att >= MIN_ATT_PER_TYPE
        row["criteria_met"] = bool(ok)
        tried.append(row)
        if ok and chosen is None:
            chosen = (split, info)
            break
    return chosen, tried


def main():
    raw = tl.read_raw(adapters.TAMPA_CSV)
    raw, u = tl.dedup(raw)
    comp, nc = tl.id_components(raw)
    log = {}
    log["copies"] = tl.copy_stats(raw)
    log["tolerance_rule"] = tl.tolerance_extra_merges(u)
    log["tier1"] = {"ids": int(raw["id"].nunique()), "components": nc,
                    "component_sizes_ids": {int(k): int(v) for k, v in pd.Series(comp).value_counts().value_counts().sort_index().items()},
                    "ids_per_rsu_max": int(raw.groupby("rsu")["id"].nunique().max()), "rsus": int(raw["rsu"].nunique())}
    u["lab"] = u["id"].map(comp).to_numpy()
    u["comp"] = u["lab"]
    # msgCnt rule check inside tier-1 components
    s = u.sort_values(["comp", "t"])
    dt = s.groupby("comp")["t"].diff()
    dc = (s["msgCnt"] - s.groupby("comp")["msgCnt"].shift()) % 128
    m = (dt > 0) & (dt < 12)
    err = ((dc - np.round(dt * tl.RATE_HZ) + 64) % 128 - 64).abs()[m]
    log["msgCnt_rule_inside_tier1"] = {"pairs": int(m.sum()), "within_1": float((err <= 1).mean()), "within_2": float((err <= 2).mean())}
    rng = np.random.RandomState(SEED)
    log["positive_control"] = positive_control(u, rng)
    log["negative_control_msgCnt"] = negative_control(u, rng)
    use_tier2 = log["positive_control"]["wrong_link_rate_of_accepted"] <= WRONG_LINK_MAX
    log["tier2_used"] = bool(use_tier2)
    links, amb = tl.link_continuity(u) if use_tier2 else ([], [])
    log["tier2_links"], log["ambiguous_candidates"] = links, amb
    u["vlab"] = u["lab"]
    u["passage"] = tl.passages(u).to_numpy().astype(int)
    log["linking_summary"] = {"ids": int(raw["id"].nunique()), "tier1_vehicles": nc, "physical_vehicles": int(u["vlab"].nunique()),
                              "passages": int(u.groupby(["vlab", "passage"]).ngroups), "silence_s": tl.SILENCE_S,
                              "n_tier2_links": len(links), "n_ambiguous_unlinked": len(amb),
                              "confidence": "tier 1 certain (bit-identical shared message); tier 2 high (unique mutual continuity, see controls); "
                                            "ambiguous pairs left unlinked"}
    old = json.loads((OUT / "splits_tampa.json").read_text())
    log["old_split_leakage"] = old_split_leakage(raw, u, comp, old)
    # the table every later step loads (must be what adapters.load_tampa returns)
    adapters._TAMPA_CACHE.clear()
    t = adapters.load_tampa(with_age=True, tier2=use_tier2)
    schema.validate(t)
    log["table"] = {"rows": int(len(t)), "passages": int(t["sender"].nunique()), "tracks": int(t["track"].nunique()),
                    "t_range_s": [float(t["t"].min()), float(t["t"].max())]}
    cnt = t.groupby("sender").size()
    log["table"]["eligible_ge50_passages"] = int((cnt >= 50).sum())
    vehicle_of = {}
    uu, _ = adapters.tampa_messages(tier2=use_tier2)
    for sdr, v in uu.groupby("sender")["vehicle"].first().items():
        vehicle_of[sdr] = v
    jdump("s1b_dedup_link.json", log)

    chosen, tried = split_candidates(t, vehicle_of)
    if chosen is None:
        jdump("s1b_split_info.json", {"criteria_met": False, "tried": tried})
        raise SystemExit("no seed met the size criteria: see s1b_split_info.json (report to the supervisor)")
    split, sinfo = chosen
    save_splits(split, OUT / "splits_tampa_v2.json")
    sinfo["tried_seeds"] = tried
    sinfo["gap_s_between_parts"] = splitting.min_gap_between_parts(t, split)
    sinfo["required_min_gap_s"] = 2 * splitting.GUARD_S
    vparts = {}
    for p, ids in split.items():
        for sdr in ids:
            vparts.setdefault(vehicle_of[sdr], set()).add(p)
    spread = {v: sorted(ps) for v, ps in vparts.items() if len(ps) > 1}
    # residual: a vehicle with passages in several parts (a different passage, >= 120 s apart)
    life = t.groupby("sender")["t"].agg(["min", "max"])
    res = {}
    for v in spread:
        sd = sorted(s for s in vehicle_of if vehicle_of[s] == v and s in life.index)
        res[v] = {"passages": {s: [float(life.loc[s, "min"]), float(life.loc[s, "max"]), int(cnt.loc[s])] for s in sd},
                  "parts": {s: next(p for p, ids in split.items() if s in ids) for s in sd}}
    sinfo["residual_vehicles_with_passages_in_several_parts"] = res
    sinfo["n_residual_vehicles"] = len(res)
    msg_in_res = sum(cnt.loc[s] for v in res for s in res[v]["passages"])
    sinfo["messages_in_residual_vehicle_passages"] = int(msg_in_res)
    sinfo["parts"] = {p: {"passages": len(ids), "messages": int(cnt.loc[ids].sum()), "eligible_ge50": int((cnt.loc[ids] >= 50).sum()),
                          "share": float(cnt.loc[ids].sum() / cnt.sum())} for p, ids in split.items()}
    sinfo["sender_overlap_between_parts"] = 0
    sinfo["heldout_attack_types_for_supervised_training"] = [6, 12, 17]
    inj = {}
    for p in ("train", "val", "test"):
        for aid in attacks.ATTACK_IDS:
            sc, att = attacks.build_scenario(t, split[p], aid)
            schema.validate(sc)
            inj.setdefault(p, {})[aid] = dict(name=schema.CLASS_NAMES[aid], n_attackers=len(att),
                                              n_labelled_attack=int((sc.label == aid).sum()), n_messages=int(len(sc)))
    sinfo["attackers_per_type_min"] = {p: min(v["n_attackers"] for v in inj[p].values()) for p in inj}
    sinfo["all_types_present_every_part"] = bool(all(v["n_labelled_attack"] > 0 for p in inj for v in inj[p].values()))
    sinfo["vehicle_of_passage"] = vehicle_of
    jdump("s1b_split_info.json", sinfo)
    jdump("s1b_injection_summary.json", inj)
    print("done; seed", sinfo["seed"], sinfo["parts"], "tier2 used", use_tier2)


if __name__ == "__main__":
    main()
