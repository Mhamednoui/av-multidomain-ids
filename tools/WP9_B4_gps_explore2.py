"""WP9 B4 exploration 2 (descriptive): sessions of AV-GPS files; duplicates between files."""
import pandas as pd, numpy as np
D = r"C:\Users\nouir\PFE\codes\data\AV-GPS-Dataset"
dfs = [pd.read_csv(f"{D}/AV-GPS-Dataset-{i}.csv", low_memory=False) for i in range(4)]
def sessions(df):
    rt = pd.to_timedelta(df["Run Time"], errors="coerce").dt.total_seconds()
    d = rt.diff()
    lab = df["Data Type"].values
    new = (d < 0) | (d > 5) | (np.r_[False, np.diff(lab) != 0])
    sid = np.cumsum(new.values)
    return sid
for i, df in enumerate(dfs):
    sid = sessions(df)
    g = pd.DataFrame({"sid": sid, "lab": df["Data Type"].values}).groupby("sid").agg(n=("lab", "size"), lab=("lab", "first"))
    print("file", i, "sessions", len(g), "normal", (g.lab == 0).sum(), "spoof", (g.lab == 1).sum(), "sizes", g.n.describe()[["min", "50%", "max"]].tolist())
    print("   spoof sizes", g[g.lab == 1].n.tolist()[:20], "normal sizes", g[g.lab == 0].n.tolist()[:25])
# overlap of rows between files by key (lat, lon, clock time)
key = lambda df: set(zip(df["GPS Latitude"].round(7), df["GPS Longitude"].round(7), df["Clock Time"].astype(str), df["Heading (deg)"]))
k = [key(d) for d in dfs]
for a in range(4):
    print([round(len(k[a] & k[b]) / len(k[a]), 3) for b in range(4)])
# spoofed rows: position behaviour
d1 = dfs[2]; sp = d1[d1["Data Type"] == 1]; print(sp[["GPS Latitude","GPS Longitude","Velocity (m/s)","GPS HDOP","Satellite Locks","Satellite Count","Longitudinal Position (m)"]].head(8))
print(sp[["GPS Latitude","GPS Longitude","Velocity (m/s)","Satellite Count"]].describe())
print(dfs[3].groupby("Data Type")["EKF Detector"].agg(["mean","size"]))
print("---- session-level overlap")
def keys(df): return list(zip(df["GPS Latitude"].round(7), df["GPS Longitude"].round(7), df["Clock Time"].astype(str), df["Heading (deg)"]))
K = [set(keys(d)) for d in dfs]
for fi in (1, 2, 3):
    df = dfs[fi]; sid = sessions(df); kk = keys(df)
    for s in np.unique(sid):
        m = np.where(sid == s)[0]
        row = [np.mean([kk[j] in K[o] for j in m]) for o in range(4)]
        print(fi, s, "n", len(m), "lab", df["Data Type"].iloc[m[0]], "frac in files 0..3", np.round(row, 2))
print("---- within/between file duplicate sessions by lat/lon sequence")
import hashlib
seen = {}
for fi in (1, 2, 3):
    df = dfs[fi]; sid = sessions(df)
    for s in np.unique(sid):
        m = np.where(sid == s)[0]
        ll = df[["GPS Latitude", "GPS Longitude"]].iloc[m].round(6).values
        h = hashlib.md5(ll.tobytes()).hexdigest()[:8]
        seen.setdefault(h, []).append((fi, int(s), len(m), int(df["Data Type"].iloc[m[0]])))
for h, v in seen.items():
    if len(v) > 1: print(h, v)
# spoof sessions in file1: coordinates stats
df = dfs[1]; sid = sessions(df)
for s in np.unique(sid):
    m = np.where(sid == s)[0]
    if df["Data Type"].iloc[m[0]] == 1:
        g = df.iloc[m]
        print(s, len(m), "lat range", g["GPS Latitude"].min().round(3), g["GPS Latitude"].max().round(3), "sats", g["Satellite Count"].mean().round(2), "hdop", g["GPS HDOP"].mean().round(1), "vel", g["Velocity (m/s)"].mean().round(2))
