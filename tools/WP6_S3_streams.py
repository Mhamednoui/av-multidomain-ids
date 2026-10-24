"""WP6 S3 stage 1: 1 Hz tick series of every frozen domain on its own VALIDATION and TEST material (fusion/streams.py format).
Construction: notes/WP6_crossdomain.md "S3 start". Nothing here is chosen: frozen domains, frozen calibrations, the S2b / S3 cross choice.
Usage: python -u -W ignore tools/WP6_S3_streams.py <stage> [...]   stages: gps cross_kitti cross_comma can network v2x lidar
Output: ../data_extra/cache_v3/WP6/s3_<domain>.pkl = {"val": pack, "test": pack} (one file per stage = checkpoint).
Inputs (read only): results/WP1/frozen_gps + WP1 KITTI stream; WP6 S2 / S2b caches; results/WP2/s7_domain + WP2 S7 window tables;
results/WP4 S7 D10 score tables (cal.pkl) + D10 stage stream (host ids); VeReMi frames (WP5 loaders) + v2x layers;
WP3 S1 train4 cache + S2 v2l1 statistics + retrained_deployed.json.
"""
import json
import pickle
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from common.calibration import ECDFCalibrator  # noqa: E402
from common.config import DATA_EXTRA, SEED  # noqa: E402
from common.metrics import budget_threshold  # noqa: E402
from crossdomain import consistency as CS  # noqa: E402
from fusion import streams as ST  # noqa: E402

CACHE = DATA_EXTRA / "cache_v3" / "WP6"
T0 = time.time()
BUDGET = 0.01
PREFIX = "s3"            # WP6 S5 sets "s5" (tools/WP6_S5_streams.py): same series plus per-tick sample counts; cross_comma without the glitch filter


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def save(name, packs):
    pickle.dump(packs, open(CACHE / f"{PREFIX}_{name}.pkl", "wb"))
    for part, p in packs.items():
        n = sum(len(s["score"]) for s in p["series"])
        log(name, part, "series", len(p["series"]), "ticks", n, "kinds", pd.Series([s["kind"] for s in p["series"]]).value_counts().to_dict())


# ---------------------------------------------------------------------------------------------------------------- GPS (vehicle block K)
def stage_gps():
    from gps import stream as GS
    from gps.domain import GPSDomain, prepare
    import WP6_S1_kitti as S1
    dom = GPSDomain.load(ROOT / "results" / "WP1" / "frozen_gps")
    lthr = {l.name: l.threshold for l in dom.layers}
    kx = S1.kitti_stream()
    kx = kx[kx["part"].isin(["val", "test"]) & kx["attack"].isin(["none", "drift", "accel_drift", "doppler_spoof", "meaconing"])]
    kx = kx[(kx["attack"] != "none") | kx["run"].str.endswith("/r0")]
    co = pickle.load(open(CACHE / "s2_kitti.pkl", "rb"))["gps_can_runs"][GS.COLUMNS]
    df = pd.concat([kx, co], ignore_index=True).sort_values(["run", "t"], kind="stable").reset_index(drop=True)
    packs = {p: {"domain": "gps", "layer_names": dom.names, "layer_thr": np.array([lthr[n] for n in dom.names]), "dom_thr": dom.comb_threshold, "series": []}
             for p in ("val", "test")}
    for d, g in df.groupby("drive", sort=True):
        g = prepare(g.reset_index(drop=True))
        cal = dom._calibrated(g)
        S = dom._statistic(cal)
        sc = dom.comb_cal.transform(S)
        Lm = np.column_stack([cal[n] for n in dom.names])
        for run, idx in g.groupby("run", sort=False).indices.items():
            r = g.iloc[idx]
            a = str(r["attack"].iloc[0])
            fam = "gps_can" if run.endswith("/gps_can") else a
            lab = r["label"].to_numpy() > 0
            s = ST.series(d, run, "clean" if fam == "none" else "attack", fam, sc[idx], Lm[idx], lab)
            s["t"] = r["t"].to_numpy(float)
            packs[r["part"].iloc[0]]["series"].append(s)
        log("gps drive", d)
    save("gps", packs)


# ---------------------------------------------------------------------------------------------------------------- cross-domain
def _cross_pack(domain, edges):
    return {"domain": domain, "layer_names": [e.name for e in edges], "layer_thr": None, "dom_thr": None, "series": []}


def _cross_series(group, name, kind, family, t, Z, cal, edges, domain_of, onset_t):
    S = np.abs(Z)
    es = cal.edge_scores(S)
    al = es >= cal.tau
    bl = CS.blame(edges, al, np.isfinite(S), domain_of)
    lab = np.zeros(len(t), bool) if not np.isfinite(onset_t) else (np.asarray(t, float) >= onset_t)
    s = ST.series(group, name, kind, family, es.max(axis=1), es, lab, blame=bl)
    s["t"] = np.asarray(t, float)
    s["layer_alarm"], s["dom_alarm"] = al, al.any(axis=1)
    return s


def stage_cross_kitti():
    import WP6_S2_kitti as SK
    import WP6_S2b_eval as B
    choice = json.loads((ROOT / "results" / "WP6" / "s3_crosschoice.json").read_text())["choice"]["kitti"]
    assert choice == "base_inst", choice                         # the quality flag was not chosen (S3 val-only choice)
    edges, runs = B.kitti_runs()                                  # dev drives, out-of-fold sigma models
    clean = {g: np.vstack([np.abs(r["Z"]) for r in rs if r["attack"] == "none"]) for g, rs in runs.items()}
    packs = {p: _cross_pack("cross_kitti", edges) for p in ("val", "test")}
    for g, rs in runs.items():
        if rs[0]["part"] != "val":
            continue
        cal = CS.Calibration(BUDGET).fit(np.vstack([clean[h] for h in runs if h != g]))
        for r in rs:
            packs["val"]["series"].append(_cross_series(g, r["run"], "clean" if r["attack"] == "none" else "attack", r["attack"], r["t"], r["Z"], cal, edges,
                                                        SK.DOMAIN_OF, r["onset_t"]))
    packs["val"]["calibration_note"] = "val drives: leave-one-drive-out calibration over the 15 dev drives (S2b)"
    cal = CS.Calibration(BUDGET).fit(np.vstack(list(clean.values())))
    dev = pickle.load(open(CACHE / "s2b_kitti.pkl", "rb"))["rows"]
    models = B.oof_models(dev[(dev["attack"] == "none") & (dev["phase"] == 0)], edges)
    rows = pickle.load(open(CACHE / "s2_kitti.pkl", "rb"))["rows"]
    rows = rows[rows["part"] == "test"].sort_values(["run", "t"]).reset_index(drop=True)
    Z = B.z_of(rows, edges, models)
    for run, idx in rows.groupby("run").indices.items():
        r0 = rows.iloc[idx[0]]
        packs["test"]["series"].append(_cross_series(r0["drive"], run, "clean" if r0["attack"] == "none" else "attack", r0["attack"],
                                                     rows["t"].to_numpy(float)[idx], Z[idx], cal, edges, SK.DOMAIN_OF, float(r0["onset_t"])))
    for p in packs.values():
        p["dom_thr"] = cal.tau if p is packs["test"] else None
        p["layer_thr"] = None
    packs["test"]["calibration"] = cal.to_dict()
    save("cross_kitti", packs)


def stage_cross_comma(glitch=None):
    import WP6_S2_comma as SC
    import WP6_S2b_eval as B
    import WP6_S3_crosschoice as X
    choice = json.loads((ROOT / "results" / "WP6" / "s3_crosschoice.json").read_text())["choice"]["comma"]
    if glitch is None:                                            # S3: the val-only choice; S5: False (glitch filter dropped, ORCHESTRATOR 2026-10-24)
        glitch = choice == "inst_glitch_filter"
    edges, data, cls = B.comma_data()                             # dev routes (train + val), out-of-fold models
    if glitch:
        X.apply_glitch(edges, data)
    gcols = [j for j, e in enumerate(edges) if {"can", "wheel"} & {e.a, e.b}]
    clean = {n: np.abs(d["Z"]) for n, d in data.items()}
    packs = {p: _cross_pack("cross_comma", edges) for p in ("val", "test")}
    W = SC.WIN
    for n, d in data.items():
        cal = CS.Calibration(BUDGET).fit(np.vstack([clean[h] for h in data if h != n]))
        t = d["t"]
        for w0 in range(0, len(t) - W + 1, W):                    # clean vehicle blocks: consecutive 120 s windows of the route
            sl = slice(w0, w0 + W)
            packs["val"]["series"].append(_cross_series(n, f"{n}/w{w0}", "clean", "none", t[sl], d["Z"][sl], cal, edges, SC.DOMAIN_OF, np.nan))
        for ep in d["episodes"]:
            packs["val"]["series"].append(_cross_series(n, ep["run"], "attack", ep["attack"], ep["t"], ep["Z"], cal, edges, SC.DOMAIN_OF, ep["onset_t"]))
    packs["val"]["calibration_note"] = "dev routes (train + val, out-of-fold models): leave-one-route-out calibration (S2b)"
    cal = CS.Calibration(BUDGET).fit(np.vstack(list(clean.values())))
    c2 = pickle.load(open(CACHE / "s2_comma.pkl", "rb"))
    b2 = pickle.load(open(CACHE / "s2b_comma.pkl", "rb"))
    setup = {**b2["setup"], **c2["setup"]}
    clsall = {n: ("g10" if s["gyro_hz"] <= 20 else "g100") for n, s in setup.items()}
    dev_routes = b2["routes"][b2["routes"]["part"].isin(["train", "val"])]
    models = {k: B.oof_models(dev_routes[dev_routes["route"].map(clsall) == k], edges) for k in ("g10", "g100")}
    routes = c2["routes"][c2["routes"]["part"] == "test"]
    eps = c2["episodes"][c2["episodes"]["part"] == "test"]
    log("comma test routes", routes["route"].nunique(), "episodes", eps["run"].nunique())
    for n, rr in routes.groupby("route"):
        rr = rr.sort_values("t").reset_index(drop=True)
        mdl = models[clsall[n]]
        Z = B.z_of(rr, edges, mdl)
        if glitch:
            Z = X.glitch(Z, gcols)
        t = rr["t"].to_numpy(float)
        for w0 in range(0, len(t) - W + 1, W):
            sl = slice(w0, w0 + W)
            packs["test"]["series"].append(_cross_series(n, f"{n}/w{w0}", "clean", "none", t[sl], Z[sl], cal, edges, SC.DOMAIN_OF, np.nan))
        e = eps[eps["route"] == n]
        for run, idx in e.groupby("run").indices.items():
            x = e.iloc[np.sort(idx)]
            r0 = x.iloc[0]
            if r0["attack"] == "none":
                continue
            Ze = B.z_of(x, edges, mdl)
            if glitch:
                Ze = X.glitch(Ze, gcols)
            packs["test"]["series"].append(_cross_series(n, run, "attack", r0["attack"], x["t"].to_numpy(float), Ze, cal, edges, SC.DOMAIN_OF, float(r0["onset_t"])))
    packs["test"]["dom_thr"] = cal.tau
    packs["test"]["calibration"] = cal.to_dict()
    for p in ("val", "test"):
        packs[p]["glitch_filter"] = glitch
    save("cross_comma", {"val": packs["val"], "test": packs["test"]})


# ---------------------------------------------------------------------------------------------------------------- CAN (ROAD)
def can_family(name):
    f = re.sub(r"_attack(_\d)?", "", name.replace("_masquerade", ""))
    return f + ("_masquerade" if name.endswith("_masquerade") else "")


def stage_can():
    from can.domain import CanDomain, LAYER_NAMES
    dom = CanDomain.load(ROOT / "results" / "WP2" / "s7_domain")
    assert dom.combiner.method == "max"
    tab = DATA_EXTRA / "WP2_S7_cache" / "tables"
    names = [LAYER_NAMES[l] for l in dom.layers]
    packs = {p: {"domain": "can", "layer_names": names, "layer_thr": np.array([dom.layer_thresholds[l] for l in dom.layers]),
                 "dom_thr": dom.combiner.threshold, "series": []} for p in ("val", "test")}
    sel = {"val": [("folds", n) for n in sorted(p.stem for p in (tab / "folds").glob("*.npz"))]
           + [("val", n) for n in sorted(p.stem for p in (tab / "val").glob("*.npz")) if re.search(r"_attack_2", n)],
           "test": [("test", n) for n in sorted(p.stem for p in (tab / "test").glob("*.npz"))]}
    for part, items in sel.items():
        for folder, n in items:
            t = dict(np.load(tab / folder / (n + ".npz")))
            cal = dom.calibrated(t)
            ok = t["ok"]
            L = np.column_stack([cal[l] for l in dom.layers])[ok]
            sc = L.max(axis=1)
            lab = t["y"][ok] > 0
            kind = "attack" if lab.any() else "clean"
            packs[part]["series"].append(ST.series(n, n, kind, can_family(n) if kind == "attack" else "none", sc, L, lab))
        log("can", part, len(items))
    save("can", packs)


# ---------------------------------------------------------------------------------------------------------------- network (D10, one host)
HOST = 49          # 192.168.10.50 in the D10 stage stream id table (the host the D10 attacks target)


def stage_network():
    from tools.WP4_S6_lib import load_s6
    from tools.WP4_S7_lib import COL, H, load_tables
    meta = json.loads((ROOT / "results" / "WP4" / "s7_domain" / "domain.json").read_text())
    thr = float(meta["combined_threshold"])
    d, _ = load_s6()
    ids = d[["src_id", "dst_id"]].to_numpy()
    val, test, cal = load_tables()
    lthr = np.array([cal[n][1] for n in H])
    packs = {}
    for part, tb in (("val", val), ("test", test)):
        pos = tb["pos"].to_numpy()
        m = (ids[pos, 0] == HOST) | (ids[pos, 1] == HOST)
        x = tb[m].reset_index(drop=True)
        L = np.column_stack([cal[n][0].transform(x[COL[n]].to_numpy(float)) for n in H]).astype(np.float32)
        comb = L.max(axis=1)
        fam = x["fam"].astype(str).to_numpy()
        att = fam != "BENIGN"
        audit = x["audit"].to_numpy()
        mins = (x["t"].to_numpy(float) // 60).astype(np.int64)
        blk = x["day"].astype(str) + "|" + x["period"].astype(str)
        p = {"domain": "network", "layer_names": list(H), "layer_thr": lthr, "dom_thr": thr, "series": [], "host": "192.168.10.50 (id 49)",
             "n_flows": int(m.sum()), "fa_flows_host_benign": float((comb[~att & ~audit] >= thr).mean()), "clean_samples": {}}
        for b, idx in pd.Series(np.arange(len(x))).groupby(blk.to_numpy()).indices.items():
            mi = mins[idx]
            u, inv = np.unique(mi, return_inverse=True)
            V = ST.tick_max(inv, L[idx], len(u))
            lab = ST.tick_any(inv, att[idx], len(u))
            fm = ST.tick_family(inv, np.where(att[idx], fam[idx], ""), len(u))
            Vt, Lt, Ft = ST.hold_minutes(u, V, lab, fm, int(u.min()), int(u.max()) + 1)
            cnt = ST.hold_minutes(u, np.bincount(inv, minlength=len(u)).astype(np.float32)[:, None], lab, fm, int(u.min()), int(u.max()) + 1)[0][:, 0]
            kind = "attack" if Lt.any() else "clean"
            fams = sorted(set(Ft[Lt]))
            s = ST.series(b, b, kind, ",".join(fams) if fams else "none", Vt.max(axis=1), Vt, Lt, fam=Ft)
            s["count"] = cnt                                          # flows of the held minute (S5 density model)
            p["series"].append(s)
            if kind == "clean":
                ok = ~att[idx] & ~audit[idx]
                p["clean_samples"][b] = comb[idx][ok].astype(np.float32)   # per-flow combined score (S5 density model)
        packs[part] = p
        log("network", part, "host flows", int(m.sum()), "blocks", len(p["series"]), "flow FA (host benign)", round(p["fa_flows_host_benign"], 4))
    save("network", packs)


# ---------------------------------------------------------------------------------------------------------------- V2X (VeReMi, ego view)
V2X_L1 = ["v2x.beacon_rate", "v2x.field_ranges"]
V2X_L2 = ["v2x.pos_speed", "v2x.pos_heading", "v2x.speed_change", "v2x.implied_speed", "v2x.heading_rate", "v2x.accel_consistency", "v2x.overlap"]
V2X_L3 = ["v2x.kf_nis", "v2x.kf_cusum_hi", "v2x.track_birth"]
V2X_NAMES = V2X_L1 + V2X_L2 + V2X_L3
V2X_RAW = {"v2x.beacon_rate": "rate", "v2x.field_ranges": "field_raw", "v2x.pos_speed": "pos_speed", "v2x.pos_heading": "pos_heading",
           "v2x.speed_change": "speed_change", "v2x.implied_speed": "implied_speed", "v2x.heading_rate": "heading_rate",
           "v2x.accel_consistency": "accel_consistency", "v2x.overlap": "overlap", "v2x.kf_nis": "nis", "v2x.kf_cusum_hi": "cusum_hi", "v2x.track_birth": "birth"}
HELDOUT = [6, 12, 17]
RADIUS_M, EGO_MIN_S, EGOS_PER_BLOCK = 300.0, 60.0, 10


def v2x_raws(df, tracker):
    from v2x import l4
    r = l4.message_scores(df, tracker)
    return np.column_stack([np.asarray(r[V2X_RAW[n]], dtype=np.float32) for n in V2X_NAMES]).astype(float)


def ego_series(blk, Lc, rng, part, pack):
    """Ego views of one VeReMi time block. blk: messages of the block (time-sorted, class 12 dropped) with calibrated layer matrix Lc."""
    lab = blk["label"].to_numpy()
    snd = blk["sender"].to_numpy()
    t = blk["t"].to_numpy(float)
    x, y = blk["x"].to_numpy(float), blk["y"].to_numpy(float)
    bad = pd.Series(lab > 0).groupby(snd).any()
    dur = pd.Series(t).groupby(snd).agg(lambda v: v.max() - v.min())
    cand = sorted(s for s in dur.index if not bad[s] and dur[s] >= EGO_MIN_S)
    if not cand:
        return
    egos = rng.choice(cand, size=min(EGOS_PER_BLOCK, len(cand)), replace=False)
    comb = Lc.max(axis=1)
    for e in egos:
        me = snd == e
        te, xe, ye = t[me], x[me], y[me]
        t0, t1 = te.min(), te.max()
        w = (t >= t0) & (t <= t1) & ~me
        ex, ey = np.interp(t[w], te, xe), np.interp(t[w], te, ye)
        near = np.hypot(x[w] - ex, y[w] - ey) <= RADIUS_M
        idx = np.flatnonzero(w)[near]
        n = int(np.ceil(t1 - t0)) + 1
        k = np.floor(t[idx] - t0).astype(np.int64)
        gen = lab[idx] == 0
        grp = str(blk["group"].iloc[0])
        Vc = ST.tick_max(k[gen], Lc[idx][gen], n)
        pack["series"].append(ST.series(grp, f"{grp}/ego{e}/clean", "clean", "none", Vc.max(axis=1), Vc, np.zeros(n, bool)))
        pack["series"][-1]["count"] = np.bincount(k[gen], minlength=n)[:n].astype(np.float32)      # heard messages per tick (S5 density model)
        if (~gen).any():
            from tools.WP5_S2_l1 import aname
            V = ST.tick_max(k, Lc[idx], n)
            fam = np.where(gen, "", np.array([aname(int(c)) if c > 0 else "" for c in lab[idx]], object))
            Lt = ST.tick_any(k, ~gen, n)
            Ft = ST.tick_family(k, fam, n)
            pack["series"].append(ST.series(grp, f"{grp}/ego{e}/attack", "attack", ",".join(sorted(set(Ft[Lt]))), V.max(axis=1), V, Lt, fam=Ft))
            pack["series"][-1]["count"] = np.bincount(k, minlength=n)[:n].astype(np.float32)


def stage_v2x():
    import WP5_S5_dev as dev5
    from v2x import splitting
    tracker = dev5.tracker_from_s4()
    v, sp = dev5.load_frames()
    va = splitting.rows_of(v, sp["val"])
    fit = va[~va["label"].isin(HELDOUT)].sort_values("t", kind="stable").reset_index(drop=True)
    R = v2x_raws(fit, tracker)
    g = fit["label"].to_numpy() == 0
    cals = [ECDFCalibrator().fit(R[g, j]) for j in range(len(V2X_NAMES))]
    Lv = np.column_stack([c.transform(R[:, j]) for j, c in enumerate(cals)])
    lthr = np.array([budget_threshold(Lv[g, j], BUDGET) for j in range(len(V2X_NAMES))])
    dthr = float(budget_threshold(Lv.max(axis=1)[g], BUDGET))
    log("v2x fitted on val (held-out types removed)", len(fit), "combined thr", dthr)
    ref = json.loads((ROOT / "results" / "WP5" / "s6_veremi.json").read_text())["layer_thresholds_calibrated"]
    diff = max(abs(lthr[j] - ref[n]) for j, n in enumerate(V2X_NAMES))
    log("max |layer threshold - WP5 S6|", diff)
    packs = {}
    for part in ("val", "test"):
        df = splitting.rows_of(v, sp[part])
        df = df[df["label"] != 12].sort_values("t", kind="stable").reset_index(drop=True)
        Rp = v2x_raws(df, tracker)
        Lc = np.column_stack([c.transform(Rp[:, j]) for j, c in enumerate(cals)]).astype(np.float32)
        gp = df["label"].to_numpy() == 0
        p = {"domain": "v2x", "layer_names": V2X_NAMES, "layer_thr": lthr, "dom_thr": dthr, "series": [], "threshold_diff_vs_wp5": diff,
             "fa_msgs_genuine": float((Lc.max(axis=1)[gp] >= dthr).mean())}
        rng = np.random.default_rng([SEED, 6, 3, 1 if part == "val" else 2])
        p["clean_samples"] = {}
        for grp, idx in df.groupby("group", sort=True).indices.items():
            ego_series(df.iloc[idx].reset_index(drop=True), Lc[idx], rng, part, p)
            p["clean_samples"][str(df["group"].iloc[idx[0]])] = Lc[idx].max(axis=1)[gp[idx]].astype(np.float32)   # genuine messages (S5 density model)
        packs[part] = p
        log("v2x", part, "messages", len(df), "genuine msg FA", round(p["fa_msgs_genuine"], 4))
    save("v2x", packs)


# ---------------------------------------------------------------------------------------------------------------- LiDAR (INTERIM)
LIDAR_ATT = ["PointDrop", "IntensitySpoof", "GhostCluster"]
LIDAR_REPS = 4


def stage_lidar():
    import xgboost as xgb
    from lidar.data import CACHE as LC, TEST, VAL
    from lidar.geometry import STAT_NAMES
    from lidar.l1 import L1Union
    mdl = xgb.XGBClassifier()
    mdl.load_model(str(LC / "retrained_deployed.json"))
    mdl.set_params(device="cpu", n_jobs=4)
    tabs = {}
    for d in VAL + TEST:
        p = pd.read_pickle(LC / "train4" / f"{d}.pkl")
        q = pd.read_pickle(LC / "S2" / f"v2l1_{d}.pkl")
        m, qm = p["meta"].reset_index(drop=True), q["meta"].reset_index(drop=True)
        assert len(m) == len(qm) and (m["cls"].to_numpy() == qm["cls"].to_numpy()).all()
        st = q["stats"].reset_index(drop=True) if isinstance(q["stats"], pd.DataFrame) else pd.DataFrame(np.asarray(q["stats"]), columns=STAT_NAMES)
        tabs[d] = (m, 1.0 - mdl.predict_proba(p["X"].astype(np.float32))[:, 0], st)
    vn = {d: tabs[d][0]["cls"].to_numpy() == "Normal" for d in VAL}
    c_v2 = ECDFCalibrator().fit(np.concatenate([tabs[d][1][vn[d]] for d in VAL]))
    u = L1Union().calibrate(pd.concat([tabs[d][2][vn[d]] for d in VAL], ignore_index=True), budget=BUDGET)
    names = ["lidar.v2_baseline_interim", "lidar.l1_union"]

    def cal_rows(d):
        m, raw, st = tabs[d]
        return np.column_stack([c_v2.transform(raw), u.calibrator.transform(np.asarray(u.raw_scores(st), float))])

    Lval = np.vstack([cal_rows(d)[vn[d]] for d in VAL])
    lthr = np.array([budget_threshold(Lval[:, j], BUDGET) for j in range(2)])
    dthr = float(budget_threshold(Lval.max(axis=1), BUDGET))
    packs = {p: {"domain": "lidar", "layer_names": names, "layer_thr": lthr, "dom_thr": dthr, "series": [], "status": "INTERIM (WP3 S1 v2 baseline + S2 L1)"}
             for p in ("val", "test")}
    for d in VAL + TEST:
        part = "val" if d in VAL else "test"
        m = tabs[d][0]
        Lr = cal_rows(d)
        k = np.arange((m["cls"] == "Normal").sum()) // 10            # 10 Hz scans -> 1 s ticks
        n = int(k.max()) + 1
        norm = Lr[m["cls"].to_numpy() == "Normal"]
        Vc = ST.tick_max(k, norm, n)
        packs[part]["series"].append(ST.series(d, f"{d}/clean", "clean", "none", Vc.max(axis=1), Vc, np.zeros(n, bool)))
        rng = np.random.default_rng([SEED, 6, 30, int(d)])
        for a in LIDAR_ATT:
            att = Lr[m["cls"].to_numpy() == a]
            Va = ST.tick_max(k, att, n)
            for rep in range(LIDAR_REPS):
                k0 = int(rng.integers(0, max(1, n // 2)))
                V = Vc.copy()
                V[k0:] = Va[k0:]
                lab = np.arange(n) >= k0
                packs[part]["series"].append(ST.series(d, f"{d}/{a}/r{rep}", "attack", a, V.max(axis=1), V, lab))
        packs[part][f"scan_fa_{d}"] = float((norm.max(axis=1) >= dthr).mean())
    log("lidar val-normal scan FA", round(float((Lval.max(axis=1) >= dthr).mean()), 4))
    save("lidar", packs)


STAGES = {"gps": stage_gps, "cross_kitti": stage_cross_kitti, "cross_comma": stage_cross_comma, "can": stage_can, "network": stage_network,
          "v2x": stage_v2x, "lidar": stage_lidar}

if __name__ == "__main__":
    for s in sys.argv[1:]:
        log("stage", s)
        STAGES[s]()
    log("done")
