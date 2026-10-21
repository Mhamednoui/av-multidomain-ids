"""WP4 S1: build the unified flow tables for D10 (CICIDS2017) or D23 (CSE-CIC-IDS2018).

Stage 1: read each CSV in chunks, drop empty rows and repeated header rows (counted), canonical columns
(ids, ts, 76 features float32, label, family, group, 64-bit feature hash) -> stage chunk files in the cache.
Stage 2: global v2 cleaning (exact duplicates, conflicting labels; counts per file), time split per day,
rewrite chunk files with kept rows + split + period -> final cache; counts -> results/WP4/s1_clean_<ds>.json.
Cache: ../data_extra/cache_v3/WP4/<ds>/ (pickle, gzip level 1; not in git). Resumable: stage 1 skips chunks that exist.
Run (codes_v3): python -u -W ignore -I tools/WP4_s1_build.py D10|D23
"""
import glob, json, os, sys, time
import numpy as np, pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from network import flows as F

EXTRA = os.path.join(ROOT, "..", "data_extra")
SRC = {"D10": os.path.join(EXTRA, "D10_cicids2017_generated_flows", "extracted", "TrafficLabelling"),
       "D23": os.path.join(EXTRA, "D23_cse-cic-ids2018", "raw")}
CACHE = os.path.join(EXTRA, "cache_v3", "WP4")
RES = os.path.join(ROOT, "results", "WP4")
CHUNK = 1_000_000
IDS = ["src_ip", "src_port", "dst_ip", "dst_port", "protocol"]


def canon(df, ds):
    """Raw stripped-header chunk -> canonical frame (no cleaning yet except empty / header rows, done by the caller)."""
    if ds == "D10":
        df = df.rename(columns={**F.D10_ID_RENAME, **F.D10_TO_D23})
    else:
        df = df.rename(columns=F.D23_ID_RENAME)
    for c in IDS:
        if c not in df.columns:
            df[c] = np.nan
    return df


def stage1(ds):
    out = os.path.join(CACHE, ds, "stage")
    os.makedirs(out, exist_ok=True)
    files = sorted(glob.glob(os.path.join(SRC[ds], "*.csv")))
    for p in files:
        base = os.path.basename(p)
        k = 0
        marker = os.path.join(out, base + ".done")
        if os.path.exists(marker):
            continue
        t0 = time.time()
        rdr = pd.read_csv(p, chunksize=CHUNK, encoding="utf-8", encoding_errors="replace", low_memory=False)
        row0 = 0
        for ch in rdr:
            n_in = len(ch)
            ch.columns = [F._norm(c) for c in ch.columns]
            lab_col = ch["Label"]
            empty = lab_col.isna()
            hdr = (lab_col.astype(str).str.strip() == "Label") & ~empty
            rows = np.arange(row0, row0 + n_in)
            row0 += n_in
            ch = ch[~empty & ~hdr].copy()
            rows = rows[(~empty & ~hdr).to_numpy()]
            ch = canon(ch, ds)
            if ds == "D10":
                ch = ch.drop(columns=["Fwd Header Length.1", "Flow ID"], errors="ignore")
            else:
                ch = ch.drop(columns=["flow_id"], errors="ignore")
            miss = [c for c in F.FEATURES if c not in ch.columns]
            assert not miss, miss
            ts = F.parse_ts(ch["ts_raw"], pm_fix=(ds == "D10")).to_numpy()
            lab = ch["label_raw"].map(F.clean_label)
            fam = F.map_family(lab, ds)
            feat = ch[F.FEATURES].apply(pd.to_numeric, errors="coerce").astype("float64").replace([np.inf, -np.inf], np.nan)
            h = pd.util.hash_pandas_object(feat, index=False).to_numpy()
            o = pd.DataFrame({"file": base, "row": rows, "ts": ts, "src_ip": ch["src_ip"].astype("object").to_numpy(),
                              "dst_ip": ch["dst_ip"].astype("object").to_numpy(),
                              "src_port": pd.to_numeric(ch["src_port"], errors="coerce").to_numpy(),
                              "dst_port": pd.to_numeric(ch["dst_port"], errors="coerce").to_numpy(),
                              "protocol": pd.to_numeric(ch["protocol"], errors="coerce").to_numpy(),
                              "label": lab.to_numpy(), "family": fam, "hash": h})
            o["group"] = o["family"].map(F.GROUP)
            for c in ["src_ip", "dst_ip", "file", "label", "family", "group"]:
                o[c] = o[c].astype("category")
            o = pd.concat([o, feat.astype("float32").reset_index(drop=True)], axis=1)
            o.attrs = {}
            o.to_pickle(os.path.join(out, "%s.%03d.pkl" % (base, k)), compression={"method": "gzip", "compresslevel": 1})
            # raw counters for this chunk
            with open(os.path.join(out, "%s.%03d.json" % (base, k)), "w") as f:
                json.dump({"file": base, "chunk": k, "lines_read": int(n_in), "empty_rows": int(empty.sum()),
                           "repeated_header_rows": int(hdr.sum()), "kept": int(len(o)),
                           "bad_timestamp": int(pd.isna(ts).sum())}, f)
            k += 1
        open(marker, "w").write("ok")
        print(ds, base, "chunks", k, "%.0fs" % (time.time() - t0), flush=True)


def stage2(ds):
    st = os.path.join(CACHE, ds, "stage")
    fin = os.path.join(CACHE, ds, "final")
    os.makedirs(fin, exist_ok=True)
    chunks = sorted(glob.glob(os.path.join(st, "*.pkl")))
    cols = ["file", "row", "ts", "family", "hash"]
    parts = []
    for p in chunks:
        d = pd.read_pickle(p, compression="gzip")[cols]
        d["file"] = d["file"].astype(str); d["family"] = d["family"].astype(str)
        d["chunk"] = os.path.basename(p)
        parts.append(d)
    g = pd.concat(parts, ignore_index=True)
    if ds == "D23":                                       # stage 1 parsed D23 without the 12-hour fix: apply it here
        g["ts"] = F.fix_pm(g["ts"])
    g.loc[g["ts"].dt.year < 2017, "ts"] = pd.NaT          # D23 has a few epoch-1970 timestamps: treated as unparseable
    n = len(g)
    print("rows after header/empty removal:", n, flush=True)
    fam_code = pd.factorize(g["family"])[0].astype(np.int16)
    order = g["ts"].astype("int64").to_numpy()               # NaT = very negative; stable sort keeps file order
    order = np.where(g["ts"].isna().to_numpy(), np.iinfo(np.int64).max, order)
    keep, n_dup, n_conf, kind = F.dedup_conflicts(g["hash"].to_numpy(), fam_code, order)
    g["kind"] = kind
    print("exact dup", n_dup, "conflict rows", n_conf, flush=True)
    # split per day on kept rows
    g["day"] = g["ts"].dt.strftime("%Y-%m-%d").fillna("NaT")
    g["split"] = "dropped"
    g["period"] = -1
    kk = g[keep]
    for day, sub in kk.groupby("day"):
        if day == "NaT":
            g.loc[sub.index, "split"] = "gap"
            continue
        s, per = F.time_split(sub["ts"].to_numpy(), sub["family"].to_numpy())
        g.loc[sub.index, "split"] = s
        g.loc[sub.index, "period"] = per
    # counts per file
    per_file = {}
    for fname, sub in g.groupby("file"):
        c = {"rows_after_header_empty": int(len(sub)), "exact_duplicates_removed": int((sub["kind"] == 1).sum()),
             "conflicting_label_rows_removed": int((sub["kind"] == 2).sum()), "rows_clean": int((sub["kind"] == 0).sum()),
             "bad_timestamp": int(sub["ts"].isna().sum())}
        per_file[fname] = c
    raw = {}
    for jp in sorted(glob.glob(os.path.join(st, "*.json"))):
        j = json.load(open(jp))
        r = raw.setdefault(j["file"], {"lines_read": 0, "empty_rows": 0, "repeated_header_rows": 0})
        for k2 in r:
            r[k2] += j[k2]
    for f_, r in raw.items():
        per_file[f_].update(r)
    clean = g[g["kind"] == 0]
    out = {"dataset": ds, "files": per_file,
           "total": {k2: int(sum(v[k2] for v in per_file.values())) for k2 in
                     ["lines_read", "empty_rows", "repeated_header_rows", "rows_after_header_empty",
                      "exact_duplicates_removed", "conflicting_label_rows_removed", "rows_clean", "bad_timestamp"]},
           "labels_clean": clean["family"].value_counts().to_dict(),
           "labels_before_dedup": g["family"].value_counts().to_dict(),
           "labels_per_file_clean": {f_: sub["family"].value_counts().to_dict() for f_, sub in clean.groupby("file")},
           "split_counts": {s: {fm: int(v) for fm, v in sub["family"].value_counts().items()} for s, sub in clean.groupby("split")},
           "split_totals": clean["split"].value_counts().to_dict(),
           "days": {d: {s: int(v) for s, v in sub["split"].value_counts().items()} for d, sub in clean.groupby("day")}}
    json.dump(out, open(os.path.join(RES, "s1_clean_%s.json" % ds), "w"), indent=1)
    print(json.dumps(out["total"]), flush=True)
    # rewrite chunks with kept rows
    start = g.groupby("chunk").apply(lambda x: x.index[0]).to_dict()
    by_chunk = {c: sub for c, sub in g[g["kind"] == 0].groupby("chunk")}
    for p in chunks:
        b = os.path.basename(p)
        d = pd.read_pickle(p, compression="gzip")
        sub = by_chunk.get(b)
        if sub is None:
            continue
        ix = sub.index.to_numpy() - start[b]
        d = d.iloc[ix].copy()
        if ds == "D23":
            d["ts"] = F.fix_pm(d["ts"])
        d.loc[d["ts"].dt.year < 2017, "ts"] = pd.NaT
        d["split"] = pd.Categorical(sub["split"].to_numpy())
        d["period"] = sub["period"].to_numpy()
        d["day"] = pd.Categorical(sub["day"].to_numpy())
        d.to_pickle(os.path.join(fin, b), compression={"method": "gzip", "compresslevel": 1})
    print("final written", flush=True)


if __name__ == "__main__":
    ds = sys.argv[1]
    os.makedirs(RES, exist_ok=True)
    if len(sys.argv) < 3 or sys.argv[2] == "1":
        stage1(ds)
    if len(sys.argv) < 3 or sys.argv[2] == "2":
        stage2(ds)
