"""WP8 S2 builder: per-domain tick sources of the V31_val system composites (notes/WP8_v31.md "S2 round 1"), from the saved / frozen v3.1 domain outputs.

Stages (resumable: one pickle per stage in ../data_extra/cache_v3/WP8/S2/, temp name then rename; a stage whose pickle exists is skipped):
  kveh   K vehicle block: S6 records of the 10 V31_val KITTI drives (GPS v3 frozen tick score / alarm; cross = S6 train-only fit_k, edge scores, alarm; blame A1, A3, v3)
  cveh   C vehicle block: S6 records of the 8 V31_val comma routes (120 s windows; cross = S6 train-only fit_c; blame A1, v3)
  lidar  per-scan LiDAR tables of the 10 V31_val drives, leave-one-drive-out scores of frozen_lidar31 (L100, = results/WP8/scores/S3/lidar_val.npz) and of
         frozen_lidar31_B125 (L125), scan time = OXTS time of the scan index
  can    ROAD V31_val captures: IncrementalCan per-second Evidence (results/WP8/scores/S5/can_val_*.npz)
  v2x    VeReMi V31_val blocks: ego views (<= 40 egos per block), each ego's heard table scored as that receiver hears it (V2XPhysicsDomain.raws == EgoStream)
  net    D10 val host-49 view: F1 per-flow scores -> minute ticks held one minute (M2 tick model); RC5 labelled variant (no hold)
Run from codes_v3/: python -u -W ignore tools/WP8_S2_build.py [stage ...]   (default: all)
"""
import json
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True

import numpy as np
import pandas as pd

import WP8_lib as L8
from common.config import DATA_EXTRA

CACHE = DATA_EXTRA / "cache_v3" / "WP8" / "S2"
LIDAR_KINDS = ["IntensitySpoof", "PointDrop", "ph_budget_far", "ph_budget_near", "ph_replace_far", "ph_replace_near"]
EGOS_PER_BLOCK, RADIUS_M, EGO_MIN_S = 40, 300.0, 60.0
HOST = 49
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def save(obj, name):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / name
    tmp = f.with_suffix(".tmp")
    pickle.dump(obj, open(tmp, "wb"), protocol=4)
    tmp.replace(f)


def blame_str(b):
    return np.array([None if x is None else str(x) for x in b], object)


# ------------------------------------------------------------------------------------------------------------- K vehicle
def stage_kveh():
    import WP8_S6_eval as E6
    from crossdomain import blame31 as B
    from crossdomain import consistency as CS
    from system.cross_runner import DOMAIN_OF as K_DOMAIN_OF
    tk, vk = E6.load_k()
    fk = E6.fit_k(tk)
    edges = fk["edges"]
    a1, a3 = B.Blame31(B.graph_k(False), B.EQUAL_COST), B.Blame31(B.graph_k(True), B.PRIOR_COST)
    out = {}
    for d, rs in sorted(vk.items()):
        for r in rs:
            Z = E6.z_of(r["R"], r["V"], edges, fk["models"])
            S, es, al, ob = E6.cross_arrays(Z, fk["cal"])
            ca = al.any(axis=1)
            ia, io = fk["inertial"].edges(r["speed"], r["A"], ca)
            t = np.asarray(r["t"], float)
            lab = (t >= r["onset_t"]) if np.isfinite(r["onset_t"]) else np.zeros(len(t), bool)
            out[(d, int(r["phase"]), r["family"])] = {
                "t": t, "n": len(t), "label": lab, "onset_t": float(r["onset_t"]),
                "gps_score": np.asarray(r["gps_score"], np.float32), "gps_alarm": np.asarray(r["gps_alarm"], bool),
                "cross_score": es.max(axis=1).astype(np.float32), "cross_alarm": ca, "cross_layers": es.astype(np.float32), "cross_layer_alarm": al,
                "cross_present": ob.any(axis=1),
                "blame_A1": blame_str(B.blame_run(a1, al, ob, ca)), "blame_A3": blame_str(B.blame_run(a3, al, ob, ca, ia, io)),
                "blame_V3": blame_str([x if a else None for x, a in zip(CS.blame(edges, al, ob, K_DOMAIN_OF), ca)])}
        log("kveh", d, len(out))
    save({"series": out, "edges": [e.name for e in edges], "tau_cross": float(fk["cal"].tau)}, "kveh.pkl")


# ------------------------------------------------------------------------------------------------------------- C vehicle
def stage_cveh():
    import WP6_S2_comma as SC
    import WP8_S6_eval as E6
    from crossdomain import blame31 as B
    from crossdomain import consistency as CS
    tc, vc = E6.load_c()
    L8.assert_not_h31([n.replace("_", "|", 1) for n in vc])
    fc = E6.fit_c(tc)
    edges = fc["edges"]
    a1 = B.Blame31(B.graph_c(), B.EQUAL_COST)
    out = {}
    for n, d in sorted(vc.items()):
        k = "g10" if d["gyro_hz"] <= 20 else "g100"
        for ep in d["episodes"]:
            Z = E6.z_of(ep["R"], ep["V"], edges, fc["models"][k])
            S, es, al, ob = E6.cross_arrays(Z, fc["cal"])
            ca = al.any(axis=1)
            t = np.asarray(ep["t"], float)
            lab = (t >= ep["onset_t"]) if np.isfinite(ep["onset_t"]) else np.zeros(len(t), bool)
            out[(n, int(ep["window"]), ep["family"], int(ep["rep"]))] = {
                "t": t, "n": len(t), "label": lab, "onset_t": float(ep["onset_t"]),
                "cross_score": es.max(axis=1).astype(np.float32), "cross_alarm": ca, "cross_layers": es.astype(np.float32), "cross_layer_alarm": al,
                "cross_present": ob.any(axis=1),
                "blame_A1": blame_str(B.blame_run(a1, al, ob, ca)),
                "blame_V3": blame_str([x if a else None for x, a in zip(CS.blame(edges, al, ob, SC.DOMAIN_OF), ca)])}
        log("cveh", n, len(out))
    save({"series": out, "edges": [e.name for e in edges], "tau_cross": float(fc["cal"].tau)}, "cveh.pkl")


# ------------------------------------------------------------------------------------------------------------- LiDAR
def stage_lidar():
    import WP8_S3_freeze as F
    from gps import stream as GS
    frame = pd.read_pickle(ROOT / "results" / "WP8" / "S3" / "frame.pkl")
    z = np.load(ROOT / "results" / "WP8" / "scores" / "S3" / "lidar_val.npz", allow_pickle=True)
    s100 = F.lodo_scores(frame, F.cfg_by_name("r3", "tail2h|zmulti|E7"))
    assert np.array_equal(s100["score"].to_numpy(float), z["v31_score"].astype(float)) and np.array_equal(s100["alarm"].to_numpy(bool), z["v31_alarm"].astype(bool)), \
        "L100 LODO scores differ from results/WP8/scores/S3/lidar_val.npz"
    log("L100 equals the S3 score file", len(s100))
    s125 = F.lodo_scores(frame, F.cfg_by_name("r3", "tail2h|zmulti|E6@1.25"))
    log("L125 LODO scores", len(s125))
    out = {"drives": {}, "kinds": LIDAR_KINDS}
    for d in sorted(s100["drive"].astype(str).unique()):
        L8.assert_not_h31([str(GS.oxts_dir(d))])
        tox = np.asarray(GS.load_oxts(d)["t"], float)
        rec = {"t_oxts": tox}
        for tag, sdf in (("L100", s100), ("L125", s125)):
            x = sdf[sdf["drive"].astype(str) == d]
            lay = np.column_stack([x[f"raw_{l}"].to_numpy(float) for l in ("L1", "L2a", "L2c", "L2d")]).astype(np.float32)
            rec[tag] = {"kind": x["kind"].astype(str).to_numpy(), "attack": x["attack"].astype(str).to_numpy(), "i": x["i"].to_numpy(int),
                        "ep": x["ep"].fillna(-1).to_numpy(int), "step": x["step"].fillna(-1).to_numpy(int),
                        "t": tox[np.clip(x["i"].to_numpy(int), 0, len(tox) - 1)], "score": x["score"].to_numpy(np.float32), "alarm": x["alarm"].to_numpy(bool),
                        "layers": lay}
        out["drives"][d] = rec
        log("lidar", d, {k: int((rec["L100"]["kind"] == k).sum()) for k in ("clean", "att", "pdep")})
    save(out, "lidar.pkl")


# ------------------------------------------------------------------------------------------------------------- CAN
def can_family(name):
    f = name.replace("_attack_2", "").replace("_attack", "")
    return f


def stage_can():
    lock = json.loads((ROOT / "locks" / "V31_val.json").read_text())["domains"]["can"]["road_val"]
    L8.assert_not_h31([x["path"] for x in lock])
    out = []
    for x in lock:
        name = Path(x["path"]).stem
        z = np.load(ROOT / "results" / "WP8" / "scores" / "S5" / f"can_val_{name}.npz")
        y = z["y"] > 0
        amb = name.startswith("ambient")
        out.append({"name": name, "group": name, "kind": "clean" if amb else "attack", "family": "none" if amb else can_family(name),
                    "score": z["score"].astype(np.float32), "dom_alarm": z["alarm"].astype(bool), "label": y,
                    "layers": np.column_stack([z[f"score_{l}"] for l in ("L1", "L3c", "L3d")]).astype(np.float32),
                    "layer_alarm": np.column_stack([z[f"alarm_{l}"] for l in ("L1", "L3c", "L3d")]).astype(bool)})
        log("can", name, len(y), int(y.sum()))
    save({"series": out, "layer_names": ["can.L1", "can.L3c", "can.L3d"]}, "can.pkl")


# ------------------------------------------------------------------------------------------------------------- V2X
def tick_max(k, v, n):
    out = np.zeros((n,) + v.shape[1:], np.float32)
    np.maximum.at(out, k, v)
    return out


def tick_any(k, v, n):
    out = np.zeros((n,) + v.shape[1:], bool)
    np.logical_or.at(out, k, v)
    return out


def tick_family(k, fam, n):
    out = np.full(n, "", object)
    df = pd.DataFrame({"k": k, "f": fam})
    df = df[df["f"] != ""]
    if len(df):
        m = df.groupby("k")["f"].agg(lambda s: s.value_counts().index[0])
        out[m.index.to_numpy()] = m.to_numpy()
    return out


def stage_v2x():
    import WP5_S5_dev as dev5
    from WP5_S2_l1 import aname
    from system.v2x_runner import LAYER_NAMES, V2XPhysicsDomain
    from v2x import splitting
    dom = V2XPhysicsDomain.load(ROOT / "results" / "WP7" / "frozen_v2x")
    v, sp = dev5.load_frames()
    va = splitting.rows_of(v, sp["val"])
    del v
    va = va[va["label"] != 12]
    groups = sorted(va["group"].astype(str).unique(), key=lambda g: int(g))
    L8.assert_not_h31([f"veremi_block_{g}" for g in groups])
    part = CACHE / "v2x_parts"
    part.mkdir(parents=True, exist_ok=True)
    for g in groups:
        f = part / f"block_{g}.pkl"
        if f.exists():
            log("skip v2x block", g)
            continue
        blk = va[va["group"].astype(str) == g].sort_values("t", kind="stable").reset_index(drop=True)
        lab, snd, t = blk["label"].to_numpy(), blk["sender"].to_numpy(), blk["t"].to_numpy(float)
        x, y = blk["x"].to_numpy(float), blk["y"].to_numpy(float)
        bad = pd.Series(lab > 0).groupby(snd).any()
        dur = pd.Series(t).groupby(snd).agg(lambda s: s.max() - s.min())
        cand = sorted(s for s in dur.index if not bad[s] and dur[s] >= EGO_MIN_S)
        k_ = int(np.ceil(len(cand) / EGOS_PER_BLOCK)) if cand else 1
        pick = cand[::max(k_, 1)][:EGOS_PER_BLOCK]
        series, clean_msg = [], []
        for e in pick:
            me = snd == e
            te, xe, ye = t[me], x[me], y[me]
            t0, t1 = te.min(), te.max()
            w = (t >= t0) & (t <= t1) & ~me
            ex, ey = np.interp(t[w], te, xe), np.interp(t[w], te, ye)
            idx = np.flatnonzero(w)[np.hypot(x[w] - ex, y[w] - ey) <= RADIUS_M]
            if len(idx) < 2:
                continue
            sub = blk.iloc[idx].copy().reset_index(drop=True)
            sub["rx_id"] = "ego"
            raws = dom.raws(sub)
            cal = dom.calibrated(raws)
            C = np.column_stack([cal[nm] for nm in LAYER_NAMES]).astype(np.float32)
            comb = C.max(axis=1)
            alarm = comb >= dom.comb_thr
            lalarm = np.column_stack([cal[nm] >= dom.thr[nm] for nm in LAYER_NAMES])
            n = int(np.ceil(t1 - t0)) + 1
            kk = np.clip(np.floor(t[idx] - t0).astype(np.int64), 0, n - 1)
            lb = lab[idx]
            gen = lb == 0
            clean_msg.append(comb[gen])

            def pack(sel, kind, fam_t, lab_t):
                ks = kk[sel]
                return {"group": g, "name": f"{g}/ego{e}/{kind}", "kind": kind, "ego": str(e), "score": tick_max(ks, comb[sel], n), "layers": tick_max(ks, C[sel], n),
                        "dom_alarm": tick_any(ks, alarm[sel], n), "layer_alarm": tick_any(ks, lalarm[sel], n), "count": np.bincount(ks, minlength=n)[:n].astype(np.float32),
                        "label": lab_t, "fam": fam_t}
            series.append(pack(gen, "clean", np.full(n, "", object), np.zeros(n, bool)))
            if (~gen).any():
                fam = np.where(gen, "", np.array([aname(int(c)) if c > 0 else "" for c in lb], object))
                series.append(pack(np.ones(len(idx), bool), "attack", tick_family(kk, fam, n), tick_any(kk, ~gen, n)))
        save_obj = {"group": g, "series": series, "clean_msg": np.concatenate(clean_msg) if clean_msg else np.zeros(0, np.float32), "candidates": len(cand), "picked": len(pick)}
        tmp = f.with_suffix(".tmp")
        pickle.dump(save_obj, open(tmp, "wb"), protocol=4)
        tmp.replace(f)
        log("v2x block", g, "candidates", len(cand), "egos", len(pick), "series", len(series), "messages", len(blk))
    allp = [pickle.load(open(part / f"block_{g}.pkl", "rb")) for g in groups]
    save({"series": [s for p in allp for s in p["series"]], "clean_msg": {p["group"]: p["clean_msg"] for p in allp},
          "blocks": {p["group"]: {"candidates": p["candidates"], "picked": p["picked"]} for p in allp}, "layer_names": LAYER_NAMES, "comb_thr": float(dom.comb_thr)}, "v2x.pkl")


# ------------------------------------------------------------------------------------------------------------- network
def stage_net():
    import WP8_S4_eval as E4
    v = E4.load_val()
    z = np.load(ROOT / "results" / "WP8" / "scores" / "S4" / "network_val.npz", allow_pickle=True)
    assert (z["block"] == v["blk"].to_numpy()).all() and (z["fam"] == v["fam"].to_numpy()).all()
    host = ((v["src_id"].to_numpy() == HOST) | (v["dst_id"].to_numpy() == HOST))
    out = []
    for b in sorted(v["blk"].unique()):
        idx = np.flatnonzero((v["blk"].to_numpy() == b) & host)
        if not len(idx):
            continue
        mins = v["minute"].to_numpy()[idx].astype(np.int64)
        fam = v["fam"].to_numpy()[idx].astype(object)
        att = fam != "BENIGN"
        u, inv = np.unique(mins, return_inverse=True)
        nmin = int(u.max() - u.min()) + 2
        j = (u - u.min()).astype(int)
        jf = j[inv]
        rec = {"group": b, "name": b, "day": b.split("|")[0], "kind": "attack" if att.any() else "clean", "host_flows": int(len(idx)),
               "audit_flows": int(v["audit"].to_numpy()[idx].sum())}
        for tag, sc, al in (("F1", z["F1_score"], z["F1_alarm"]), ("RC5", z["RC5_score"], z["RC5_alarm"])):
            S = np.zeros(nmin, np.float32)
            A = np.zeros(nmin, bool)
            np.maximum.at(S, jf, sc[idx].astype(np.float32))
            np.logical_or.at(A, jf, al[idx].astype(bool))
            hold = 1 if tag == "F1" else 0                   # F1: minute m visible from the close of m (held during m + 1); RC5: placed in minute m
            Sh, Ah = np.zeros(nmin, np.float32), np.zeros(nmin, bool)
            Sh[hold:], Ah[hold:] = S[:nmin - hold], A[:nmin - hold]
            rec[tag] = {"score": np.repeat(Sh, 60), "dom_alarm": np.repeat(Ah, 60)}
        labm = np.zeros(nmin, bool)
        famm = np.full(nmin, "", object)
        np.logical_or.at(labm, jf, att)
        famm[j] = pd.Series(np.where(att, fam, "")).groupby(inv).agg(lambda s: next((x for x in s.value_counts().index if x), "")).to_numpy()
        cnt = np.bincount(jf, minlength=nmin).astype(np.float32)
        for tag, hold in (("F1", 1), ("RC5", 0)):
            lh, fh, ch = np.zeros(nmin, bool), np.full(nmin, "", object), np.zeros(nmin, np.float32)
            lh[hold:], fh[hold:], ch[hold:] = labm[:nmin - hold], famm[:nmin - hold], cnt[:nmin - hold]
            rec[tag].update(label=np.repeat(lh, 60), fam=np.repeat(fh, 60), count=np.repeat(ch, 60))
        rec["n"] = nmin * 60
        out.append(rec)
        log("net", b, rec["kind"], nmin, "minutes", int(labm.sum()), "attack minutes")
    save({"series": out}, "net.pkl")


STAGES = {"kveh": stage_kveh, "cveh": stage_cveh, "lidar": stage_lidar, "can": stage_can, "v2x": stage_v2x, "net": stage_net}

if __name__ == "__main__":
    for st in sys.argv[1:] or list(STAGES):
        if (CACHE / f"{st}.pkl").exists():
            log("skip", st)
            continue
        log("stage", st)
        STAGES[st]()
