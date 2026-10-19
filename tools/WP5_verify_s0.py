"""WP5 S0: verify downloaded D12 (VeReMi Extension) and D14 (Tampa BSM sample).

Inputs: ../data_extra/D12_veremi_extension/mixalldata_clean.csv, ../data_extra/D14_tampa_bsm/bsm_sample.csv
Outputs: results/WP5/s0_data_check.json
Run with python -I -u -W ignore from codes_v3 (data is untrusted: read only).
"""
import json
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D12 = os.path.join(ROOT, "..", "data_extra", "D12_veremi_extension", "mixalldata_clean.csv")
D14 = os.path.join(ROOT, "..", "data_extra", "D14_tampa_bsm", "bsm_sample.csv")
OUT = os.path.join(ROOT, "results", "WP5", "s0_data_check.json")


def d12():
    df = pd.read_csv(D12)
    res = {"rows": int(len(df)), "columns": list(df.columns)}
    for c in ("class", "attack", "attackerType", "label"):
        if c in df.columns:
            res["label_col"] = c
            res["label_counts"] = {str(k): int(v) for k, v in df[c].value_counts().items()}
    for c in ("sender", "senderPseudo", "receiver", "sim", "simulation"):
        if c in df.columns:
            res["n_unique_" + c] = int(df[c].nunique())
    num = df.select_dtypes("number")
    res["describe"] = {c: [float(num[c].min()), float(num[c].max())] for c in num.columns}
    res["nan_counts"] = {c: int(v) for c, v in df.isna().sum().items() if v}
    return res


def d14():
    df = pd.read_csv(D14, low_memory=False)
    res = {"rows": int(len(df)), "columns": list(df.columns)}
    res["n_vehicle_ids"] = int(df["coreData_id"].nunique())
    t = pd.to_datetime(df["metadata_recordGeneratedAt"], errors="coerce", utc=True)
    res["t_min"], res["t_max"] = str(t.min()), str(t.max())
    res["n_days"] = int(t.dt.date.nunique())
    res["msgs_per_day"] = {str(k): int(v) for k, v in t.dt.date.value_counts().sort_index().items()}
    for c in ("coreData_lat", "coreData_long", "coreData_speed", "coreData_heading", "coreData_secMark"):
        res[c] = [float(df[c].min()), float(df[c].max()), int(df[c].isna().sum())]
    cnt = df.groupby("coreData_id").size()
    res["msgs_per_vehicle"] = {"median": float(cnt.median()), "max": int(cnt.max()), "ge_100": int((cnt >= 100).sum())}
    res["bsm_source"] = {str(k): int(v) for k, v in df["metadata_bsmSource"].value_counts().items()}
    return res


if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out = {"D12": d12(), "D14": d14()}
    json.dump(out, open(OUT, "w"), indent=1)
    print(json.dumps(out, indent=1)[:6000])
