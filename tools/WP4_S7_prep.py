"""WP4 S7 prep: one score table per D10 split (val, test) over the S3-S6 STAGE stream rows with the raw score of every layer of the S7 stacks.
Layers tcp_flags, scan, trw, bruteforce, dos_rate, slow, beacon, l3_service, l3_ae are read from the S6 caches (fitted / calibrated in S3-S6, nothing re-chosen);
net.l4_xgb is scored with the saved S6 model (calibrated on the de-duplicated benign validation rows as in S6);
topology layers net.allow_service / net.allow_pair (S2 classes, S2 parameters) are fitted on the benign train STAGE stream and calibrated on the benign val stream.
Label variants: 'fam' = published family; 'fam_corr' = Bot correction from the dataset documentation (published BENIGN flows between the five documented Ares victims
192.168.10.5/.8/.9/.14/.15 and the C2 205.174.165.73 port 8080, either direction, are relabelled Bot; never from a model output).
Output: ../data_extra/cache_v3/WP4/S7/d10_val.pkl, d10_test.pkl, cal.pkl; results/WP4/s7_prep.json. Usage: python -u -W ignore tools/WP4_S7_prep.py"""
import glob
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd
import xgboost as xgb

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common.config import BUDGET_DOMAIN
from network import l1
from network.flows import FEATURES
from network.l4 import XGBNet
from tools.WP4_S6_lib import COLS, feat, load_s6, sel
from tools.WP4_S7_lib import RES, S6, S7, log

VICTIMS = {"192.168.10.5", "192.168.10.8", "192.168.10.9", "192.168.10.14", "192.168.10.15"}
C2 = "205.174.165.73"
C2_PORT = 8080
STAGE = os.path.join(S6, "..", "D10", "stage")


def bot_rule_keys():
    """Set of 'file|row' keys of all stage flows matching the documented Bot rule (any label)."""
    keys, n_by_file = [], {}
    for p in sorted(glob.glob(os.path.join(STAGE, "*.pkl"))):
        d = pd.read_pickle(p, compression="gzip")[["file", "row", "src_ip", "dst_ip", "src_port", "dst_port"]]
        s, t = d["src_ip"].astype(str), d["dst_ip"].astype(str)
        sp = pd.to_numeric(d["src_port"], errors="coerce")
        dp = pd.to_numeric(d["dst_port"], errors="coerce")
        m = (s.isin(VICTIMS) & (t == C2) & (dp == C2_PORT)) | ((s == C2) & (sp == C2_PORT) & t.isin(VICTIMS))
        k = (d.loc[m, "file"].astype(str) + "|" + d.loc[m, "row"].astype(str))
        keys.append(k)
        n_by_file[str(d["file"].iloc[0])] = int(m.sum())
    return set(pd.concat(keys)), n_by_file


def feat_pos(X, pos):
    o = np.argsort(pos)
    arr = np.empty((len(pos), len(COLS)), np.float32)
    arr[o] = np.asarray(X[np.asarray(pos)[o]])[:, [FEATURES.index(c) for c in COLS]]
    return pd.DataFrame(arr, columns=COLS)


def main():
    d, X = load_s6()
    dev = json.load(open(os.path.join(RES, "s6_dev_val.json")))
    chosen = dev["chosen"]
    cal = pickle.load(open(os.path.join(S6, "base_cal.pkl"), "rb"))
    val = pd.read_pickle(os.path.join(S6, "base_val.pkl"))
    test = pd.read_pickle(os.path.join(S6, "base_test.pkl"))
    log("val", len(val), "test", len(test))
    for df in (val, test):
        df["fam"] = df["family"].astype(str)
        df["in_final"] = d["in_final"].to_numpy()[df["pos"].to_numpy()]
        df["day"] = df["day"].astype(str)
        df["split"] = df["split"].astype(str)
    # ---- L4
    L = XGBNet(params=chosen["params"], n_trees=chosen["n_trees"])
    L.model = xgb.XGBClassifier()
    L.model.load_model(os.path.join(S6, "l4_model.json"))
    L.best_n_trees = int(chosen["n_trees"])
    mvb = sel(d, "val", benign_only=True)
    L.calibrate(feat(d, X, mvb), BUDGET_DOMAIN)
    cal["net.l4_xgb"] = (L.calibrator, float(L.threshold), "s_net.l4_xgb")
    for df in (val, test):
        df["s_net.l4_xgb"] = L.raw_scores(feat_pos(X, df["pos"].to_numpy()))
    log("L4 scored; threshold (calibrated)", L.threshold)
    # ---- topology layers on the stage streams
    sp_ = d["sp"].to_numpy()
    famall = d["fam"].to_numpy()
    aud = d["audit"].to_numpy()

    def tf(mask):
        f = d.loc[mask, ["src_id", "dst_id", "dst_port", "protocol"]].rename(columns={"src_id": "src_ip", "dst_id": "dst_ip"}).reset_index(drop=True)
        return f

    trb, vab = tf((sp_ == "train") & (famall == "BENIGN") & ~aud), tf((sp_ == "val") & (famall == "BENIGN") & ~aud)
    for cls in (l1.AllowService, l1.AllowPair):
        T = cls().fit(trb)
        T.calibrate(vab, BUDGET_DOMAIN)
        cal[T.name] = (T.calibrator, float(T.threshold), "s_" + T.name)
        for df in (val, test):
            df["s_" + T.name] = T.raw_scores(d.iloc[df["pos"].to_numpy()][["src_id", "dst_id", "dst_port", "protocol"]].rename(
                columns={"src_id": "src_ip", "dst_id": "dst_ip"}).reset_index(drop=True))
        log("topology", T.name, "known hosts", len(T.known), "threshold", T.threshold)
    # ---- Bot label correction (evaluation side)
    keys, n_by_file = bot_rule_keys()
    info = {"rule_matches_by_file": n_by_file, "rule_matches_total": len(keys)}
    for nm, df in (("val", val), ("test", test)):
        k = d["file"].astype(str).to_numpy()[df["pos"].to_numpy()].astype(object) + "|" + d["row"].astype(str).to_numpy()[df["pos"].to_numpy()].astype(object)
        hit = pd.Series(k).isin(keys).to_numpy()
        df["bot_rule"] = hit
        fam = df["fam"].to_numpy()
        df["fam_corr"] = np.where(hit & (fam == "BENIGN"), "Bot", fam)
        info[nm] = {"rule_matches": int(hit.sum()), "of_which_published_bot": int((hit & (fam == "Bot")).sum()),
                    "relabelled_benign_to_bot": int((hit & (fam == "BENIGN")).sum()), "published_bot": int((fam == "Bot").sum()),
                    "rule_matches_other_attack_labels": {f: int((hit & (fam == f)).sum()) for f in sorted(set(fam[hit]) - {"BENIGN", "Bot"})},
                    "relabelled_in_audit_file": int((hit & (fam == "BENIGN") & df["audit"].to_numpy()).sum())}
        log(nm, info[nm])
    keep_val = ["pos", "fam", "fam_corr", "bot_rule", "day", "period", "t", "audit", "in_final", "split"] + sorted(c for c in val.columns if c.startswith("s_"))
    val[keep_val].to_pickle(os.path.join(S7, "d10_val.pkl"))
    test[keep_val].to_pickle(os.path.join(S7, "d10_test.pkl"))
    pickle.dump(cal, open(os.path.join(S7, "cal.pkl"), "wb"))
    info["layers"] = sorted(cal)
    info["thresholds"] = {k: v[1] for k, v in cal.items()}
    json.dump(info, open(os.path.join(RES, "s7_prep.json"), "w"), indent=1)
    log("saved", sorted(cal))


if __name__ == "__main__":
    main()
