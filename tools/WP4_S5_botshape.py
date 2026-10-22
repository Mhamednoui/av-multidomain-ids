"""WP4 S5: descriptive Bot flow shapes per split (D10 stream, packet counts / duration), to explain the signature check. Writes results/WP4/s5_bot_shapes.json."""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.WP4_S5_lib import RES, frame, load_d10

d, X = load_d10()
out = {}
for sp in ("train", "val", "test"):
    m = ((d["split"].astype(str) == sp) & (d["family"].astype(str) == "Bot")).to_numpy()
    f = frame(d, X, m)
    g = f.groupby(["Tot Fwd Pkts", "Tot Bwd Pkts"]).size().sort_values(ascending=False)
    out[sp] = {"n": int(m.sum()), "port_8080": int((f["dst_port"] == 8080).sum()), "top_shapes": {"%g/%g" % k: int(v) for k, v in g.head(6).items()},
               "median_duration_us": float(f["Flow Duration"].median()), "dur_p5_p95": [float(f["Flow Duration"].quantile(.05)), float(f["Flow Duration"].quantile(.95))]}
    print(sp, out[sp])
json.dump(out, open(os.path.join(RES, "s5_bot_shapes.json"), "w"), indent=1)
# benign flows with the beacon-phase shape (3 fwd / 3 bwd packets, duration 0.99-1.05 s)
for sp in ("train", "val", "test"):
    m = ((d["split"].astype(str) == sp) & (d["family"].astype(str) == "BENIGN") & ~d["audit"]).to_numpy()
    f = frame(d, X, m)
    s = (f["Tot Fwd Pkts"] == 3) & (f["Tot Bwd Pkts"] == 3) & (f["Flow Duration"] >= 0.99e6) & (f["Flow Duration"] <= 1.05e6)
    out[sp]["benign_beacon_shape"] = {"benign_flows": int(m.sum()), "match": int(s.sum()), "match_port_8080": int((s & (f["dst_port"] == 8080)).sum())}
    print(sp, out[sp]["benign_beacon_shape"])
json.dump(out, open(os.path.join(RES, "s5_bot_shapes.json"), "w"), indent=1)
