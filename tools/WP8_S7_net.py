"""WP8 S7 network: the frozen v3 stack H (results/WP4/s7_domain, batch NetworkDomain) and the frozen v3.1 streams (F1 = Stream31Final, tick-final 60 s, primary; RC5 = Stream31 with carry, labelled variant;
objects fitted and frozen in S4: results/WP8/S4/parts/stream31_{F1,RC5}.pkl) on the D10 TEST split (H31 'network re-used', exposure 7 -> n+1; the WP4 time split, flows sorted (minute, file, row) as in S4).
Metrics as S4: stack H macro over the 11 families at the frozen alarm rule, FA on the benign headline (BENIGN minus the audited Infiltration file), paired bootstrap over 10-min blocks (B = 2000, seed 31),
flow-level Evidence delay (v3 NetworkRunner: 5-minute bin close; F1: minute close; RC5: flow arrival), alarm lag. Also the per-minute host view (host 49, as WP8_S2_build.stage_net) for the system composites:
raw score / alarm per 60 s tick for v3 (placed in the flow minute, hold 0: the v3 runner delivers it at the bin close), F1 (held one minute) and RC5 (hold 0).
`--split val` reruns the whole path on D10 VALIDATION rows (dry run, output to the scratchpad): v3 macro / F1 / RC5 must reproduce results/WP8/S4/s4_val_candidates.json.
Output (test): results/WP8/S7/network.json, results/WP8/scores/S7/network_test.npz, ../data_extra/cache_v3/WP8/S7/net.pkl. Run: python -u -W ignore tools/WP8_S7_net.py [--split test|val] [--out DIR]"""
import argparse
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S7_lib as S7

import numpy as np
import pandas as pd

import WP8_S4_eval as E4

from network.domain import NetworkDomain
from network.stream31 import Stream31

STAGE = S7.DATA_EXTRA / "cache_v3" / "WP4" / "S3" / "D10_stage.pkl"
HOST = 49


def load_split(split):
    d = pd.read_pickle(STAGE)
    d["audit"] = d["file"].astype(str).str.contains(E4.AUDIT_FILE).to_numpy()
    d["fam"] = d["family"].astype(str)
    v = d[d["split"].astype(str) == split].copy()
    del d
    v = v.sort_values(["minute", "file", "row"], kind="stable").reset_index(drop=True)
    v["fid"] = v["file"].astype(str).astype("category").cat.codes
    v["blk"] = v["day"].astype(str) + "|" + v["period"].astype(str)
    return v


def host_series(v, scores, name):
    """Per-block host-49 minute ticks as WP8_S2_build.stage_net: score / alarm per 60 s tick, F1 held one minute, v3 and RC5 placed in the flow minute."""
    out = []
    for b in sorted(v["blk"].unique()):
        idx = np.flatnonzero((v["blk"].to_numpy() == b) & ((v["src_id"].to_numpy() == HOST) | (v["dst_id"].to_numpy() == HOST)))
        if not len(idx):
            continue
        mins = v["minute"].to_numpy()[idx].astype(np.int64)
        fam = v["fam"].to_numpy()[idx].astype(object)
        att = fam != "BENIGN"
        u, inv = np.unique(mins, return_inverse=True)
        nmin = int(u.max() - u.min()) + 2
        jf = (u - u.min()).astype(int)[inv]
        rec = {"group": b, "name": b, "day": b.split("|")[0], "kind": "attack" if att.any() else "clean", "host_flows": int(len(idx)), "audit_flows": int(v["audit"].to_numpy()[idx].sum())}
        labm = np.zeros(nmin, bool)
        famm = np.full(nmin, "", object)
        np.logical_or.at(labm, jf, att)
        j = (u - u.min()).astype(int)
        famm[j] = pd.Series(np.where(att, fam, "")).groupby(inv).agg(lambda s: next((x for x in s.value_counts().index if x), "")).to_numpy()
        cnt = np.bincount(jf, minlength=nmin).astype(np.float32)
        for tag, hold in (("F1", 1), ("RC5", 0), ("V3", 0)):
            sc, al = scores[tag]
            S = np.zeros(nmin, np.float32)
            A = np.zeros(nmin, bool)
            np.maximum.at(S, jf, sc[idx].astype(np.float32))
            np.logical_or.at(A, jf, al[idx].astype(bool))
            Sh, Ah, lh, fh, ch = np.zeros(nmin, np.float32), np.zeros(nmin, bool), np.zeros(nmin, bool), np.full(nmin, "", object), np.zeros(nmin, np.float32)
            Sh[hold:], Ah[hold:], lh[hold:], fh[hold:], ch[hold:] = S[:nmin - hold], A[:nmin - hold], labm[:nmin - hold], famm[:nmin - hold], cnt[:nmin - hold]
            rec[tag] = {"score": np.repeat(Sh, 60), "dom_alarm": np.repeat(Ah, 60), "label": np.repeat(lh, 60), "fam": np.repeat(fh, 60), "count": np.repeat(ch, 60)}
        rec["n"] = nmin * 60
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    test = a.split == "test"
    out = Path(a.out) if a.out else (S7.OUT if test else None)
    assert test or a.out, "--split val needs --out (scratch folder)"
    sc_dir = S7.SCORES if test else out
    S7.journal("S7", f"network {a.split}: start (v3 batch, F1, RC5)", f"out {out}")
    if test:
        S7.open_guard()
    v = load_split(a.split)
    vb = None
    fam = v["fam"].to_numpy()
    print("flows", len(v), {f: int((fam == f).sum()) for f in E4.EVAL11}, flush=True)
    dom = NetworkDomain.load(E4.FROZEN)
    s3, a3, X3 = dom.score_arrays(v)
    F1 = Stream31.load(str(S7.ROOT / "results" / "WP8" / "S4" / "parts" / "stream31_F1.pkl"))
    RC5 = Stream31.load(str(S7.ROOT / "results" / "WP8" / "S4" / "parts" / "stream31_RC5.pkl"))
    s1, a1, X1, _ = F1.score_table(v)
    s5, a5, X5, _ = RC5.score_table(v)
    d3, d1, d5 = E4.emission_delay(v, 5), E4.emission_delay(v, 1), np.zeros(len(v))
    res = {"material": f"D10 {a.split} split, flows sorted (minute, file, row); benign headline = BENIGN minus the audited Infiltration file", "exposure": S7.EXPOSURE["reused"] if test else "validation (dry run)",
           "n_flows": int(len(v)), "candidates": {}}
    n_b, k3 = E4.block_counts(a3, v)
    for name, al, sc, dl in (("v3", a3, s3, d3), ("F1", a1, s1, d1), ("RC5", a5, s5, d5)):
        sm = E4.summary(al, v)
        sm["delay_flow_level"] = E4.delay_stats(dl, fam)
        sm["alarm_lag"] = E4.alarm_lag(al, v, dl)
        _, k = E4.block_counts(al, v)
        if name != "v3":
            sm["paired_vs_v3"] = {"macro_diff_points": (sm["macro"] - res["candidates"]["v3"]["macro"]) * 100, **E4.paired_boot(n_b, k, k3)}
        res["candidates"][name] = sm
        print(name, round(sm["macro"] * 100, 2), round(sm["fa"] * 100, 3), sm.get("paired_vs_v3"), flush=True)
    sd = Path(sc_dir)
    sd.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(sd / f"network_{a.split}.npz", t=v["t"].to_numpy(float), fam=fam.astype(str), audit=v["audit"].to_numpy(), block=v["blk"].astype(str).to_numpy(), minute=v["minute"].to_numpy(),
                        v3_score=s3.astype("float32"), v3_alarm=a3, F1_score=s1.astype("float32"), F1_alarm=a1, RC5_score=s5.astype("float32"), RC5_alarm=a5, v3_layers=X3.astype("float32"),
                        F1_layers=X1.astype("float32"), RC5_layers=X5.astype("float32"))
    series = host_series(v, {"V3": (s3, a3), "F1": (s1, a1), "RC5": (s5, a5)}, a.split)
    cdir = S7.CACHE if test else Path(a.out)
    cdir.mkdir(parents=True, exist_ok=True)
    pickle.dump({"series": series}, open(cdir / ("net.pkl" if test else "net_val.pkl"), "wb"), protocol=4)
    S7.write_json(res, (out if out else S7.OUT) / ("network.json" if test else "network_val.json"))
    S7.journal("S7", f"network {a.split}: done", f"v3 macro {res['candidates']['v3']['macro']:.4f}, F1 {res['candidates']['F1']['macro']:.4f}, RC5 {res['candidates']['RC5']['macro']:.4f}")


if __name__ == "__main__":
    main()
