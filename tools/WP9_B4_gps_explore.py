"""WP9 B4 exploration of AV-GPS-Dataset files (read-only, descriptive; no model)."""
import sys, pandas as pd, numpy as np
D = r"C:\Users\nouir\PFE\codes\data\AV-GPS-Dataset"
for i in range(4):
    df = pd.read_csv(f"{D}/AV-GPS-Dataset-{i}.csv", low_memory=False)
    print("== file", i, df.shape, "label counts", df["Data Type"].value_counts().to_dict())
    rt = pd.to_timedelta(df["Run Time"], errors="coerce").dt.total_seconds()
    d = rt.diff()
    brk = np.where((d < 0) | (d > 5))[0]
    print(" run-time breaks (reset/gap) n=", len(brk), brk[:20])
    lab = df["Data Type"].values
    ch = np.where(np.diff(lab) != 0)[0] + 1
    print(" label changes at", ch[:30], "n", len(ch))
    for c in ["Satellite Locks", "Satellite Count", "GPS HDOP"]:
        print(" ", c, df.groupby("Data Type")[c].describe()[["mean", "min", "50%", "max"]].round(2).to_dict("index"))
    if "EKF Detector" in df: print(" EKF Detector", df.groupby("Data Type")["EKF Detector"].mean().to_dict())
    print(" date/time ranges", df["Clock Date"].dropna().unique()[:5], df["Clock Time"].iloc[[0,-1]].tolist())
a = pd.read_csv(f"{D}/AV-GPS-Dataset-0.csv", low_memory=False); b = pd.read_csv(f"{D}/AV-GPS-Dataset-1.csv", low_memory=False)
n = len(a); print("file0 == first rows of file1:", (a.fillna(-9).values[:n] == b.fillna(-9).values[:n]).all() if True else None)
