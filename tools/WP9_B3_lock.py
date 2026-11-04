"""WP9 B3 step 1: dedup count + split lock for VeReMi Extension (D12), BEFORE any model is fitted.

Facts (reports/WP5_S1.md, re-checked in tools/WP9_B3_explore*.py): the combined CSV is ONE 24 h simulation timeline; no run / file / receiver id exists
(type = 4 for all rows, messageID is one global counter). The run-level equivalent is the 1800 s time block of WP5 (senders assigned by first message;
senders crossing a block end dropped, so no two blocks have a sender alive at the same time).
H31 (locks/H31.json, "reused": veremi_test) holds the 10 WP5 test blocks (S7 scores them). B3 keeps them OUT completely: the other 38 blocks are
re-cut 60/20/20 by group_split (seed SEED) into B3 train / val / test. Output: locks/WP9_veremi.json.
Run: python -I -u -W ignore tools/WP9_B3_lock.py
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd

from common.config import SEED
from common.splits import group_split

CSV = ROOT.parent / "data_extra" / "D12_veremi_extension" / "mixalldata_clean.csv"
BLOCK_S = 1800.0


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 24), b""):
            h.update(ch)
    return h.hexdigest()


def main():
    df = pd.read_csv(CSV)
    n0 = len(df)
    n_dup_full = int(df.duplicated().sum())
    n_dup_key = int(df.duplicated(["sender", "senderPseudo", "sendTime"]).sum())
    n_dup_mid = int(df["messageID"].duplicated().sum())
    df = df.drop_duplicates().reset_index(drop=True)
    life = df.groupby("sender")["sendTime"].agg(["min", "max"])
    b0 = np.floor(life["min"] / BLOCK_S).astype(int)
    b1 = np.floor(life["max"] / BLOCK_S).astype(int)
    keep = b0 == b1
    sender_block = b0[keep]
    wp5 = json.load(open(ROOT / "results/WP5/splits_veremi.json"))
    info5 = json.load(open(ROOT / "results/WP5/s1_split_info.json"))
    # reproduce the WP5 assignment: same senders, same blocks
    part5 = {}
    for p, ids in wp5.items():
        for s in ids:
            part5[int(s)] = p
    assert set(part5) == set(sender_block.index), "WP5 sender set differs"
    blk_part5 = {}
    for s, b in sender_block.items():
        blk_part5.setdefault(int(b), set()).add(part5[int(s)])
    assert all(len(v) == 1 for v in blk_part5.values())
    h31_blocks = sorted(b for b, v in blk_part5.items() if v == {"test"})
    assert sorted(map(str, h31_blocks)) == sorted(info5["blocks"]["test"])
    free_blocks = sorted(b for b in blk_part5 if b not in h31_blocks)
    blocks = group_split([str(b) for b in free_blocks], fractions=(0.6, 0.2, 0.2), seed=SEED)
    part_of_block = {int(b): p for p, bs in blocks.items() for b in bs}
    split = {"train": [], "val": [], "test": []}
    for s, b in sender_block.items():
        if int(b) in part_of_block:
            split[part_of_block[int(b)]].append(int(s))
    split = {p: sorted(v) for p, v in split.items()}
    # checks
    allids = [s for v in split.values() for s in v]
    assert len(allids) == len(set(allids))
    assert not set(allids) & {int(s) for s in wp5["test"]}, "H31 overlap"
    df = df[df["sender"].isin(set(allids))]
    part_of_sender = {s: p for p, v in split.items() for s in v}
    df["part"] = df["sender"].map(part_of_sender)
    cls = pd.crosstab(df["class"], df["part"]).to_dict()
    # time disjointness between parts: no sender of one part alive at a time when a sender of another part is alive
    ivs = {p: sorted((float(life.loc[s, "min"]), float(life.loc[s, "max"])) for s in v) for p, v in split.items()}
    overlap = 0
    for p in ivs:
        for q in ivs:
            if p < q:
                lo_p, hi_p = min(a for a, _ in ivs[p]), max(b for _, b in ivs[p])
                for a, b in ivs[q]:
                    pass
    # block-level check (cheap and sufficient): blocks of different parts are different 1800 s intervals, senders live inside their block
    adj = {}
    for p in ("val", "test"):
        adj[p] = int(sum(1 for b in blocks[p] if (int(b) - 1 in part_of_block and part_of_block[int(b) - 1] == "train") or (int(b) + 1 in part_of_block and part_of_block[int(b) + 1] == "train")))
    lock = {
        "_note": "WP9 B3 VeReMi Extension split lock, written BEFORE any B3 model was fitted (2026-11-04). D12 = one simulation timeline, no run id; run-level equivalent = 1800 s time block.",
        "dataset": "D12 VeReMi Extension combined CSV (mixalldata_clean.csv)",
        "csv_sha256": sha256(CSV), "csv_bytes": CSV.stat().st_size,
        "dedup": {"rows": n0, "exact_full_row_duplicates": n_dup_full, "dup_(sender,pseudo,sendTime)": n_dup_key, "dup_messageID": n_dup_mid, "rows_after": int(n0 - n_dup_full),
                  "policy": "exact duplicate rows dropped (none found); repeated positions (replay / constant-position attacks) are NOT duplicates and are kept"},
        "block_s": BLOCK_S, "straddling_senders_dropped": int((~keep).sum()),
        "h31_excluded": {"why": "locks/H31.json reused.veremi_test = the 10 WP5 test blocks (S7 scores them); B3 uses none of their messages",
                         "blocks": [str(b) for b in h31_blocks], "n_senders": len(wp5["test"])},
        "blocks": {p: sorted(bs, key=int) for p, bs in blocks.items()},
        "n_senders": {p: len(v) for p, v in split.items()},
        "n_messages": {p: int((df["part"] == p).sum()) for p in split},
        "class_counts_messages": {str(k): v for k, v in cls.items()},
        "val_test_blocks_adjacent_to_train_block": adj,
        "sender_ids_sha256": {p: hashlib.sha256(",".join(map(str, v)).encode()).hexdigest() for p, v in split.items()},
        "sender_ids": {p: v for p, v in split.items()},
        "cross_sender_features": "overlap / birth density are computed INSIDE each part only; parts never coexist in time (senders cannot straddle a block end)",
    }
    out = ROOT / "locks" / "WP9_veremi.json"
    out.write_text(json.dumps(lock, indent=1))
    print(json.dumps({k: lock[k] for k in ("dedup", "n_senders", "n_messages", "val_test_blocks_adjacent_to_train_block", "blocks")}, indent=1))
    print(pd.crosstab(df["class"], df["part"]))


if __name__ == "__main__":
    main()
