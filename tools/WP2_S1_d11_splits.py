"""WP2 S1: D11 hash groups, vehicle fingerprint check, per-set splits.

Reads results/WP2/s1_d11_scan.json (tools/WP2_S1_d11_scan.py). Writes
results/WP2/splits_d11.json, s1_d11_vehicle_check.json, s1_d11_dedup.json, s1_d11_acceptance.json.
Run: python -I -W ignore tools/WP2_S1_d11_splits.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.dont_write_bytecode = True
from can.adapters import d11_file_table
from can.splits import check_d11_split, d11_split
from common.config import results_dir

OUT = results_dir("WP2")


def components(items, adj):
    comp, seen = [], set()
    for a in items:
        if a in seen:
            continue
        stack, c = [a], []
        seen.add(a)
        while stack:
            x = stack.pop()
            c.append(x)
            for y in adj[x]:
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        comp.append(sorted(c))
    return comp


def vehicle_check(ft, scan):
    """Cluster files by the Jaccard similarity of their ID sets (files with random IDs excluded),
    then compare the clusters with the README vehicle of each file."""
    ids = {s["capture"]: set(s["id_set"]) for s in scan}
    use = [c for c in ft["capture"] if "fuzzing" not in c]
    adj = {c: [] for c in use}
    for i, a in enumerate(use):
        for b in use[i + 1:]:
            j = len(ids[a] & ids[b]) / len(ids[a] | ids[b])
            if j >= 0.8:
                adj[a].append(b)
                adj[b].append(a)
    comps = components(use, adj)
    readme = dict(zip(ft["capture"], ft["vehicle_readme"]))
    out = []
    for c in comps:
        names = defaultdict(int)
        for x in c:
            names[readme[x]] += 1
        sets = sorted({x.split("/")[0] + "/" + ("train" if "train" in x else x.split("/")[1][:7]) for x in c})
        common_ids = sorted(set.intersection(*[ids[x] for x in c]))
        out.append({"n_files": len(c), "readme_vehicle_counts": dict(names), "n_common_ids": len(common_ids),
                    "subsets": sets, "example": c[:2]})
    return sorted(out, key=lambda r: -r["n_files"]), sorted(comps, key=lambda c: -len(c))


def vehicle_table(ft, scan, clusters_full, hashes):
    """Per-file vehicle: ID-fingerprint cluster (main clusters named by their README majority),
    else the vehicle of a byte-identical copy that is clustered, else the majority fingerprint
    vehicle of the same (set, subset), else README (set-level). Source is recorded per file."""
    readme = dict(zip(ft["capture"], ft["vehicle_readme"]))
    main = [c for c in clusters_full if len(c) >= 20]
    fp = {}
    for c in main:
        votes = defaultdict(int)
        for x in c:
            votes[readme[x]] += 1
        name = max(votes, key=votes.get)
        for x in c:
            fp[x] = name
    by_hash = defaultdict(list)
    for c, h in hashes.items():
        by_hash[h].append(c)
    sub = lambda c: tuple(c.split("/")[:2])
    sub_votes = defaultdict(lambda: defaultdict(int))
    for c, v in fp.items():
        sub_votes[sub(c)][v] += 1
    out = {}
    for c in ft["capture"]:
        if c in fp:
            v, src = fp[c], "id-fingerprint"
        else:
            cp = [x for x in by_hash[hashes[c]] if x != c and x in fp]
            if cp:
                v, src = fp[cp[0]], "byte-identical copy of " + cp[0]
            elif sub_votes[sub(c)]:
                vv = sub_votes[sub(c)]
                v, src = max(vv, key=vv.get), "majority of its subset"
            else:
                v, src = readme[c], "README set-level only"
        out[c] = {"vehicle": v, "source": src, "readme": readme[c], "agrees_with_readme": v == readme[c]}
    return out


def main():
    ft = d11_file_table()
    scan = json.load(open(OUT / "s1_d11_scan.json"))
    hashes = {s["capture"]: s["sha256"] for s in scan}
    groups = defaultdict(list)
    for c, h in hashes.items():
        groups[h].append(c)
    dup = [sorted(v) for v in groups.values() if len(v) > 1]
    s0 = json.load(open(OUT / "s0_duplicates.json"))
    s0_pairs = sorted(sorted(x[:-4] for x in p) for p in s0["dup_groups"])
    dedup = {"distinct": len(groups), "n_files": len(hashes), "dup_groups": sorted(dup),
             "same_as_s0": sorted(dup) == s0_pairs and s0["distinct"] == len(groups)}
    json.dump(dedup, open(OUT / "s1_d11_dedup.json", "w"), indent=1)

    clusters, comps = vehicle_check(ft, scan)
    vt = vehicle_table(ft, scan, comps, hashes)
    json.dump(vt, open(OUT / "s1_d11_vehicles.json", "w"), indent=1)
    disagree = {c: v for c, v in vt.items() if not v["agrees_with_readme"]}
    json.dump({"method": "connected components of Jaccard(ID set) >= 0.8 over non-fuzzing files",
               "clusters": clusters}, open(OUT / "s1_d11_vehicle_check.json", "w"), indent=1)

    sp = d11_split(ft, hashes)
    check_d11_split(sp, hashes)
    json.dump({"rule": "per set: train_01 minus val hold-out (highest-numbered capture of each attack family "
                       "with >= 2 captures) = train; hold-out = val; test_01..04 as D11; byte-identical files "
                       "(sha256) kept once per set with precedence train > val > test_01 > ... > test_04; "
                       "vehicles: README set-level mapping (see s1_d11_vehicle_check.json for contradictions)",
               "splits": sp}, open(OUT / "splits_d11.json", "w"), indent=1)

    # acceptance vs S0
    s0inv = {f["path"][:-4]: f for f in json.load(open(OUT / "s0_inventory.json"))["files"]}
    bad = []
    for s in scan:
        f = s0inv[s["capture"]]
        if f["rows"] != s["rows"] or f["labels"].get("1", 0) != s["labels"]["1"] or f["labels"].get("0", 0) != s["labels"]["0"]:
            bad.append(s["capture"])
    n_inv = {s["capture"]: s["inversions"] for s in scan}
    s0_nonmono = sum(1 for f in s0inv.values() if not f["monotonic"])
    inv_files = [c for c, v in n_inv.items() if v > 0]
    per_attack = defaultdict(int)
    for s in scan:
        fam = s["capture"].rsplit("/", 1)[1].rsplit("-", 1)[0]
        per_attack[fam] += s["labels"]["1"]
    # counts after dedup (distinct files)
    distinct_caps = [v[0] for v in groups.values()]
    per_attack_distinct = defaultdict(int)
    for c in distinct_caps:
        per_attack_distinct[c.rsplit("/", 1)[1].rsplit("-", 1)[0]] += next(s for s in scan if s["capture"] == c)["labels"]["1"]
    summary = {
        "files": len(scan), "rows_total": sum(s["rows"] for s in scan),
        "rows_label1_total": sum(s["labels"]["1"] for s in scan),
        "rows_and_labels_match_s0_all_files": not bad, "mismatching_files": bad,
        "roundtrip_ok_all": all(s["roundtrip_ok"] for s in scan),
        "files_with_whitespace_in_data_field": [s["capture"] for s in scan if s["had_whitespace"]],
        "dlc_hist_total": {k: int(v) for k, v in sorted(
            defaultdict(int, {k: sum(s["dlc_hist"].get(k, 0) for s in scan) for s in scan for k in s["dlc_hist"]}).items())},
        "files_with_inversions": len(inv_files), "s0_non_monotonic_files": s0_nonmono,
        "inversions_total": sum(n_inv.values()),
        "inv_pairs_involving_attack": sum(s["inv_pairs_involving_attack"] for s in scan),
        "inv_pairs_with_label_change": sum(s["inv_pairs_with_label_change"] for s in scan),
        "inv_pairs_same_id": sum(s["inv_pairs_same_id"] for s in scan),
        "min_dt_all_s": min(s["min_dt"] for s in scan),
        "sort_would_move_frames": sum(s["sort_moves_frames"] for s in scan),
        "sort_would_change_label_sequence_at": sum(s["sort_changes_label_seq"] for s in scan),
        "sort_would_change_id_sequence_at": sum(s["sort_changes_id_seq"] for s in scan),
        "max_displacement_if_sorted": max(s["max_displacement_if_sorted"] for s in scan),
        "label1_per_attack_all_files": dict(sorted(per_attack.items())),
        "label1_per_attack_distinct_files": dict(sorted(per_attack_distinct.items())),
        "dedup": {"distinct": dedup["distinct"], "dup_groups": len(dup), "same_as_s0": dedup["same_as_s0"]},
        "vehicle_sources": {k: sum(1 for v in vt.values() if v["source"].startswith(k))
                            for k in ("id-fingerprint", "byte-identical copy", "majority of its subset", "README set-level only")},
        "vehicle_files_disagreeing_with_readme": len(disagree),
        "vehicle_disagreeing_subsets": sorted({"/".join(c.split("/")[:2]) + " README=" + v["readme"] + " data=" + v["vehicle"]
                                               for c, v in disagree.items()}),
        "split_counts": {s: {p: len(v) for p, v in parts.items()} for s, parts in sp.items()},
        "t_first_all_equal_epoch_offset_0": all(s["t_first"] == 0.0 for s in scan),
    }
    json.dump(summary, open(OUT / "s1_d11_acceptance.json", "w"), indent=1)
    print(json.dumps(summary, indent=1))
    print("vehicle clusters:")
    for c in clusters:
        print(c["n_files"], c["readme_vehicle_counts"], c["n_common_ids"], c["subsets"])


if __name__ == "__main__":
    main()
