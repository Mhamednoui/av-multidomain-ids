"""WP4 S1 gate v2: D10 (GeneratedLabelledFlows) vs MachineLearningCVE (MLCVE) vs D01. Rule in notes/WP4_network.md.
Output: results/WP4/s1_gate2.json.  Run: python -u -W ignore -I tools/WP4_s1_gate2.py
"""
import glob, json, os, sys
import numpy as np, pandas as pd
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from network import flows

BASE = os.path.join(ROOT, "..", "data_extra", "D10_cicids2017_generated_flows")
D10 = os.path.join(BASE, "extracted", "TrafficLabelling")
ML = os.path.join(BASE, "MachineLearningCVE")
D01 = os.path.join(ROOT, "..", "codes", "data", "CICIDS2017_sample.csv")
GROUP = {"DoS Hulk": "DoS", "DoS GoldenEye": "DoS", "DoS slowloris": "DoS", "DoS Slowhttptest": "DoS",
         "FTP-Patator": "BruteForce", "SSH-Patator": "BruteForce",
         "Web Attack Brute Force": "WebAttack", "Web Attack XSS": "WebAttack", "Web Attack Sql Injection": "WebAttack",
         "BENIGN": "BENIGN", "Bot": "Bot", "PortScan": "PortScan", "Infiltration": "Infiltration"}
KEY = ["Flow Duration", "Total Fwd Packets", "Total Backward Packets", "Total Length of Fwd Packets", "Total Length of Bwd Packets"]


def hashes(df, cols):
    x = df[cols].apply(pd.to_numeric, errors="coerce").astype("float64").replace([np.inf, -np.inf], np.nan)
    return pd.util.hash_pandas_object(x, index=False).to_numpy()


def load(d, feats, with_dstport=False):
    out = {}
    for p in sorted(glob.glob(os.path.join(d, "*.csv"))):
        df = flows.read_csv_raw(p)
        df = df.dropna(subset=["Label"])
        df["Label"] = df["Label"].map(flows.clean_label)
        out[os.path.basename(p)] = df
    return out


def main():
    d01 = pd.read_csv(D01)
    d01.columns = [flows._norm(c) for c in d01.columns]
    feats = [c for c in d01.columns if c != "Label"]
    f = d01[feats].replace([np.inf, -np.inf], np.nan)
    const = [c for c in feats if f[c].nunique(dropna=False) <= 1]
    ft = [c for c in feats if c not in const]
    d = d01.copy(); d[feats] = f
    d = d.drop_duplicates(subset=ft + ["Label"])
    g = d.groupby(ft, dropna=False)["Label"].transform("nunique")
    clean = d[g == 1]
    print("D01 clean", len(clean), flush=True)
    ml = load(ML, feats); d10 = load(D10, feats)
    miss = [c for c in feats if any(c not in df.columns for df in ml.values())]
    print("D01 features missing in MLCVE:", miss, flush=True)
    # G1
    hc = hashes(clean, feats)
    pairs = set()
    for df in ml.values():
        pairs.update(zip(hashes(df, feats).tolist(), df["Label"].map(GROUP).fillna("?").tolist()))
    found = np.array([(h, l) in pairs for h, l in zip(hc.tolist(), clean["Label"].tolist())])
    g1 = float(found.mean())
    # G2
    g2 = {}
    ok2 = set(ml) == set(d10)
    for k in sorted(ml):
        a = ml[k]["Label"].value_counts().to_dict(); b = d10.get(k, pd.DataFrame({"Label": []}))["Label"].value_counts().to_dict()
        g2[k] = {"rows_mlcve": len(ml[k]), "rows_d10": len(d10.get(k, [])), "labels_equal": a == b,
                 "labels_mlcve": a, "labels_d10": b}
        ok2 &= (len(ml[k]) == len(d10.get(k, [])) and a == b)
    # G3
    keyset = set()
    for df in d10.values():
        keyset.update(zip(hashes(df, KEY).tolist(), df["Label"].tolist()))
    tot = hit = 0
    per = {}
    for k, df in ml.items():
        r = np.array([(h, l) in keyset for h, l in zip(hashes(df, KEY).tolist(), df["Label"].tolist())])
        per[k] = float(r.mean()); tot += len(r); hit += int(r.sum())
    g3 = hit / tot
    # extra: feature-column diff between MLCVE and D10 on key-matched, first-row-per-key
    res = {"d01_clean": len(clean), "G1_rate": g1, "G1_found": int(found.sum()), "G1_pass": g1 >= 0.99,
           "d01_features_missing_in_mlcve": miss, "G2_pass": bool(ok2), "G2_files": g2,
           "G3_rate": g3, "G3_per_file": per, "G3_pass": g3 >= 0.99}
    res["gate_met"] = bool(res["G1_pass"] and res["G2_pass"] and res["G3_pass"])
    json.dump(res, open(os.path.join(ROOT, "results", "WP4", "s1_gate2.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "G2_files"}, indent=1))
    for k, v in g2.items(): print(k, v["rows_mlcve"], v["rows_d10"], v["labels_equal"])


if __name__ == "__main__":
    main()
