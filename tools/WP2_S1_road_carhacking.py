"""WP2 S1: ROAD and Car-Hacking through the adapters; compare with v2; write splits.

Outputs (results/WP2/): s1_road.json, s1_carhacking.json, splits_road.json, splits_carhacking.json.
v2 reference numbers are parsed from ../codes_v2/results/road_external.log and can_train.log
(read only). Run: python -I -W ignore tools/WP2_S1_road_carhacking.py
"""
import ast
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.dont_write_bytecode = True
from can.adapters import (CARHACKING_FILES, load_carhacking, load_road, load_road_signals, road_captures,
                          road_label_check)
from can.frames import validate_frame
from can.splits import block_index, carhacking_blocks, road_split
from common.config import ROOT, results_dir

V2 = ROOT.parent / "codes_v2" / "results"
OUT = results_dir("WP2")


def v2_road_reference():
    cap, check = {}, None
    for line in open(V2 / "road_external.log", encoding="utf-8"):
        m = re.match(r"\s+(\S+)\s+(train|val|test)\s+([\d,]+) frames, injected\s+([\d,]+)", line)
        if m:
            cap[m.group(1)] = {"part": m.group(2), "frames": int(m.group(3).replace(",", "")),
                               "injected": int(m.group(4).replace(",", ""))}
        if line.startswith("label check"):
            check = ast.literal_eval(line.split("): ", 1)[1])
    return cap, check


def v2_carhacking_reference():
    ref = {}
    txt = open(V2 / "can_train.log", encoding="utf-8").read()
    for m in re.finditer(r"^(DoS|Fuzzy|RPM|Gear)\s+([\d,]+) frames, injected\s+([\d,]+)", txt, re.M):
        ref[m.group(1)] = {"frames": int(m.group(2).replace(",", "")), "injected": int(m.group(3).replace(",", ""))}
    cc = re.search(r"class counts\s+train \[([\d ]+)\]\s+val \[([\d ]+)\]\s+test \[([\d ]+)\]", txt)
    ref["class_counts"] = {k: [int(x) for x in cc.group(i + 1).split()] for i, k in enumerate(("train", "val", "test"))}
    return ref


def road():
    caps = road_captures()
    ref, ref_check = v2_road_reference()
    res, checks, mism = {}, {}, []
    for r in caps.itertuples():
        if not r.usable:
            continue
        t0 = time.time()
        d = load_road(r.name, caps)
        st = validate_frame(d)
        res[r.name] = {"family": r.family, "kind": r.kind, "part": r.part, "frames": st["frames"],
                       "injected": st["injected"], "negative_dt": st["negative_dt"],
                       "attack_names": sorted(d["attack"].astype(str).unique().tolist()),
                       "v2": ref.get(r.name)}
        v = ref.get(r.name)
        ok = v is not None and v["frames"] == st["frames"] and v["injected"] == st["injected"] and v["part"] == r.part
        res[r.name]["matches_v2"] = bool(ok)
        if not ok:
            mism.append(r.name)
        c = road_label_check(r.name, d)
        if c:
            checks[r.name] = c
        print(f"{r.name:45s} {r.part:5s} {st['frames']:>9,} inj {st['injected']:>6,} v2 match {ok} ({time.time() - t0:.1f}s)",
              flush=True)
    # decoded signals: rows and ID overlap with the raw log for a few captures
    sig = {}
    for name in ["ambient_dyno_reverse", "ambient_dyno_drive_winter", "max_speedometer_attack_3_masquerade",
                 "reverse_light_on_attack_1_masquerade"]:
        d = load_road(name, caps)
        s = load_road_signals(name)
        sig[name] = {"frames_log": len(d), "rows_signals": len(s), "ids_log": int(d["id"].nunique()),
                     "ids_signals": int(s["ID"].nunique()), "signal_cols": [c for c in s.columns if c.startswith("Signal_")][-1],
                     "label_sum": int(s["Label"].sum())}
        print("signals", name, sig[name], flush=True)
    check_diff = {n: {"ours_minus_road": v["ours"] - v["road_signal_labels"]} for n, v in checks.items()}
    out = {"captures": res, "n_captures": len(res), "n_match_v2": sum(v["matches_v2"] for v in res.values()),
           "mismatching": mism, "label_check": checks, "label_check_v2": ref_check,
           "label_check_same_as_v2": checks == ref_check,
           "label_check_max_abs_diff": max(abs(v["ours_minus_road"]) for v in check_diff.values()),
           "signals": sig, "accelerator_unused": caps[~caps["usable"]]["name"].tolist()}
    json.dump(out, open(OUT / "s1_road.json", "w"), indent=1)
    sp = road_split(caps)
    json.dump({"rule": "v2: attack instance 1 train, 2 val, 3 test; coolant capture test; masquerade with its original; "
                       "ambient test / val lists from v2; accelerator captures unused (no injected frames)",
               "splits": sp, "counts": {k: len(v) for k, v in sp.items()}}, open(OUT / "splits_road.json", "w"), indent=1)
    print("ROAD", out["n_match_v2"], "/", out["n_captures"], "match v2; label check same as v2:",
          out["label_check_same_as_v2"], "max diff", out["label_check_max_abs_diff"])


def carhacking():
    ref = v2_carhacking_reference()
    res, labels = {}, {}
    for name, fn in CARHACKING_FILES.items():
        d = load_carhacking(name)
        st = validate_frame(d)
        nlines = sum(1 for _ in open(Path(ROOT.parent / "codes" / "data" / fn), "rb"))
        res[name] = {"frames": st["frames"], "raw_lines": nlines, "injected": st["injected"],
                     "negative_dt": st["negative_dt"], "v2": ref.get(name),
                     "matches_v2": bool(ref[name] == {"frames": st["frames"], "injected": st["injected"]}),
                     "first_attack_row_frac": float(np.flatnonzero(d["label"].to_numpy())[0] / len(d)),
                     "last_attack_row_frac": float(np.flatnonzero(d["label"].to_numpy())[-1] / len(d))}
        labels[name] = d["label"].to_numpy()
        print(name, res[name], flush=True)
    blocks = carhacking_blocks(labels)
    classes = ["Normal"] + list(CARHACKING_FILES)
    counts = {p: [0] * 5 for p in ("train", "val", "test")}
    for name, lab in labels.items():
        part = np.array(blocks[name], dtype=object)[block_index(len(lab))]
        for p in counts:
            m = part == p
            counts[p][0] += int(((lab == 0) & m).sum())
            counts[p][classes.index(name)] += int(((lab == 1) & m).sum())
    out = {"files": res, "block_class_counts": counts, "classes": classes, "v2_class_counts": ref["class_counts"],
           "val_test_and_train_attacks_same_as_v2": all(
               counts[p] == ref["class_counts"][p] for p in ("val", "test")) and counts["train"][1:] == ref["class_counts"]["train"][1:],
           "train_normal_ours": counts["train"][0], "train_normal_v2_after_25pct_subsample": ref["class_counts"]["train"][0],
           "train_normal_ours_x_0.25": counts["train"][0] * 0.25}
    json.dump(out, open(OUT / "s1_carhacking.json", "w"), indent=1)
    json.dump({"rule": "v2 block_split: 100 interleaved blocks per file; attack blocks and normal blocks each cut 70/15/15; "
                       "one default_rng(42) used over the files in order DoS, Fuzzy, RPM, Gear",
               "n_blocks": 100, "blocks": blocks}, open(OUT / "splits_carhacking.json", "w"), indent=1)
    print("Car-Hacking val/test/train-attack counts same as v2:", out["val_test_and_train_attacks_same_as_v2"])
    print(counts, ref["class_counts"])


if __name__ == "__main__":
    road()
    carhacking()
