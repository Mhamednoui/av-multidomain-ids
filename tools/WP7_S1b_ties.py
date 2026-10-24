"""WP7 S1b: how often does v2x.l3.birth_density (track_birth check) use births with EQUAL timestamp that arrive later in the table, i.e. information a causal stream does not have?
COUNTING ONLY: nothing is scored; the only columns read are track and t (and the split lists). Datasets: VeReMi validation and test splits (all rows of the split senders, attackers
included, as the S6 harness streams them) and Tampa v2 validation and test passages (genuine clean frame; injected attack scenarios copy these timestamps).
Birth = first message of a track. A tied group = births of different tracks with exactly equal t. In a group of m births, the (m-1) earlier-ordered ones are scored by the batch with
the later ones counted (m(m-1)/2 non-causal pairs, m-1 affected births). Order = time, ties by table order (what the runner sees). Also counts rows that share t with another row (any track).
Run from codes_v3/: python -I -u -W ignore tools/WP7_S1b_ties.py     Output: results/WP7/S1b_ties.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP7_S1_lib as L

import numpy as np
import pandas as pd

from v2x import adapters, splitting
import WP5_S5_dev as dev5


def count(df):
    d = df[["track", "t"]].reset_index(drop=True)
    d = d.iloc[np.argsort(d["t"].to_numpy(), kind="stable")]
    first = ~d["track"].duplicated().to_numpy()
    births = d[first]
    g = births.groupby("t").size()
    tied = g[g > 1]
    rows_g = d.groupby("t").size()
    return {"messages": int(len(d)), "tracks_births": int(len(births)),
            "messages_sharing_t_with_another_message": int(rows_g[rows_g > 1].sum()),
            "tied_birth_groups": int(len(tied)), "births_in_tied_groups": int(tied.sum()),
            "noncausal_birth_pairs": int((tied * (tied - 1) // 2).sum()), "births_with_noncausal_neighbour": int((tied - 1).sum()),
            "share_of_births_affected": float((tied - 1).sum() / max(len(births), 1))}


def main():
    res = {}
    v, sp = dev5.load_frames()
    for part in ("val", "test"):
        res[f"VeReMi {part}"] = count(splitting.rows_of(v, sp[part]))
    tp = adapters.load_tampa(with_age=True)
    st = json.loads((L.ROOT / "results" / "WP5" / "splits_tampa_v2.json").read_text())
    for part in ("val", "test"):
        res[f"Tampa {part}"] = count(tp[tp["sender"].isin(set(map(str, st[part])))])
    L.dump({"what": "counting of equal-timestamp births (non-causal use in v2x.l3.birth_density); no scoring", "datasets": res}, "S1b_ties.json")
    for k, x in res.items():
        print(k, x, flush=True)


if __name__ == "__main__":
    main()
