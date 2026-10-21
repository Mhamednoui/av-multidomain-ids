import glob, os, pandas as pd, json
FIN = r"C:/Users/nouir/PFE/data_extra/cache_v3/WP4/D10/final"
out = {}
for p in sorted(glob.glob(os.path.join(FIN, "*.pkl"))):
    d = pd.read_pickle(p, compression="gzip")[["file", "ts", "family"]]
    d["h"] = d["ts"].dt.hour
    d["day"] = d["ts"].dt.strftime("%m-%d")
    d["att"] = d["family"].astype(str) != "BENIGN"
    for (day, f), g in d.groupby(["day", d["file"].astype(str).str[:9]]):
        k = day + " " + f
        o = out.setdefault(k, {"all": {}, "att": {}})
        for h, v in g["h"].value_counts().items(): o["all"][int(h)] = o["all"].get(int(h), 0) + int(v)
        for h, v in g[g["att"]]["h"].value_counts().items(): o["att"][int(h)] = o["att"].get(int(h), 0) + int(v)
for k, o in out.items():
    print(k, "hours all", sorted(o["all"]), "attack hours", {h: o["att"][h] for h in sorted(o["att"])})
