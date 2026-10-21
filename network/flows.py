"""Unified flow tables for CICIDS2017 (D10) and CSE-CIC-IDS2018 (D23).

Purpose: canonical column set (ids, timestamp, 76 flow features in D23 names, label, family, group),
v2-style cleaning (exact duplicates, conflicting labels) with counts, and the time split
(periods cut chronologically, gaps dropped).
Inputs: CICFlowMeter CSVs under ../data_extra (untrusted data: parsed with pandas, never executed).
Outputs: DataFrames / arrays; written to results/WP4 and ../data_extra/cache_v3/WP4 by tools/WP4_s1_build.py.
References: Sharafaldin et al. 2018 (CICIDS2017, CSE-CIC-IDS2018); cleaning idea from codes_v2/network/train.py.
"""
import re

import numpy as np
import pandas as pd

# 76 flow features, D10 (stripped header) name -> D23 name. D10 also has a 77th column
# 'Fwd Header Length.1' that is identical to 'Fwd Header Length' (checked) and is dropped.
D10_TO_D23 = {
    "Flow Duration": "Flow Duration",
    "Total Fwd Packets": "Tot Fwd Pkts",
    "Total Backward Packets": "Tot Bwd Pkts",
    "Total Length of Fwd Packets": "TotLen Fwd Pkts",
    "Total Length of Bwd Packets": "TotLen Bwd Pkts",
    "Fwd Packet Length Max": "Fwd Pkt Len Max",
    "Fwd Packet Length Min": "Fwd Pkt Len Min",
    "Fwd Packet Length Mean": "Fwd Pkt Len Mean",
    "Fwd Packet Length Std": "Fwd Pkt Len Std",
    "Bwd Packet Length Max": "Bwd Pkt Len Max",
    "Bwd Packet Length Min": "Bwd Pkt Len Min",
    "Bwd Packet Length Mean": "Bwd Pkt Len Mean",
    "Bwd Packet Length Std": "Bwd Pkt Len Std",
    "Flow Bytes/s": "Flow Byts/s",
    "Flow Packets/s": "Flow Pkts/s",
    "Flow IAT Mean": "Flow IAT Mean",
    "Flow IAT Std": "Flow IAT Std",
    "Flow IAT Max": "Flow IAT Max",
    "Flow IAT Min": "Flow IAT Min",
    "Fwd IAT Total": "Fwd IAT Tot",
    "Fwd IAT Mean": "Fwd IAT Mean",
    "Fwd IAT Std": "Fwd IAT Std",
    "Fwd IAT Max": "Fwd IAT Max",
    "Fwd IAT Min": "Fwd IAT Min",
    "Bwd IAT Total": "Bwd IAT Tot",
    "Bwd IAT Mean": "Bwd IAT Mean",
    "Bwd IAT Std": "Bwd IAT Std",
    "Bwd IAT Max": "Bwd IAT Max",
    "Bwd IAT Min": "Bwd IAT Min",
    "Fwd PSH Flags": "Fwd PSH Flags",
    "Bwd PSH Flags": "Bwd PSH Flags",
    "Fwd URG Flags": "Fwd URG Flags",
    "Bwd URG Flags": "Bwd URG Flags",
    "Fwd Header Length": "Fwd Header Len",
    "Bwd Header Length": "Bwd Header Len",
    "Fwd Packets/s": "Fwd Pkts/s",
    "Bwd Packets/s": "Bwd Pkts/s",
    "Min Packet Length": "Pkt Len Min",
    "Max Packet Length": "Pkt Len Max",
    "Packet Length Mean": "Pkt Len Mean",
    "Packet Length Std": "Pkt Len Std",
    "Packet Length Variance": "Pkt Len Var",
    "FIN Flag Count": "FIN Flag Cnt",
    "SYN Flag Count": "SYN Flag Cnt",
    "RST Flag Count": "RST Flag Cnt",
    "PSH Flag Count": "PSH Flag Cnt",
    "ACK Flag Count": "ACK Flag Cnt",
    "URG Flag Count": "URG Flag Cnt",
    "CWE Flag Count": "CWE Flag Count",
    "ECE Flag Count": "ECE Flag Cnt",
    "Down/Up Ratio": "Down/Up Ratio",
    "Average Packet Size": "Pkt Size Avg",
    "Avg Fwd Segment Size": "Fwd Seg Size Avg",
    "Avg Bwd Segment Size": "Bwd Seg Size Avg",
    "Fwd Avg Bytes/Bulk": "Fwd Byts/b Avg",
    "Fwd Avg Packets/Bulk": "Fwd Pkts/b Avg",
    "Fwd Avg Bulk Rate": "Fwd Blk Rate Avg",
    "Bwd Avg Bytes/Bulk": "Bwd Byts/b Avg",
    "Bwd Avg Packets/Bulk": "Bwd Pkts/b Avg",
    "Bwd Avg Bulk Rate": "Bwd Blk Rate Avg",
    "Subflow Fwd Packets": "Subflow Fwd Pkts",
    "Subflow Fwd Bytes": "Subflow Fwd Byts",
    "Subflow Bwd Packets": "Subflow Bwd Pkts",
    "Subflow Bwd Bytes": "Subflow Bwd Byts",
    "Init_Win_bytes_forward": "Init Fwd Win Byts",
    "Init_Win_bytes_backward": "Init Bwd Win Byts",
    "act_data_pkt_fwd": "Fwd Act Data Pkts",
    "min_seg_size_forward": "Fwd Seg Size Min",
    "Active Mean": "Active Mean",
    "Active Std": "Active Std",
    "Active Max": "Active Max",
    "Active Min": "Active Min",
    "Idle Mean": "Idle Mean",
    "Idle Std": "Idle Std",
    "Idle Max": "Idle Max",
    "Idle Min": "Idle Min",
}
FEATURES = list(D10_TO_D23.values())          # canonical feature order (D23 names)
D10_ID_RENAME = {"Source IP": "src_ip", "Source Port": "src_port", "Destination IP": "dst_ip",
                 "Destination Port": "dst_port", "Protocol": "protocol", "Timestamp": "ts_raw", "Label": "label_raw"}
# D23: the 80-column files have only Dst Port / Protocol / Timestamp as ids; the Tuesday-20-02 file has 84 columns
# = the same 80 plus these four id columns.
D23_TUE_EXTRA = {"Flow ID": "flow_id", "Src IP": "src_ip", "Src Port": "src_port", "Dst IP": "dst_ip"}
D23_ID_RENAME = {"Dst Port": "dst_port", "Protocol": "protocol", "Timestamp": "ts_raw", "Label": "label_raw", **D23_TUE_EXTRA}

# fine attack family (cross-dataset names) and coarse group (v2 classes + DDoS + Heartbleed)
FAMILY_D10 = {"BENIGN": "BENIGN", "DoS Hulk": "DoS-Hulk", "DoS GoldenEye": "DoS-GoldenEye", "DoS slowloris": "DoS-Slowloris",
              "DoS Slowhttptest": "DoS-SlowHTTPTest", "Heartbleed": "Heartbleed", "FTP-Patator": "FTP-Patator",
              "SSH-Patator": "SSH-Patator", "Web Attack - Brute Force": "Web-BruteForce", "Web Attack - XSS": "Web-XSS",
              "Web Attack - Sql Injection": "Web-SQLi", "Infiltration": "Infiltration", "Bot": "Bot",
              "DDoS": "DDoS-LOIC-HTTP", "PortScan": "PortScan"}
FAMILY_D23 = {"Benign": "BENIGN", "Bot": "Bot", "DoS attacks-Hulk": "DoS-Hulk", "DoS attacks-SlowHTTPTest": "DoS-SlowHTTPTest",
              "DoS attacks-GoldenEye": "DoS-GoldenEye", "DoS attacks-Slowloris": "DoS-Slowloris",
              "Brute Force -Web": "Web-BruteForce", "Brute Force -XSS": "Web-XSS", "SQL Injection": "Web-SQLi",
              "FTP-BruteForce": "FTP-Patator", "SSH-Bruteforce": "SSH-Patator", "DDoS attacks-LOIC-HTTP": "DDoS-LOIC-HTTP",
              "DDOS attack-LOIC-UDP": "DDoS-LOIC-UDP", "DDOS attack-HOIC": "DDoS-HOIC", "Infilteration": "Infiltration"}
GROUP = {"BENIGN": "BENIGN", "Bot": "Bot", "FTP-Patator": "BruteForce", "SSH-Patator": "BruteForce", "Infiltration": "Infiltration",
         "PortScan": "PortScan", "Heartbleed": "Heartbleed", "Web-BruteForce": "WebAttack", "Web-XSS": "WebAttack",
         "Web-SQLi": "WebAttack", "DDoS-LOIC-HTTP": "DDoS", "DDoS-LOIC-UDP": "DDoS", "DDoS-HOIC": "DDoS",
         "DoS-Hulk": "DoS", "DoS-GoldenEye": "DoS", "DoS-Slowloris": "DoS", "DoS-SlowHTTPTest": "DoS"}


def _norm(c):
    return re.sub(r"\s+", " ", str(c).strip())


def clean_label(s):
    """Strip; replace non-ASCII dashes / replacement chars (D10 Web Attack labels) by '-'; collapse spaces."""
    s = str(s).replace("�", "-")
    s = re.sub(r"[^\x00-\x7f]", "-", s)
    s = re.sub(r"-+", "-", s)
    return re.sub(r"\s+", " ", s).strip()


def map_family(labels, dataset):
    """Label strings -> fine family names. Unknown labels raise (no silent default)."""
    m = FAMILY_D10 if dataset == "D10" else FAMILY_D23
    lab = pd.Series(labels).map(clean_label)
    fam = lab.map(m)
    if fam.isna().any():
        raise ValueError("unknown labels: %s" % sorted(set(lab[fam.isna()])))
    return fam.to_numpy()


def parse_ts(s, pm_fix):
    """Timestamps -> datetime64. D10: 'd/m/yyyy H:MM' (Monday: with seconds), no AM/PM: hours 1-7 mean
    afternoon (pm_fix=True adds 12 h). D23: 'dd/mm/yyyy HH:MM:SS', also without AM/PM (hours 1-5 hold the afternoon attacks). Unparseable -> NaT."""
    s = pd.Series(s).astype(str).str.strip()
    t = pd.to_datetime(s, format="%d/%m/%Y %H:%M:%S", errors="coerce")
    t = t.fillna(pd.to_datetime(s, format="%d/%m/%Y %H:%M", errors="coerce"))
    return fix_pm(t) if pm_fix else t


def fix_pm(t):
    """Add 12 h to timestamps with hour 1-7 (12-hour clock without AM/PM; true for D10 and D23, checked on attack windows)."""
    t = pd.Series(t)
    return t + pd.to_timedelta(((t.dt.hour >= 1) & (t.dt.hour <= 7)).astype(int) * 12, unit="h")


def row_hash(df, cols):
    """64-bit hash of the float64 feature values (inf -> NaN as in v2)."""
    x = df[cols].apply(pd.to_numeric, errors="coerce").astype("float64").replace([np.inf, -np.inf], np.nan)
    return pd.util.hash_pandas_object(x, index=False).to_numpy()


def dedup_conflicts(h, label_code, order):
    """v2 cleaning on feature hashes. Returns (keep mask, n_exact_dup, n_conflict_rows, drop_kind) where drop_kind is
    0 kept, 1 exact duplicate, 2 conflicting label. Exact duplicates (same features and label): the earliest by
    `order` is kept. Then every remaining row whose features occur with more than one label is dropped (all of them)."""
    n = len(h)
    idx = np.argsort(order, kind="stable")
    key = pd.DataFrame({"h": h[idx], "l": label_code[idx]})
    dup_sorted = key.duplicated(keep="first").to_numpy()
    kind = np.zeros(n, dtype=np.int8)
    kind[idx[dup_sorted]] = 1
    keep = kind == 0
    k2 = pd.DataFrame({"h": h[keep], "l": label_code[keep]})
    nun = k2.groupby("h")["l"].transform("nunique").to_numpy()
    conf = np.where(keep)[0][nun > 1]
    kind[conf] = 2
    return kind == 0, int(dup_sorted.sum()), int(len(conf)), kind


def attack_windows(ts, fam, min_flows=30, gap_min=30.0):
    """Attack windows per family: timestamp clusters (a gap > gap_min minutes separates clusters; clusters with
    fewer than min_flows flows are ignored), each trimmed to its 1st-99th percentile. Returns [(start, end, family)]."""
    out = []
    df = pd.DataFrame({"t": np.asarray(ts).astype("datetime64[ns]"), "f": np.asarray(fam)})
    df = df[df["f"] != "BENIGN"]
    for f, g in df.groupby("f"):
        t = np.sort(g["t"].to_numpy())
        cut = np.where(np.diff(t) > np.timedelta64(int(gap_min * 60), "s"))[0] + 1
        for c in np.split(t, cut):
            if len(c) >= min_flows:
                lo, hi = np.quantile(c.astype("int64"), [0.01, 0.99]).astype("int64")
                out.append((np.datetime64(int(lo), "ns"), np.datetime64(int(hi), "ns"), f))
    return out


def time_split(ts, fam, frac=(0.6, 0.2, 0.2), gap_min=1, short_min=5):
    """Split ONE day's flows by time. Periods = attack windows + the benign stretches between / around them.
    Each period is cut at flow-count quantiles (time-ordered) into train / val / test (frac) with `gap_min` minutes dropped before each
    boundary. Periods shorter than `short_min` minutes go entirely to train. NaT -> 'gap'.
    Returns (split array of str, period id array)."""
    tsv = pd.Series(ts).reset_index(drop=True)
    fam = np.asarray(fam)
    n = len(tsv)
    split = np.full(n, "gap", dtype=object)
    per = np.full(n, -1, dtype=int)
    ok = tsv.notna().to_numpy()
    if not ok.any():
        return split, per
    idx_ok = np.where(ok)[0]
    tv = tsv[ok].to_numpy().astype("datetime64[ns]")
    wins = sorted(attack_windows(tv, fam[ok]), key=lambda w: w[0])
    edges, cur = [], tv.min()
    for (a, b, f) in wins:
        a = max(a, cur)
        if b <= a:
            continue
        if a > cur:
            edges.append((cur, a))
        edges.append((a, b))
        cur = b
    end = tv.max() + np.timedelta64(1, "s")
    if end > cur:
        edges.append((cur, end))
    g = np.timedelta64(int(gap_min * 60), "s")
    for pid, (a, b) in enumerate(edges):
        m = (tv >= a) & (tv < b)
        ii = idx_ok[m]
        per[ii] = pid
        if (b - a) / np.timedelta64(1, "m") < short_min:
            split[ii] = "train"
            continue
        tt = tv[m]
        # cut points = flow-count quantiles of the period (bursty attacks: clock-time cuts left val nearly empty)
        q = np.quantile(tt.astype("int64"), [frac[0], frac[0] + frac[1]]).astype("int64")
        c1, c2 = np.datetime64(int(q[0]), "ns"), np.datetime64(int(q[1]), "ns")
        s = np.full(len(tt), "gap", dtype=object)
        s[tt < c1 - g] = "train"
        s[(tt >= c1) & (tt < c2 - g)] = "val"
        s[tt >= c2] = "test"
        split[ii] = s
    return split, per
