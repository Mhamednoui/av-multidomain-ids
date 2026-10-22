"""WP4 S7 freeze: build the deployable network domain (network/domain.py, stack H = zero-shot, topology-free) from the D10 benign train / validation streams with the combiner chosen on
validation (combiners.pkl entry "H"), save it to results/WP4/s7_domain/ and check that it reproduces the S7 verdict alarms of the D10 test stream flow by flow.
Also writes example Evidence fixtures (results/WP4/s7_domain/example_evidence_*.json).
Usage: python -u -W ignore tools/WP4_S7_freeze.py"""
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from network.domain import STACKS, WINDOWS, NetworkDomain
from tools.WP4_S3_lib import load, stream
from tools.WP4_S7_lib import RES, S7, comb_alarm, load_combiner, load_tables, log

OUT = os.path.join(RES, "s7_domain")


def main():
    os.makedirs(OUT, exist_ok=True)
    dev3 = json.load(open(os.path.join(RES, "s3_dev_val.json")))["chosen"]
    for n, w in WINDOWS.items():
        assert dev3.get(n, 1) == w, (n, dev3.get(n), w)
    combs = pickle.load(open(os.path.join(S7, "combiners.pkl"), "rb"))
    e = combs["H"]
    d = load("D10")
    tr, vb = stream(d, "train", True), stream(d, "val", True)
    mt = (d["split"].astype(str) == "test").to_numpy()
    te = d.loc[mt].reset_index(drop=True)
    te_pos = np.flatnonzero(mt)
    te["sample_id"] = te_pos.astype(str)
    for df in (tr, vb):
        df["sample_id"] = np.arange(len(df)).astype(str)
    del d
    D = NetworkDomain("H", method=e["method"])
    D.fit(tr, vb, set_combiner=False)
    D.set_combiner(e["method"], e["threshold"], e["model"])
    assert D.comb.layer_names == list(e["names"]), (D.comb.layer_names, e["names"])
    D.save(OUT)
    log("saved", OUT, "method", D.comb.method, "threshold", D.comb.threshold)
    # ---- reproduce the S7 verdict alarms on the D10 test stage stream
    val, test, cal = load_tables()
    C = load_combiner(e)
    s_ref, al_ref = comb_alarm(C, test, cal)
    s, al, X = D.score_arrays(te)
    pos_ref = test["pos"].to_numpy()
    o = np.argsort(pos_ref)
    assert np.array_equal(pos_ref[o], te_pos), "row sets differ"
    s_ref, al_ref = s_ref[o], al_ref[o]
    chk = {"n_rows": int(len(te)), "max_abs_score_diff": float(np.abs(s - s_ref).max()), "alarm_mismatches": int((al != al_ref).sum()), "alarm_rate": float(al.mean())}
    log("freeze check", chk)
    # ---- fixtures: a slice of the PortScan window (alarmed) and a benign slice
    fam = te["family"].astype(str).to_numpy()
    idx_ps = np.flatnonzero((fam == "PortScan") & al)[:5]
    idx_b = np.flatnonzero((fam == "BENIGN") & ~al)[:3]
    sel = np.sort(np.r_[idx_ps, idx_b])
    # score a contiguous time slice around the scan so the window features are those of the stream
    t0, t1 = te["t"].iloc[idx_ps[0]] - 300, te["t"].iloc[idx_ps[0]] + 300
    sl = te[(te["t"] >= t0) & (te["t"] <= t1)].reset_index(drop=True)
    comb, per = D.score_prepared(sl)
    pick = [i for i in range(len(comb)) if comb[i].alarm][:3] + [i for i in range(len(comb)) if not comb[i].alarm][:2]
    ex = {"note": "Evidence of the frozen network domain (stack H) for flows of a 10-minute slice around a PortScan; combined + per-layer",
          "combined": [comb[i].to_dict() for i in pick], "per_layer": {n: [per[n][i].to_dict() for i in pick] for n in per}}
    json.dump(ex, open(os.path.join(OUT, "example_evidence_portscan.json"), "w"), indent=1)
    chk["fixture_flows"] = len(pick)
    chk["stack"] = "H"
    chk["layers"] = STACKS["H"]
    chk["domain_pkl_bytes"] = os.path.getsize(os.path.join(OUT, "domain.pkl"))
    json.dump(chk, open(os.path.join(OUT, "freeze_check.json"), "w"), indent=1)
    assert chk["alarm_mismatches"] == 0 and chk["max_abs_score_diff"] < 1e-9


if __name__ == "__main__":
    main()
