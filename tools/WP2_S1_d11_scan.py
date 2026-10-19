"""WP2 S1: scan all 236 D11 files through the adapter; write results/WP2/s1_d11_scan.json.

Per file: sha256 of the bytes, rows, label counts, dlc histogram, ID set, byte round-trip check
(re-encoded bytes == data_field, whitespace stripped, upper-case), timestamp order statistics
(inversions, and what re-sorting would do to the labels). Run: python -I -W ignore tools/WP2_S1_d11_scan.py
"""
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.dont_write_bytecode = True
from can.adapters import d11_file_table, d11_raw_hex, load_d11
from can.frames import BYTE_COLS, bytes_to_hex, validate_frame
from common.config import DATA_EXTRA, results_dir

CACHE = DATA_EXTRA / "D11_can-train-and-test" / "s1_scan_cache"   # derived, not committed
CACHE.mkdir(exist_ok=True)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def scan(row) -> dict:
    d = load_d11(row.path, row.capture, row.vehicle_readme)
    st = validate_frame(d)
    raw = d11_raw_hex(row.path).str.strip().str.upper().to_numpy().astype("U16")
    back = bytes_to_hex(d["dlc"].to_numpy(), d[BYTE_COLS].to_numpy())
    t = d["t"].to_numpy()
    lab = d["label"].to_numpy()
    ids = d["id"].to_numpy()
    dt = np.diff(t)
    neg = np.flatnonzero(dt < 0)
    order = np.argsort(t, kind="stable")
    moved = order != np.arange(len(t))
    out = {
        "capture": row.capture, "sha256": sha256(row.path), "rows": len(d),
        "labels": {"0": int((lab == 0).sum()), "1": int((lab == 1).sum())},
        "dlc_hist": {str(k): int(v) for k, v in zip(*np.unique(d["dlc"].to_numpy(), return_counts=True))},
        "id_set": sorted(int(i) for i in np.unique(ids)),
        "roundtrip_ok": bool((raw == back).all()),
        "had_whitespace": bool(d11_raw_hex(row.path).str.contains(r"\s", regex=True).any()),
        "duration_s": float(t.max() - t.min()), "t_first": float(t[0]),
        "inversions": int(len(neg)), "min_dt": float(dt.min()) if len(dt) else 0.0,
        "inv_pairs_with_label_change": int((lab[neg] != lab[neg + 1]).sum()),
        "inv_pairs_involving_attack": int(((lab[neg] == 1) | (lab[neg + 1] == 1)).sum()),
        "inv_pairs_same_id": int((ids[neg] == ids[neg + 1]).sum()),
        "sort_moves_frames": int(moved.sum()),
        "sort_changes_label_seq": int((lab[order] != lab).sum()),
        "sort_changes_id_seq": int((ids[order] != ids).sum()),
        "max_displacement_if_sorted": int(np.abs(order - np.arange(len(t))).max()),
        "negative_dt_validate": st["negative_dt"],
    }
    return out


def main():
    ft = d11_file_table()
    res = []
    t0 = time.time()
    for k, row in enumerate(ft.itertuples()):
        cf = CACHE / (row.capture.replace("/", "__") + ".json")
        if cf.exists():
            r = json.load(open(cf))
        else:
            r = scan(row)
            json.dump(r, open(cf, "w"))
        res.append(r)
        print(f"{k + 1:3d}/{len(ft)} {r['capture']:60s} {r['rows']:>9,} lab1 {r['labels']['1']:>8,} "
              f"inv {r['inversions']:>4} rt {r['roundtrip_ok']} ({time.time() - t0:.0f}s)", flush=True)
    json.dump(res, open(results_dir("WP2") / "s1_d11_scan.json", "w"))
    print("done", time.time() - t0)


if __name__ == "__main__":
    main()
