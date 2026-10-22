"""WP4 S5 explore (train / val only): constant and duplicate features, benign train feature ranges, Bot flow shape in train."""
import json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from network.flows import FEATURES
from tools.WP4_S3_lib import load, ROOT
X = np.load(os.path.join(ROOT, "..", "data_extra", "cache_v3", "WP4", "S5", "D10_X.npy"), mmap_mode="r")
d = load("D10")
tr = (d.split.astype(str) == "train").to_numpy() & (d.family.astype(str) == "BENIGN").to_numpy() & ~d.audit.to_numpy()
Xt = np.asarray(X[np.flatnonzero(tr)])
print("benign train", Xt.shape)
df = pd.DataFrame(Xt, columns=FEATURES)
st = df.describe(percentiles=[.01, .5, .99]).T[["min", "1%", "50%", "99%", "max"]]
st["nan"] = df.isna().mean(); st["nuniq"] = df.nunique()
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
print(st.round(3))
# duplicates
cols = FEATURES
dup = {}
for i, a in enumerate(cols):
    for b in cols[i+1:]:
        if np.array_equal(df[a].fillna(-9).values, df[b].fillna(-9).values):
            dup[a] = b
print("identical columns:", dup)
ba = d.family.astype(str) == "Bot"
Xb = pd.DataFrame(np.asarray(X[np.flatnonzero(ba.to_numpy() & (d.split.astype(str) == "train").to_numpy())]), columns=FEATURES)
print(Xb.describe(percentiles=[.5]).T[["min", "50%", "max", "std"]].round(2))
print(d.loc[ba & (d.split.astype(str) == "train"), "dst_port"].value_counts().head())
