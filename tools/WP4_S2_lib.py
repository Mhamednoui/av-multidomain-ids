"""WP4 S2 shared loaders: compact D10 / D23 tables (only the columns the L1 layers need) from the S1 caches.
Writes small pickles to ../data_extra/cache_v3/WP4/S2/ (first call), reads them afterwards."""
import glob
import os

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
B = os.path.join(ROOT, "..", "data_extra", "cache_v3", "WP4")
OUT = os.path.join(B, "S2")
IDS = ["ts", "src_ip", "dst_ip", "src_port", "dst_port", "protocol", "family", "split", "day", "file"]
FEAT = ["Flow Duration", "Tot Fwd Pkts", "Tot Bwd Pkts", "TotLen Fwd Pkts", "TotLen Bwd Pkts", "Fwd Pkt Len Max", "Fwd Pkt Len Min",
        "Fwd Header Len", "Bwd Header Len", "Pkt Len Max", "FIN Flag Cnt", "SYN Flag Cnt", "RST Flag Cnt", "PSH Flag Cnt", "ACK Flag Cnt",
        "URG Flag Cnt", "ECE Flag Cnt"]


def _build(ds, files, stage=False):
    parts = []
    for f in files:
        d = pd.read_pickle(f, compression="gzip")
        cols = [c for c in IDS + FEAT if c in d.columns]
        d = d[cols].copy()
        for c in ("family", "split", "day", "file"):
            d[c] = d[c].astype(str).astype("category")
        for c in FEAT:
            d[c] = d[c].astype("float32")
        parts.append(d)
    return pd.concat(parts, ignore_index=True)


def _load(ds):
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, ds + ".pkl")
    if os.path.exists(p):
        return pd.read_pickle(p)
    d = _build(ds, sorted(glob.glob(os.path.join(B, ds, "final", "*.pkl"))))
    d["t"] = d["ts"].astype("int64") / 1e9
    d.loc[d["ts"].isna(), "t"] = float("nan")
    d.to_pickle(p)
    return d


def load_d10():
    return _load("D10")


def load_d23():
    return _load("D23")
