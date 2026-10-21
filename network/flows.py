"""Unified flow tables for CICIDS2017 (D10) and CSE-CIC-IDS2018 (D23).

Purpose: read the published CICFlowMeter CSVs, give them one canonical column set
(ids, timestamp, 77 flow features, label), clean them as in v2 (empty / repeated-header rows,
exact duplicates, conflicting labels) and count every step.
Inputs: CSV files under ../data_extra (untrusted data: parsed with pandas only, never executed).
Outputs: DataFrames; counts as dicts (written to results/WP4/ by tools/WP4_s1_build.py).
References: Sharafaldin et al. 2018 (CICIDS2017); v2 cleaning in codes_v2/network/train.py (copied idea).
"""
import re

import numpy as np
import pandas as pd

ID_COLS = ["Flow ID", "Src IP", "Src Port", "Dst IP", "Dst Port", "Protocol", "Timestamp"]

# D10 header -> canonical (after strip). D10 uses Source/Destination, D23 (80-col files) has no ids.
D10_RENAME = {"Source IP": "Src IP", "Source Port": "Src Port", "Destination IP": "Dst IP", "Destination Port": "Dst Port"}

# D23 Tuesday-20-02 file: 84 columns with the D10 style names. Explicit map to the canonical
# (80-column D23) names. Names that already match are listed too, so the test can check all 84.
D23_TUE_MAP = {
    "Flow ID": "Flow ID", "Src IP": "Src IP", "Src Port": "Src Port", "Dst IP": "Dst IP", "Dst Port": "Dst Port",
    "Protocol": "Protocol", "Timestamp": "Timestamp", "Flow Duration": "Flow Duration",
    "Tot Fwd Pkts": "Tot Fwd Pkts", "Tot Bwd Pkts": "Tot Bwd Pkts",
    "TotLen Fwd Pkts": "TotLen Fwd Pkts", "TotLen Bwd Pkts": "TotLen Bwd Pkts",
}


def _norm(c):
    return re.sub(r"\s+", " ", str(c).strip())


def clean_label(s):
    """Strip and replace non-ASCII dashes (D10 Web Attack labels contain one) by '-'."""
    s = str(s).replace("\ufffd", "-").replace("\u2013", "-").replace("\u2014", "-")
    s = re.sub(r"[^\x00-\x7f]", "-", s)
    return re.sub(r"\s+", " ", s).strip()


def read_csv_raw(path):
    """Read a CICFlowMeter CSV as strings-free numeric-friendly frame; header names stripped.
    Non-UTF-8 bytes (D10 Web Attack labels) are replaced, not fatal."""
    df = pd.read_csv(path, encoding="utf-8", encoding_errors="replace", low_memory=False,
                     dtype={"Label": str, " Label": str, "Flow ID": str, " Source IP": str,
                            " Destination IP": str, "Src IP": str, "Dst IP": str, " Timestamp": str, "Timestamp": str})
    df.columns = [_norm(c) for c in df.columns]
    return df


def d10_feature_names(cols):
    """Feature columns of a stripped D10 header: everything except ids and Label (77 incl. the
    duplicated 'Fwd Header Length.1' that CICFlowMeter-V3 writes)."""
    ids = {"Flow ID", "Source IP", "Source Port", "Destination IP", "Destination Port", "Protocol", "Timestamp", "Label"}
    return [c for c in cols if c not in ids]
