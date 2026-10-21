"""WP4 S1 gate: is the D10 unofficial mirror consistent with D01 (v2 sample from the official files)?
Rule written in notes/WP4_network.md before running. Output: results/WP4/s1_gate_d10_vs_d01.json
Run from codes_v3: python -u -W ignore -I tools/WP4_s1_gate.py
"""
import glob, json, os, sys
import numpy as np, pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from network import flows

D01 = os.path.join(ROOT, "..", "codes", "data", "CICIDS2017_sample.csv")
D10 = os.path.join(ROOT, "..", "data_extra", "D10_cicids2017_generated_flows", "extracted", "TrafficLabelling")
GROUP = {"DoS Hulk": "DoS", "DoS GoldenEye": "DoS", "DoS slowloris": "DoS", "DoS Slowhttptest": "DoS",
         "FTP-Patator": "BruteForce", "SSH-Patator": "BruteForce",
         "Web Attack Brute Force": "WebAttack", "Web Attack XSS": "WebAttack", "Web Attack Sql Injection": "WebAttack",
         "BENIGN": "BENIGN", "Bot": "Bot", "PortScan": "PortScan", "Infiltration": "Infiltration"}


def hashes(df, feats):
    x = df[feats].apply(pd.to_numeric, errors="coerce").astype("float64").replace([np.inf, -np.inf], np.nan)
    return pd.util.hash_pandas_object(x, index=False).to_numpy()


def main():
    d01 = pd.read_csv(D01)
    d01.columns = [flows._norm(c) for c in d01.columns]
    feats = [c for c in d01.columns if c != "Label"]
    n0 = len(d01)
    f = d01[feats].replace([np.inf, -np.inf], np.nan)
    d01 = d01.drop_duplicates(subset=feats + ["Label"]) if False else d01
    # v2 cleaning (copied from codes_v2/network/train.py)
    const = [c for c in feats if f[c].nunique(dropna=False) <= 1]
    ft = [c for c in feats if c not in const]
    d = d01.copy(); d[feats] = f
    d = d.drop_duplicates(subset=ft + ["Label"]); n_dup = n0 - len(d)
    g = d.groupby(ft, dropna=False)["Label"].transform("nunique")
    n_conf = int((g > 1).sum()); clean = d[g == 1]
    print("D01 v2 reproduce:", n0, n_dup, n_conf, len(clean), flush=True)

    h01_all = hashes(d01, feats); h01_clean = hashes(clean, feats)
    pairs, hs = set(), set()
    n10 = 0
    for p in sorted(glob.glob(os.path.join(D10, "*.csv"))):
        df = flows.read_csv_raw(p)
        df = df.dropna(subset=["Label"])
        df["Label"] = df["Label"].map(flows.clean_label)
        h = hashes(df, feats)
        n10 += len(df)
        hs.update(h.tolist())
        lab = df["Label"].map(GROUP).fillna("?").to_numpy()
        pairs.update(zip(h.tolist(), lab.tolist()))
        print(os.path.basename(p), len(df), flush=True)
    def rate(h, labels):
        feat_only = np.array([x in hs for x in h])
        with_lab = np.array([(x, l) in pairs for x, l in zip(h.tolist(), labels)])
        return feat_only, with_lab
    fo_c, wl_c = rate(h01_clean, clean["Label"].tolist())
    fo_a, wl_a = rate(h01_all, d01["Label"].tolist())
    miss = clean[~wl_c]["Label"].value_counts().to_dict()
    res = {"d10_labelled_rows": n10, "d01_raw": n0, "d01_dup_removed": n_dup, "d01_conflict_removed": n_conf,
           "d01_clean": len(clean), "d01_const_cols_removed": const,
           "clean_features_only_rate": float(fo_c.mean()), "clean_features_and_label_rate": float(wl_c.mean()),
           "clean_found": int(wl_c.sum()), "raw_features_only_rate": float(fo_a.mean()),
           "raw_features_and_label_rate": float(wl_a.mean()), "clean_missing_by_label": miss,
           "gate_met": bool(wl_c.mean() >= 0.99)}
    json.dump(res, open(os.path.join(ROOT, "results", "WP4", "s1_gate_d10_vs_d01.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
