"""WP2 S4: check can/signals.py decoding against the decoded signal_extractions CSV of ROAD.
Usage: python tools/WP2_S4_decode_check.py <capture> [...]   -> results/WP2/s4_decode_check.json
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from can import adapters as A
from can import signals as S
from common.config import DATA_EXTRA, RESULTS

OUT = RESULTS / "WP2"


def check(name, dbc):
    B = np.load(DATA_EXTRA / "WP2_S4_cache" / "road" / (name + ".npy"))
    raw = np.load(DATA_EXTRA / "WP2_S2_cache" / "road" / (name + ".npz"))
    csv = A.load_road_signals(name)
    keep = np.isin(raw["id"], list(dbc))
    res = {"frames": int(len(B)), "frames_in_dbc": int(keep.sum()), "csv_rows": int(len(csv))}
    if len(csv) != keep.sum():
        res["aligned"] = False
        return res
    ids = raw["id"][keep]
    B = B[keep]
    res["id_equal"] = bool((csv["ID"].to_numpy() == ids).all())
    dec = S.decode_all(ids, B, dbc)
    bad, tot = {}, 0
    for i, (rows, V) in dec.items():
        C = csv.iloc[rows, 3:3 + V.shape[1]].to_numpy(float)
        ok = np.isclose(C, V, equal_nan=True)
        tot += ok.size
        if not ok.all():
            bad[hex(i)] = [int((~ok[:, k]).sum()) for k in range(V.shape[1])]
    res["values_compared"] = int(tot)
    res["ids_with_mismatch"] = bad
    res["aligned"] = True
    return res


def main():
    dbc = S.parse_dbc()
    out = {"n_ids": len(dbc), "n_signals": sum(len(v) for v in dbc.values())}
    out["captures"] = {n: check(n, dbc) for n in sys.argv[1:]}
    json.dump(out, open(OUT / "s4_decode_check.json", "w"), indent=1)
    print(json.dumps(out, indent=1)[:3000])


if __name__ == "__main__":
    main()
