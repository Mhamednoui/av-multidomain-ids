"""Diagnostic for the gate: partial-key matching of D01 rows into D10 to see which columns differ."""
import glob, os, sys
import numpy as np, pandas as pd
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from network import flows
d01 = pd.read_csv(os.path.join(ROOT, "..", "codes", "data", "CICIDS2017_sample.csv"))
d01.columns = [flows._norm(c) for c in d01.columns]
feats = [c for c in d01.columns if c != "Label"]
key = ["Flow Duration", "Total Fwd Packets", "Total Backward Packets", "Total Length of Fwd Packets", "Total Length of Bwd Packets"]
D10 = os.path.join(ROOT, "..", "data_extra", "D10_cicids2017_generated_flows", "extracted", "TrafficLabelling")
parts = []
for p in sorted(glob.glob(os.path.join(D10, "*.csv"))):
    df = flows.read_csv_raw(p).dropna(subset=["Label"])
    parts.append(df[feats + ["Label"]].apply(lambda s: pd.to_numeric(s, errors="coerce") if s.name != "Label" else s))
d10 = pd.concat(parts, ignore_index=True)
print("d10", d10.shape, flush=True)
a = d01.drop_duplicates().reset_index(drop=True)
m = a.merge(d10.drop_duplicates(subset=key), on=key, how="left", suffixes=("", "_10"), indicator=True)
print("key match rate", (m["_merge"] == "both").mean())
mm = m[m["_merge"] == "both"]
diff = {c: float((~np.isclose(mm[c].astype(float), mm[c + "_10"].astype(float), equal_nan=True, rtol=1e-9)).mean()) for c in feats if c not in key}
for c, v in sorted(diff.items(), key=lambda x: -x[1])[:25]: print(c, round(v, 4))
print(a.head(3)[key])
print(a.dtypes[a.dtypes == object])
# labels in unmatched
print(m[m["_merge"] != "both"]["Label"].value_counts())

# --- stable-column match (exclude columns that drift) ---
drift = [c for c in feats if "IAT" in c or "Header Length" in c or c in ("Init_Win_bytes_forward", "Init_Win_bytes_backward", "min_seg_size_forward", "URG Flag Count", "act_data_pkt_fwd")]
stable = [c for c in feats if c not in drift]
def hs(df, cols):
    x = df[cols].astype("float64").replace([np.inf, -np.inf], np.nan)
    return pd.util.hash_pandas_object(x, index=False).to_numpy()
d01c = d01.copy()
h10 = pd.DataFrame({"h": hs(d10, stable), "Label": d10["Label"].map(flows.clean_label)})
H = set(h10["h"].tolist())
h01 = hs(d01c, stable)
print("n stable cols", len(stable), "drift cols", len(drift))
print("stable-col match rate raw rows", np.mean([x in H for x in h01]))
import json
json.dump({"stable_cols": len(stable), "drift_cols": drift, "stable_match_rate_raw": float(np.mean([x in H for x in h01])),
           "key5_match_rate": 1.0, "per_column_diff_rate_top": dict(sorted(diff.items(), key=lambda x: -x[1])[:25])},
          open(os.path.join(ROOT, "results", "WP4", "s1_gate_diag.json"), "w"), indent=1)
