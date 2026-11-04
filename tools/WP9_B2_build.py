"""WP9 B2: build compact flow tables for the network benchmark (cache ../data_extra/cache_v3/WP9/B2/<name>.pkl, outside git).

Names: D10o = CICIDS2017 original CICFlowMeter labels (the WP4 cleaned table, re-used: exact duplicates and conflicting labels already removed);
D10e = CICIDS2017 corrected labels of Engelen et al. 2021 (WTMC), regenerated with the fixed CICFlowMeter; "X - Attempted" flows are relabelled
BENIGN as the authors recommend (the attempted family is kept in column `attempted`), then the same dedup / conflict cleaning as WP4.
Columns: day, ts (datetime64), src_ip, dst_ip, src_port, dst_port, protocol, family, attempted, 76 features (D23 names, float32), v3split (D10o only).
Run (codes_v3): python -u -W ignore -I tools/WP9_B2_build.py D10o|D10e
"""
import glob, json, os, sys, time
import numpy as np, pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from network import flows as F

EXTRA = os.path.join(ROOT, "..", "data_extra")
OUT = os.path.join(EXTRA, "cache_v3", "WP9", "B2")
RES = os.path.join(ROOT, "results", "WP9")
FEATS = F.FEATURES
IDC = ["src_ip", "dst_ip", "src_port", "dst_port", "protocol"]


def build_d10o():
    fs = sorted(glob.glob(os.path.join(EXTRA, "cache_v3", "WP4", "D10", "final", "*.pkl")))
    parts = []
    for f in fs:
        d = pd.read_pickle(f, compression="gzip")
        d["day"] = os.path.basename(f).split("-")[0]
        d = d.rename(columns={"split": "v3split", "period": "v3period"})
        d["attempted"] = ""
        parts.append(d[["day", "file", "row", "ts"] + IDC + ["family", "attempted", "v3split", "v3period"] + FEATS])
    d = pd.concat(parts, ignore_index=True)
    d["ts"] = pd.to_datetime(d["ts"])
    stats = {"rows": int(len(d)), "note": "WP4 cleaned table (results/WP4/s1_clean_D10.json holds the dedup counts)"}
    return d, stats


MAP_E = None


def build_d10e():
    src = os.path.join(EXTRA, "D10e_cicids2017_wtmc2021", "extracted")
    parts, raw_n = [], {}
    for f in sorted(glob.glob(os.path.join(src, "*.csv"))):
        x = pd.read_csv(f, low_memory=False)
        x.columns = [F._norm(c) for c in x.columns]
        cols = list(x.columns)
        assert cols[:7] == ["Flow ID", "Src IP", "Src Port", "Dst IP", "Dst Port", "Protocol", "Timestamp"] and cols[-1] == "Label" and len(cols) == 84, cols[:8]
        feat_cols = cols[7:83]
        base = os.path.basename(f)
        raw_n[base] = int(len(x))
        d = pd.DataFrame({"day": base.split("-")[0], "file": base, "row": np.arange(len(x)),
                          "ts": pd.to_datetime(x["Timestamp"].astype(str).str.strip(), format="%d/%m/%Y %I:%M:%S %p", errors="coerce"),
                          "src_ip": x["Src IP"], "dst_ip": x["Dst IP"], "src_port": x["Src Port"], "dst_port": x["Dst Port"], "protocol": x["Protocol"]})
        lab = x["Label"].map(F.clean_label)
        att = lab.str.endswith(" - Attempted")
        base_lab = lab.where(~att, lab.str.replace(" - Attempted", "", regex=False))
        fam = base_lab.map(F.FAMILY_D10)
        assert not fam.isna().any(), sorted(set(base_lab[fam.isna()]))
        d["attempted"] = np.where(att, fam, "")
        d["family"] = np.where(att, "BENIGN", fam)
        fx = x[feat_cols].apply(pd.to_numeric, errors="coerce").astype("float64").replace([np.inf, -np.inf], np.nan)
        fx.columns = FEATS
        d = pd.concat([d, fx], axis=1)
        parts.append(d)
    d = pd.concat(parts, ignore_index=True)
    n0 = len(d)
    bad_ts = int(d["ts"].isna().sum())
    d = d[d["ts"].notna()].reset_index(drop=True)
    h = F.row_hash(d, FEATS)
    codes = pd.factorize(d["family"])[0]
    order = np.arange(len(d))
    keep, n_dup, n_conf, kind = F.dedup_conflicts(h, codes, order)
    stats = {"raw_rows": raw_n, "rows_total": int(n0), "bad_timestamp": bad_ts, "exact_duplicates": n_dup, "conflicting_rows": n_conf,
             "kept": int(keep.sum()), "attempted_relabelled_benign": d["attempted"][d["attempted"] != ""].value_counts().to_dict()}
    d = d[keep].reset_index(drop=True)
    d["v3split"] = ""
    d["v3period"] = -1
    for c in FEATS:
        d[c] = d[c].astype("float32")
    return d, stats


if __name__ == "__main__":
    name = sys.argv[1]
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    d, st = {"D10o": build_d10o, "D10e": build_d10e}[name]()
    d["ts"] = pd.to_datetime(d["ts"])
    st["family_counts"] = d["family"].value_counts().to_dict()
    st["seconds"] = round(time.time() - t0, 1)
    d.to_pickle(os.path.join(OUT, name + ".pkl"), compression="gzip")
    json.dump(st, open(os.path.join(RES, "B2_build_%s.json" % name), "w"), indent=1, default=str)
    print(name, len(d), st["family_counts"], st["seconds"])
