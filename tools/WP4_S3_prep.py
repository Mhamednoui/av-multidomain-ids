"""WP4 S3 prep: compact PRE-DEDUP flow tables (stage caches) with the time split of the final tables.

Stage rows (all flows, duplicates and conflicting labels kept: flow multiplicity matters for counts) get
  - the +12 h fix of S1 (hours 1..7 are PM; stage ts is raw),
  - split / period / day looked up from the final tables: the interval [min ts, max ts] of every (day, period, split) of the final table;
    a stage flow outside every interval (the 1-minute gaps) gets split "gap".
Self-check: final rows pushed through the same lookup must keep their split (agreement printed).
Output: ../data_extra/cache_v3/WP4/S3/D10_stage.pkl, D23tue_stage.pkl (IPs factorised to int32 codes, minute index, features float32).
Usage: python -u -W ignore tools/WP4_S3_prep.py
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
B = os.path.join(ROOT, "..", "data_extra", "cache_v3", "WP4")
OUT = os.path.join(B, "S3")
FEAT = ["Flow Duration", "Tot Fwd Pkts", "Tot Bwd Pkts", "TotLen Fwd Pkts", "TotLen Bwd Pkts",
        "FIN Flag Cnt", "SYN Flag Cnt", "RST Flag Cnt", "PSH Flag Cnt", "ACK Flag Cnt", "URG Flag Cnt", "ECE Flag Cnt",
        "Fwd Header Len", "Bwd Header Len", "Fwd Pkt Len Max", "Fwd Pkt Len Min", "Pkt Len Max"]
IDS = ["file", "row", "ts", "src_ip", "dst_ip", "src_port", "dst_port", "protocol", "family"]


def log(*a):
    print(*a, flush=True)


def fix_ts(ts):
    h = ts.dt.hour
    return ts.where(~((h >= 1) & (h <= 7)), ts + pd.Timedelta(hours=12))


def intervals(final):
    f = final[final.split != "gap"]
    g = f.groupby(["day", "period", "split"], observed=True).ts.agg(["min", "max"]).reset_index()
    g["day"] = g["day"].astype(str)
    g["split"] = g["split"].astype(str)
    return g.sort_values("min").reset_index(drop=True)


def assign(ts, iv):
    """split, period for every ts (ns int64) via the interval table (sorted by start); outside -> gap."""
    st = iv["min"].astype("int64").to_numpy()
    en = iv["max"].astype("int64").to_numpy()
    t = ts.astype("int64").to_numpy()
    i = np.searchsorted(st, t, side="right") - 1
    ok = (i >= 0) & (t <= en[np.clip(i, 0, None)])
    i = np.clip(i, 0, None)
    split = np.where(ok, iv["split"].to_numpy()[i], "gap")
    period = np.where(ok, iv["period"].to_numpy()[i], -1)
    return split, period


def build(ds, stage_files, final_files, fname):
    final = pd.concat([pd.read_pickle(f, compression="gzip")[["file", "row", "ts", "day", "period", "split"]] for f in final_files],
                      ignore_index=True)
    iv_by_day = {d: g for d, g in intervals(final).groupby("day")}
    parts = []
    for p in stage_files:
        s = pd.read_pickle(p, compression="gzip")
        s = s[IDS + FEAT].copy()
        s["ts"] = fix_ts(s["ts"])
        parts.append(s)
        log("  read", os.path.basename(p), len(s))
    s = pd.concat(parts, ignore_index=True)
    del parts
    s = s[s.ts.notna() & (s.ts.dt.year > 2000)].reset_index(drop=True)
    s["day"] = s["ts"].dt.strftime("%Y-%m-%d")
    s["split"] = "gap"
    s["period"] = -1
    for d, g in s.groupby("day"):
        if d not in iv_by_day:
            continue
        sp, pe = assign(g["ts"], iv_by_day[d])
        s.loc[g.index, "split"] = sp
        s.loc[g.index, "period"] = pe
    # self-check on the final rows
    fchk = final[final.split != "gap"].copy()
    fchk["day"] = fchk["day"].astype(str)
    ok = 0
    tot = 0
    for d, g in fchk.groupby("day"):
        sp, _ = assign(g["ts"], iv_by_day[d])
        ok += int((sp == g["split"].astype(str).to_numpy()).sum())
        tot += len(g)
    log("  self-check: final rows keep their split", ok, "/", tot)
    # the (file,row) of a final row must have the same ts as the corrected stage row
    m = fchk[["file", "row", "ts"]].merge(s[["file", "row", "ts"]], on=["file", "row"], suffixes=("_f", "_s"))
    log("  ts agreement final vs stage (file,row):", float((m.ts_f == m.ts_s).mean()), "of", len(m), "matched rows")
    # compact encoding
    src = pd.concat([s.src_ip, s.dst_ip]).astype(str)
    codes, uni = pd.factorize(src)
    s["src_id"] = codes[:len(s)].astype("int32")
    s["dst_id"] = codes[len(s):].astype("int32")
    s["minute"] = (s["ts"].astype("int64") // 60_000_000_000).astype("int64")
    s["t"] = s["ts"].astype("int64") / 1e9
    s = s.drop(columns=["src_ip", "dst_ip"])
    for c in FEAT:
        s[c] = s[c].astype("float32")
    for c in ("file", "family", "split", "day"):
        s[c] = s[c].astype(str).astype("category")
    s["dst_port"] = pd.to_numeric(s["dst_port"], errors="coerce").fillna(-1).astype("int32")
    s["src_port"] = pd.to_numeric(s["src_port"], errors="coerce").fillna(-1).astype("int32")
    s["protocol"] = pd.to_numeric(s["protocol"], errors="coerce").fillna(-1).astype("int16")
    s["period"] = s["period"].astype("int16")
    s = s.sort_values(["day", "file", "row"], kind="stable").reset_index(drop=True)
    os.makedirs(OUT, exist_ok=True)
    s.to_pickle(os.path.join(OUT, fname))
    info = {"n": int(len(s)), "by_split": s.split.value_counts().to_dict(),
            "by_family_split": {f"{a}|{b}": int(c) for (a, b), c in s.groupby(["family", "split"], observed=True).size().items() if c},
            "self_check": [ok, tot]}
    log("  ", fname, len(s), s.split.value_counts().to_dict())
    return info


def main():
    info = {}
    log("D10")
    info["D10"] = build("D10", sorted(glob.glob(os.path.join(B, "D10", "stage", "*.pkl"))),
                        sorted(glob.glob(os.path.join(B, "D10", "final", "*.pkl"))), "D10_stage.pkl")
    log("D23 Tue-20-02")
    info["D23tue"] = build("D23", sorted(glob.glob(os.path.join(B, "D23", "stage", "Thues*.pkl"))),
                           sorted(glob.glob(os.path.join(B, "D23", "final", "Thues*.pkl"))), "D23tue_stage.pkl")
    json.dump(info, open(os.path.join(ROOT, "results", "WP4", "s3_prep.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
