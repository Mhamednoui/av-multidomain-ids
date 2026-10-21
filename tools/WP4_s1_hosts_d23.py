"""WP4 S1: D23 per-host summary. Only the Thuesday-20-02 file has IPs (80-column files have none). Output results/WP4/s1_hosts_d23.json
Run: python -u -W ignore -I tools/WP4_s1_hosts_d23.py"""
import glob, json, os
import pandas as pd
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIN = os.path.join(ROOT, "..", "data_extra", "cache_v3", "WP4", "D23", "final")
parts = []
for p in sorted(glob.glob(os.path.join(FIN, "Thuesday*.pkl"))):
    d = pd.read_pickle(p, compression="gzip")[["ts", "src_ip", "dst_ip", "family"]]
    for c in ["src_ip", "dst_ip", "family"]:
        d[c] = d[c].astype(str)
    parts.append(d)
d = pd.concat(parts)
res = {"file": "Thuesday-20-02-2018", "rows_clean": int(len(d)), "ts_min": str(d["ts"].min()), "ts_max": str(d["ts"].max()), "families": {}}
for f, g in d[d["family"] != "BENIGN"].groupby("family"):
    res["families"][f] = {"flows": int(len(g)), "top_src": g["src_ip"].value_counts().head(5).to_dict(),
                          "top_dst": g["dst_ip"].value_counts().head(5).to_dict()}
json.dump(res, open(os.path.join(ROOT, "results", "WP4", "s1_hosts_d23.json"), "w"), indent=1)
print(json.dumps(res)[:1500])
