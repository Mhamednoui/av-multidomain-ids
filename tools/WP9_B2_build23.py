"""WP9 B2: stream the corrected CSE-CIC-IDS2018 (Liu et al., CNS 2022; CSECICIDS2018_improved.zip, ~36 GB uncompressed) into a compact table.

Pass 1 (resumable, one part file per member): for every row keep (feature hash, raw label, attempted flag, day order) for the GLOBAL exact-duplicate / conflict
cleaning; store the full row (76 CICFlowMeter features float32, timestamp, hash of the Flow ID = 5-tuple, label) only for attack rows and for a deterministic
1-in-10 sample of benign rows chosen by the feature hash (identical vectors share one fate, so de-duplication on the sample equals de-duplication on the full data).
Benign rows carry weight 10 in all metrics (inverse sampling probability); attack rows weight 1.
Pass 2 (assemble): global dedup / conflict removal as WP4 (earliest copy kept, conflicting rows dropped), "Attempted" flows relabelled BENIGN (authors' recommendation),
family mapping, one pickle table + stats json. The zip is read in place (python -I, never executed; no extraction).
Run (codes_v3): python -u -W ignore -I tools/WP9_B2_build23.py pass1|pass2
"""
import json, os, re, sys, time, zipfile
import numpy as np, pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from network import flows as F

EXTRA = os.path.join(ROOT, "..", "data_extra")
ZIP = os.path.join(EXTRA, "D23e_cse-cic-ids2018_improved_cns2022", "raw", "CSECICIDS2018_improved.zip")
OUT = os.path.join(EXTRA, "cache_v3", "WP9", "B2")
PARTS = os.path.join(OUT, "D23x_parts")
RES = os.path.join(ROOT, "results", "WP9")
FEATS = F.FEATURES
# source column names of the 76 features (same names as the WTMC 2021 files, positions 7..82 of the CICIDS2017 corrected header)
SRC = ["Flow Duration", "Total Fwd Packet", "Total Bwd packets", "Total Length of Fwd Packet", "Total Length of Bwd Packet", "Fwd Packet Length Max", "Fwd Packet Length Min",
       "Fwd Packet Length Mean", "Fwd Packet Length Std", "Bwd Packet Length Max", "Bwd Packet Length Min", "Bwd Packet Length Mean", "Bwd Packet Length Std", "Flow Bytes/s",
       "Flow Packets/s", "Flow IAT Mean", "Flow IAT Std", "Flow IAT Max", "Flow IAT Min", "Fwd IAT Total", "Fwd IAT Mean", "Fwd IAT Std", "Fwd IAT Max", "Fwd IAT Min", "Bwd IAT Total",
       "Bwd IAT Mean", "Bwd IAT Std", "Bwd IAT Max", "Bwd IAT Min", "Fwd PSH Flags", "Bwd PSH Flags", "Fwd URG Flags", "Bwd URG Flags", "Fwd Header Length", "Bwd Header Length",
       "Fwd Packets/s", "Bwd Packets/s", "Packet Length Min", "Packet Length Max", "Packet Length Mean", "Packet Length Std", "Packet Length Variance", "FIN Flag Count", "SYN Flag Count",
       "RST Flag Count", "PSH Flag Count", "ACK Flag Count", "URG Flag Count", "CWR Flag Count", "ECE Flag Count", "Down/Up Ratio", "Average Packet Size", "Fwd Segment Size Avg",
       "Bwd Segment Size Avg", "Fwd Bytes/Bulk Avg", "Fwd Packet/Bulk Avg", "Fwd Bulk Rate Avg", "Bwd Bytes/Bulk Avg", "Bwd Packet/Bulk Avg", "Bwd Bulk Rate Avg", "Subflow Fwd Packets",
       "Subflow Fwd Bytes", "Subflow Bwd Packets", "Subflow Bwd Bytes", "FWD Init Win Bytes", "Bwd Init Win Bytes", "Fwd Act Data Pkts", "Fwd Seg Size Min", "Active Mean", "Active Std",
       "Active Max", "Active Min", "Idle Mean", "Idle Std", "Idle Max", "Idle Min"]
assert len(SRC) == 76 == len(FEATS)
ORDER = ["Wednesday-14-02-2018.csv", "Thursday-15-02-2018.csv", "Friday-16-02-2018.csv", "Tuesday-20-02-2018.csv", "Wednesday-21-02-2018.csv", "Thursday-22-02-2018.csv",
         "Friday-23-02-2018.csv", "Wednesday-28-02-2018.csv", "Thursday-01-03-2018.csv", "Friday-02-03-2018.csv"]
RATE = 10
CHUNK = 500_000


def key(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def pass1():
    os.makedirs(PARTS, exist_ok=True)
    z = zipfile.ZipFile(ZIP)
    for day, name in enumerate(ORDER):
        p = os.path.join(PARTS, name + ".npz")
        if os.path.exists(p):
            continue
        t0 = time.time()
        H, LAB, ATT, STORE, ROWS = [], [], [], [], []
        X, TS, FH = [], [], []
        n = 0
        with z.open(name) as f:
            for ch in pd.read_csv(f, usecols=["Flow ID", "Timestamp", "Label", "Attempted Category"] + SRC, chunksize=CHUNK, low_memory=False):
                x = ch[SRC].apply(pd.to_numeric, errors="coerce").to_numpy(np.float64)
                x = np.where(np.isinf(x), np.nan, x)
                h = pd.util.hash_pandas_object(pd.DataFrame(x), index=False).to_numpy()
                lab = ch["Label"].astype(str).str.strip().to_numpy()
                att = (pd.to_numeric(ch["Attempted Category"], errors="coerce").fillna(-1).to_numpy() != -1)
                ben_like = np.array([key(l) == "benign" for l in lab]) | att
                keep = (~ben_like) | (h % RATE == 0)
                H.append(h)
                LAB.append(lab)
                ATT.append(att)
                STORE.append(keep)
                ROWS.append(np.arange(n, n + len(ch)))
                n += len(ch)
                X.append(x[keep].astype(np.float32))
                TS.append(pd.to_datetime(ch["Timestamp"][keep].astype(str).str.strip(), errors="coerce").to_numpy().astype("datetime64[ns]").astype(np.int64))
                FH.append(pd.util.hash_array(ch["Flow ID"][keep].astype(str).to_numpy(dtype=object)))
        labs = np.concatenate(LAB)
        ul, li = np.unique(labs, return_inverse=True)
        np.savez_compressed(p + ".tmp.npz", h=np.concatenate(H), lab=li.astype(np.int16), lab_names=ul, att=np.concatenate(ATT), store=np.concatenate(STORE),
                            x=np.concatenate(X), ts=np.concatenate(TS), flow_h=np.concatenate(FH), day=day)
        os.replace(p + ".tmp.npz", p)
        print(time.strftime("%H:%M:%S"), name, "rows", n, "stored", int(np.concatenate(STORE).sum()), "labels", dict(zip(ul.tolist(), np.bincount(li).tolist())), "%.0fs" % (time.time() - t0), flush=True)


FAM_KEYS = {key(k): v for k, v in {**F.FAMILY_D23, **F.FAMILY_D10}.items()}
FAM_KEYS.update({"benign": "BENIGN", "dosattackshulk": "DoS-Hulk", "dosattacksgoldeneye": "DoS-GoldenEye", "dosattacksslowloris": "DoS-Slowloris",
                 "dosattacksslowhttptest": "DoS-SlowHTTPTest", "infiltration": "Infiltration", "infilteration": "Infiltration", "bot": "Bot",
                 "ddosattackshoic": "DDoS-HOIC", "ddosattackhoic": "DDoS-HOIC", "ddosattacksloichttp": "DDoS-LOIC-HTTP", "ddosattackloicudp": "DDoS-LOIC-UDP",
                 "ddosattacksloicudp": "DDoS-LOIC-UDP", "ftpbruteforce": "FTP-Patator", "sshbruteforce": "SSH-Patator", "bruteforceweb": "Web-BruteForce",
                 "bruteforcexss": "Web-XSS", "sqlinjection": "Web-SQLi", "webattackbruteforce": "Web-BruteForce", "webattackxss": "Web-XSS", "webattacksqlinjection": "Web-SQLi"})


def fam_of(lab):
    k = key(lab).replace("attempted", "")
    return FAM_KEYS.get(k)


def pass2():
    parts = []
    for name in ORDER:
        z = np.load(os.path.join(PARTS, name + ".npz"), allow_pickle=True)
        parts.append({k: z[k] for k in z.files})
    # global cleaning on (hash, label family, attempted->benign)
    names_all = sorted(set(sum([list(p["lab_names"]) for p in parts], [])))
    fam_map = {n: fam_of(n) for n in names_all}
    unmapped = [n for n, v in fam_map.items() if v is None]
    assert not unmapped, "unmapped labels: %s" % unmapped
    fams = sorted(set(fam_map.values()))
    fcode = {f: i for i, f in enumerate(fams)}
    H, L, S = [], [], []
    for p in parts:
        fc = np.array([fcode[fam_map[n]] for n in p["lab_names"]], dtype=np.int16)[p["lab"]]
        fc = np.where(p["att"], fcode["BENIGN"], fc)
        H.append(p["h"]); L.append(fc); S.append(p["store"])
    H = np.concatenate(H); L = np.concatenate(L); S = np.concatenate(S)
    n0 = len(H)
    k1 = H ^ (L.astype(np.uint64) * np.uint64(0x9E3779B97F4A7C15))
    _, first = np.unique(k1, return_index=True)
    keep = np.zeros(n0, bool)
    keep[first] = True
    n_dup = int(n0 - keep.sum())
    hk = H[keep]
    uh, inv, cnt = np.unique(hk, return_inverse=True, return_counts=True)
    conf = np.zeros(n0, bool)
    ki = np.where(keep)[0]
    conf[ki[cnt[inv] > 1]] = True
    keep &= ~conf
    stats = {"rows_total": n0, "exact_duplicates": n_dup, "conflicting_rows": int(conf.sum()), "kept": int(keep.sum()), "benign_sample_rate": "1/%d, weight %d" % (RATE, RATE),
             "attempted_flows_relabelled_benign": int(sum(p["att"].sum() for p in parts)), "label_names": {n: fam_map[n] for n in names_all}}
    # stored rows that survive
    off, rows = 0, []
    for day, p in enumerate(parts):
        n = len(p["h"])
        kp = keep[off:off + n][p["store"]]
        fc = np.array([fcode[fam_map[n_]] for n_ in p["lab_names"]], dtype=np.int16)[p["lab"]]
        fc = np.where(p["att"], fcode["BENIGN"], fc)
        fam_st = np.array(fams, dtype=object)[fc[p["store"]]]
        att_st = np.where(p["att"][p["store"]], np.array([fam_map[n_] for n_ in p["lab_names"]], dtype=object)[p["lab"][p["store"]]], "")
        d = pd.DataFrame(p["x"][kp], columns=FEATS)
        d.insert(0, "attempted", att_st[kp])
        d.insert(0, "family", fam_st[kp])
        d.insert(0, "flow_h", p["flow_h"][kp])
        d.insert(0, "ts", pd.to_datetime(p["ts"][kp]))
        d.insert(0, "day", ORDER[day].split("-")[0] + ORDER[day].split("-")[1] + ORDER[day].split("-")[2])
        off += n
        rows.append(d)
    d = pd.concat(rows, ignore_index=True)
    bad = int(d["ts"].isna().sum())
    d = d[d["ts"].notna()].reset_index(drop=True)
    d["wt"] = np.where(d["family"] == "BENIGN", float(RATE), 1.0).astype(np.float32)
    stats["bad_timestamp_dropped"] = bad
    stats["family_counts_unweighted"] = d["family"].value_counts().to_dict()
    stats["family_counts_weighted"] = {k: float(v) for k, v in d.groupby("family")["wt"].sum().items()}
    stats["days"] = d["day"].value_counts().to_dict()
    d.to_pickle(os.path.join(OUT, "D23x.pkl"), compression="gzip")
    json.dump(stats, open(os.path.join(RES, "B2_build_D23x.json"), "w"), indent=1, default=str)
    print(stats["family_counts_unweighted"], stats["family_counts_weighted"])


if __name__ == "__main__":
    {"pass1": pass1, "pass2": pass2}[sys.argv[1]]()
