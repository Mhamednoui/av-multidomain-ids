"""WP4 S6 diagnostic (descriptive, nothing is chosen from it): who are the BENIGN-labelled flows with the Bot beacon shape (3 fwd / 3 bwd packets, 0.99-1.03 s) on port 8080?
Compares their source / destination addresses with those of the Bot-labelled flows (final D10 tables, all splits). Output results/WP4/s6_bot_benign_shape.json."""
import glob
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.WP4_S6_lib import RES, S5

B = os.path.join(S5, "..", "D10", "final")
cols = ["file", "ts", "src_ip", "dst_ip", "dst_port", "family", "split", "Tot Fwd Pkts", "Tot Bwd Pkts", "Flow Duration"]
d = pd.concat([pd.read_pickle(f, compression="gzip")[cols] for f in glob.glob(os.path.join(B, "*.pkl"))], ignore_index=True)
d["family"] = d["family"].astype(str)
sh = (d["Tot Fwd Pkts"] == 3) & (d["Tot Bwd Pkts"] == 3) & d["Flow Duration"].between(993816, 1030358) & (d["dst_port"] == 8080)
bot_src = set(d.loc[d["family"] == "Bot", "src_ip"].astype(str))
bot_dst = set(d.loc[(d["family"] == "Bot") & (d["dst_port"] == 8080), "dst_ip"].astype(str))
out = {"bot_sources": sorted(bot_src), "bot_c2_8080": sorted(bot_dst)}
for sp in ("train", "val", "test"):
    x = d[sh & (d["split"].astype(str) == sp)]
    ben = x[x["family"] == "BENIGN"]
    out[sp] = {"shape_flows_bot": int((x["family"] == "Bot").sum()), "shape_flows_benign": int(len(ben)),
               "benign_src_in_bot_sources": int(ben["src_ip"].astype(str).isin(bot_src).sum()), "benign_dst_is_bot_c2": int(ben["dst_ip"].astype(str).isin(bot_dst).sum()),
               "benign_src_top": ben["src_ip"].astype(str).value_counts().head(5).to_dict(), "benign_dst_top": ben["dst_ip"].astype(str).value_counts().head(3).to_dict(),
               "benign_files": ben["file"].astype(str).value_counts().head(3).to_dict()}
    print(sp, out[sp], flush=True)
json.dump(out, open(os.path.join(RES, "s6_bot_benign_shape.json"), "w"), indent=1)
