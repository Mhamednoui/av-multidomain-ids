"""WP8 S4 unseen-Bot analysis on D10 VALIDATION (V31_val) with label-free / physically motivated candidates, per notes/WP8_v31.md (S4 pre-registration, N4).
Part A (explanation, val only): where Bot flows sit in the benign val distribution of every H layer and of the frozen beacon layer; flow-shape duplicates among BENIGN-labelled flows; group structure of the
Bot flows on the 1-minute grid; published vs documented-rule corrected labels.
Part B (candidates, all fitted on benign TRAIN cells only, calibrated at 1 % of benign VAL): BOT-A net.beacon (frozen WP4 S4 definition), BOT-B persistent rare endpoint, BOT-C size regularity of
persistent groups, BOT-D = max(B, C); alone and as an added layer to stack H (max combiner, threshold 1 % of the benign val combined score; N2 must hold).
Inputs: ../data_extra/cache_v3/WP8/S4/D10_trainval_stage.pkl (train + val only), the frozen v3 domain (read only), IP strings of the WP4 stage chunks (only to apply the documented Bot relabel rule
and to name the groups; no model uses an address). Outputs: results/WP8/S4/s4_bot.json, scores results/WP8/scores/S4/network_bot_val.npz.
Usage: python -u -W ignore -I tools/WP8_S4_bot.py
"""
import glob
import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))
import WP8_S4_eval as E  # noqa: E402

from common.calibration import ECDFCalibrator  # noqa: E402
from common.metrics import auc, budget_threshold  # noqa: E402
from network import l2a, l2b  # noqa: E402
from network.domain import NetworkDomain  # noqa: E402

VICTIMS = {"192.168.10.5", "192.168.10.8", "192.168.10.9", "192.168.10.14", "192.168.10.15"}
C2 = "205.174.165.73"
WIN60 = 60
T0 = time.time()
log = E.log


def load_both():
    E.W8.assert_not_h31([E.STAGE])
    d = pd.read_pickle(E.STAGE)
    assert set(d["split"].astype(str).unique()) <= {"train", "val"}
    d["audit"] = d["file"].astype(str).str.contains(E.AUDIT_FILE).to_numpy()
    d["fam"] = d["family"].astype(str)
    d = d.sort_values(["minute", "file", "row"], kind="stable").reset_index(drop=True)
    d["blk"] = d["day"].astype(str) + "|" + d["period"].astype(str)
    return d


def add_ips(v):
    parts = []
    for p in glob.glob(os.path.join(ROOT, "..", "data_extra", "cache_v3", "WP4", "D10", "stage", "*.pkl")):
        s = pd.read_pickle(p, compression="gzip")[["file", "row", "src_ip", "dst_ip"]]
        s["file"], s["src_ip"], s["dst_ip"] = s["file"].astype(str), s["src_ip"].astype(str), s["dst_ip"].astype(str)
        parts.append(s)
    ip = pd.concat(parts, ignore_index=True)
    v = v.assign(file=v["file"].astype(str)).merge(ip, on=["file", "row"], how="left")
    assert v["src_ip"].notna().all()
    return v


class Persistent:
    """BOT-B / BOT-C helper: per-flow window statistics over the trailing 60 minutes of service-directed flows (all label-free, address-free: ids only group)."""

    def feats(self, df):
        m = df["minute"].to_numpy().astype("int64")
        svc = df["dst_port"].to_numpy() < l2a.EPHEMERAL
        g = l2a.gid(df["src_id"].to_numpy(), df["dst_id"].to_numpy(), df["dst_port"].to_numpy(), df["protocol"].to_numpy())
        ep = l2a.gid(df["dst_id"].to_numpy(), df["dst_port"].to_numpy(), df["protocol"].to_numpy())
        act = l2a.trailing(g, m, WIN60, m, mask=svc)                                   # distinct active minutes of the group
        pop = l2a.trailing(ep, m, WIN60, df["src_id"].to_numpy(), mask=svc)            # distinct sources that contacted this endpoint
        byt = (df["TotLen Fwd Pkts"].to_numpy(float) + df["TotLen Bwd Pkts"].to_numpy(float))
        n = l2a.trailing(g, m, WIN60, w=svc.astype(float))
        s1 = l2a.trailing(g, m, WIN60, w=np.where(svc, byt, 0.0))
        s2 = l2a.trailing(g, m, WIN60, w=np.where(svc, byt * byt, 0.0))
        mean = s1 / np.maximum(n, 1)
        cv = np.sqrt(np.maximum(s2 / np.maximum(n, 1) - mean * mean, 0.0)) / np.maximum(mean, 1.0)
        return {"g": g, "act": act.astype(float), "pop": pop.astype(float), "n": n, "cv": cv, "svc": svc, "m": m}


class BotB:
    """Persistent rare endpoint: score = benign tail of the active-minute count among groups whose endpoint had <= 3 distinct sources in the window; 0 elsewhere."""
    name = "BOT-B"

    def fit(self, tr):
        f = Persistent().feats(tr)
        ok = f["svc"] & (f["pop"] <= 3) & (f["act"] >= 1)
        cell = l2a.gid(f["g"], f["m"])
        self.t = l2a.TailTable(l2a.unique_cells(cell[ok], f["act"][ok])[0])
        return self

    def raw(self, df):
        f = Persistent().feats(df)
        ok = f["svc"] & (f["pop"] <= 3)
        out = np.zeros(len(df))
        out[ok] = self.t.score(f["act"][ok])
        return out


class BotC:
    """Size regularity of persistent groups: among groups with >= 6 active minutes and >= 6 flows in the window, score = benign tail of -CV of the bytes per flow."""
    name = "BOT-C"

    def fit(self, tr):
        f = Persistent().feats(tr)
        ok = f["svc"] & (f["act"] >= 6) & (f["n"] >= 6)
        cell = l2a.gid(f["g"], f["m"])
        self.t = l2a.TailTable(l2a.unique_cells(cell[ok], -f["cv"][ok])[0])
        return self

    def raw(self, df):
        f = Persistent().feats(df)
        ok = f["svc"] & (f["act"] >= 6) & (f["n"] >= 6)
        out = np.zeros(len(df))
        out[ok] = self.t.score(-f["cv"][ok])
        return out


class BotA:
    name = "BOT-A"

    def fit(self, tr):
        self.B = l2b.Beacon().fit_stream(tr)
        return self

    def raw(self, df):
        return np.asarray(self.B.stream_scores(df), float)


def calib(raw_b):
    c = ECDFCalibrator().fit(raw_b)
    return c, budget_threshold(c.transform(raw_b), 0.01)


def bot_groups(v, bot):
    rows = []
    d = v[bot]
    for (s, t_, p), g in d.groupby(["src_ip", "dst_ip", "dst_port"]):
        m = np.sort(g["minute"].unique())
        rows.append({"src": s, "dst": t_, "port": int(p), "flows": int(len(g)), "active_minutes": int(len(m)), "median_gap_min": float(np.median(np.diff(m))) if len(m) > 1 else None,
                     "span_min": int(m.max() - m.min() + 1), "flows_per_active_minute": float(len(g) / len(m))})
    return sorted(rows, key=lambda r: -r["flows"])


def main():
    os.makedirs(E.OUT, exist_ok=True)
    d = load_both()
    tr = d[d["split"].astype(str) == "train"]
    trb = tr[(tr["fam"] == "BENIGN") & ~tr["audit"]].reset_index(drop=True)
    v = d[d["split"].astype(str) == "val"].reset_index(drop=True)
    vb = v[(v["fam"] == "BENIGN") & ~v["audit"]].reset_index(drop=True)
    del d, tr
    v = add_ips(v)
    fam = v["fam"].to_numpy()
    bot = fam == "Bot"
    ben = (fam == "BENIGN") & ~v["audit"].to_numpy()
    # documented relabel rule (information only): flows between an Ares victim and the C2 on port 8080, either direction, labelled BENIGN
    c2flow = (((v["src_ip"].isin(VICTIMS)) & (v["dst_ip"] == C2) & (v["dst_port"] == 8080)) | ((v["dst_ip"].isin(VICTIMS)) & (v["src_ip"] == C2) & (v["src_port"] == 8080))).to_numpy()
    bot_c = bot | (c2flow & (fam == "BENIGN"))
    res = {"n_val_flows": int(len(v)), "n_bot_published": int(bot.sum()), "n_bot_corrected": int(bot_c.sum()), "relabelled_benign_flows": int((bot_c & ~bot).sum())}
    # ---------------- Part A: explanation
    dom = NetworkDomain.load(E.FROZEN)
    raw = dom.raw_matrix(v)
    by = {L.name: L for L in dom.layers}
    A = {}
    cal_cols = {}
    for n, L in by.items():
        cs = L.calibrator.transform(raw[n])
        cal_cols[n] = cs
        yy = np.r_[np.ones(int(bot.sum())), np.zeros(int(ben.sum()))]
        A[n] = {"auc_bot_vs_benign": float(auc(yy, np.r_[cs[bot], cs[ben]])), "median_calibrated_bot": float(np.median(cs[bot])), "share_bot_above_layer_threshold": float((cs[bot] >= L.threshold).mean()),
                "p95_benign_calibrated": float(np.percentile(cs[ben], 95)), "layer_threshold": float(L.threshold),
                "median_raw_bot": float(np.median(raw[n][bot])), "median_raw_benign": float(np.median(raw[n][ben])), "p99_raw_benign": float(np.percentile(raw[n][ben], 99))}
    res["A_layers_H"] = A
    shape = ["Tot Fwd Pkts", "Tot Bwd Pkts", "TotLen Fwd Pkts", "TotLen Bwd Pkts", "dst_port"]
    key = v[shape].astype(float).astype(str).agg("|".join, axis=1)
    kb = set(key[bot])
    sh = key.isin(kb).to_numpy()
    res["A_shape_duplicates"] = {"bot_shapes": len(kb), "bot_flows_with_shape_found_in_benign_headline": float(sh[ben].sum() > 0 and np.mean(key[bot].isin(set(key[ben])))),
                                 "benign_flows_with_a_bot_shape": int((sh & ben).sum()), "benign_flows_with_a_bot_shape_src_in_victims": int((sh & ben & v["src_ip"].isin(VICTIMS).to_numpy()).sum()),
                                 "benign_with_bot_shape_dst_is_c2": int((sh & ben & (v["dst_ip"] == C2).to_numpy()).sum()), "bot_flows": int(bot.sum()),
                                 "max_precision_of_an_exact_shape_detector": float(bot.sum() / max(1, (sh & (bot | ben)).sum())),
                                 "note": "benign flows with the Bot shape between the Bot hosts and the C2 are the documented label noise (WP4 S6): the beacon traffic inside the Friday benign-labelled files"}
    res["A_groups_published"] = bot_groups(v, bot)
    res["A_groups_corrected"] = bot_groups(v, bot_c)
    log("A done", {k: (round(x["auc_bot_vs_benign"], 3), round(x["share_bot_above_layer_threshold"], 3)) for k, x in A.items()})
    # ---------------- Part B: candidates
    cands = [BotA(), BotB(), BotC()]
    cols_v, cols_vb, cal = {}, {}, {}
    for c in cands:
        t1 = time.time()
        c.fit(trb)
        rv, rvb = c.raw(v), c.raw(vb)
        cc, th = calib(rvb)
        cols_v[c.name], cols_vb[c.name] = cc.transform(rv), cc.transform(rvb)
        cal[c.name] = th
        log(c.name, "fit+score %.0fs" % (time.time() - t1))
    cols_v["BOT-D"], cols_vb["BOT-D"] = np.maximum(cols_v["BOT-B"], cols_v["BOT-C"]), np.maximum(cols_vb["BOT-B"], cols_vb["BOT-C"])
    cal["BOT-D"] = budget_threshold(cols_vb["BOT-D"], 0.01)
    # stack H on val benign-only stream for the added-layer threshold
    sH_v, aH_v, XH_v = dom.score_arrays(v)
    sH_b = dom.score_arrays(vb)[0]
    base = E.summary(aH_v, v)
    B = {"H_reference": {"fa": base["fa"], "macro": base["macro"], "bot": base["detection"].get("Bot")}}
    for nme, cv_ in cols_v.items():
        yy = np.r_[np.ones(int(bot.sum())), np.zeros(int(ben.sum()))]
        alone = cv_ >= cal[nme]
        r = {"alone": {"fa": float(alone[ben].mean()), "bot_published": float(alone[bot].mean()), "bot_corrected": float(alone[bot_c].mean()), "auc_bot_vs_benign": float(auc(yy, np.r_[cv_[bot], cv_[ben]])),
                       "groups_hit": int(sum(alone[(v["src_ip"] == g["src"]).to_numpy() & (v["dst_ip"] == g["dst"]).to_numpy() & bot].any() for g in res["A_groups_published"])),
                       "groups": len(res["A_groups_published"]), "precision_on_alarmed_bot_or_benign": float(alone[bot].sum() / max(1, alone[bot | ben].sum()))}}
        sv = np.maximum(sH_v, cv_)
        sb = np.maximum(sH_b, cols_vb[nme])
        thr = budget_threshold(sb, 0.01)
        st = sv >= thr
        sm = E.summary(st, v)
        r["added_to_H"] = {"fa": sm["fa"], "macro": sm["macro"], "macro_diff_vs_H_points": (sm["macro"] - base["macro"]) * 100, "bot_published": sm["detection"].get("Bot"),
                           "bot_corrected": float(st[bot_c].mean()), "detection": sm["detection"], "threshold": float(thr)}
        r["counts_for_N4"] = bool(nme != "BOT-C" and r["alone"]["bot_published"] >= 0.20 and sm["fa"] <= 0.01 and (sm["macro"] - base["macro"]) * 100 >= -3.0 and r["added_to_H"]["bot_published"] >= 0.20)
        B[nme] = r
        log(nme, r["alone"], {k: r["added_to_H"][k] for k in ("fa", "macro", "bot_published")})
    res["B_candidates"] = B
    res["B_note"] = ("BOT-C uses the byte count of the flows of a group (the fixed shape of the Ares beacon): shape-dependent by construction, reported but never counted for N4. "
                     "BOT-A / BOT-B use only counts of active minutes, gaps and sources: no port, address or size identity.")
    np.savez_compressed(os.path.join(E.SCORES, "network_bot_val.npz"), fam=fam.astype(str), bot_corrected=bot_c, audit=v["audit"].to_numpy(), t=v["t"].to_numpy(float), **{k.replace("-", "_"): x.astype("float32") for k, x in cols_v.items()})
    json.dump(res, open(os.path.join(E.OUT, "s4_bot.json"), "w"), indent=1)
    log("done")


if __name__ == "__main__":
    main()
