"""WP8 S8 step 3: system simulation of frozen v3.1 with and without the reference-health gate (system/health31.py), on the SAME composites (tools/WP8_S7_sim.py construction, sources of S7).
`--material val`: V31_val sources (S2 caches; the gate must not fire, results must equal results/WP8/S2/frozen_system31 in-sample check) -> results/WP8/S8/system_s8_val.json.
`--material h31`: ONE re-scoring on H31, labelled "re-used hold-out, exposure 2 (post-M4 fix), NOT fresh" -> results/WP8/S8/system_s8_h31.json.
Runs: v31_ungated (= S7 v31, must reproduce results/WP8/S7/system_h31.json exactly, rule A3) and v31_gated (gate applied to the saved GPS / cross tick sources and to the LiDAR scan rows; L2c / L2d masked).
Nothing is fitted: the frozen system31 objects, thresholds, ECDFs and correlator are used unchanged. Also reported: health-flag ticks / episodes per clean hour, the blind share of ticks, FA on evaluable ticks,
the share of attack-labelled ticks that are gated (per attacked domain) and detection on attack composites overlapping gated ticks (the gate counts as a miss there).
Chunks (resumable): results/WP8/S8/parts/sim_<tag>_<run>_<fam>.pkl; scores results/WP8/scores/S8/. Run: python -u -W ignore tools/WP8_S8_sim.py --material h31|val"""
import argparse
import json
import pickle
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S7_lib as S7

import numpy as np

S8_OUT = S7.ROOT / "results" / "WP8" / "S8"
S7.OUT, S7.PARTS, S7.SCORES = S7.OUT, S8_OUT / "parts", S7.ROOT / "results" / "WP8" / "scores" / "S8"   # S7.OUT stays readable (frozen_system31_b15); outputs go to S8 below

import WP8_S2_sim as M
import WP8_S7_sim as T
from fusion.system31 import load_system31
from system import health31 as H

log = M.log
HERE_ROOT = S7.ROOT


def journal(what, state=""):
    S7.journal("S8", what, state)


def drive_health(d):
    from gps import stream as GS
    t, pa, va = H.read_oxts_health(GS.oxts_dir(d))
    return t, H.degraded_frames(pa, va)


def gate_sources(material):
    """(ungated Sources31, gated Sources31, info). Both carry the per-tick 'gate' array on the GPS part (measured for the ungated run, applied in the gated run)."""
    if material == "val":
        c = M.CACHE
    else:
        c = S7.CACHE
        S7.open_guard()
        S7.patch_h31_paths()
    kveh = pickle.load(open(c / "kveh.pkl", "rb"))
    cveh = pickle.load(open(c / "cveh.pkl", "rb"))
    lid = pickle.load(open(c / "lidar.pkl", "rb"))
    can = pickle.load(open(c / "can.pkl", "rb"))["series"]
    v2x = pickle.load(open(c / "v2x.pkl", "rb"))
    net = pickle.load(open(c / "net.pkl", "rb"))
    if material == "val":
        for d, rec in lid["drives"].items():
            rec.pop("L125", None)
        for s in net["series"]:
            for tag in ("F1", "RC5"):
                s[tag] = dict(s[tag])
    has_v3 = material != "val"
    health = {d: drive_health(d) for d in sorted({k[0] for k in kveh["series"]})}
    gk = {"series": {}, "edges": kveh["edges"], "tau_cross": kveh["tau_cross"]}
    ug = {"series": {}, "edges": kveh["edges"], "tau_cross": kveh["tau_cross"]}
    info = {"drives": {}}
    for key, s in kveh["series"].items():
        t, deg = health[key[0]]
        g = H.tick_gate(t, deg, s["t"])
        ug["series"][key] = dict(s, gate=g)
        gk["series"][key] = H.gate_series(s, g)
    for d, (t, deg) in health.items():
        info["drives"][d] = {"degraded_frames": int(deg.sum()), "frames": int(len(deg))}
    # LiDAR: pose layers masked at gated scans
    from lidar.domain31 import Domain31
    union = Domain31.load(HERE_ROOT / "results" / "WP8" / "S3" / "frozen_lidar31").union
    n_scan_gated = {}
    lid_g = {"drives": {}, "kinds": lid["kinds"]}
    for d, rec in lid["drives"].items():
        t, deg = health.get(d, (None, None))
        r2 = dict(rec)
        if deg is not None and deg.any():
            assert "frame" in rec, "gated LiDAR drive without raw scores"
            a = dict(rec["L100"])
            gs = deg[np.clip(a["i"], 0, len(deg) - 1)]
            raw = {l: rec["frame"]["v31_raw_" + l].to_numpy(float) for l in H.LIDAR_LAYERS}
            stat, score, alarm = H.mask_union(union, raw, gs)
            a["stat"], a["score"], a["alarm"], a["gate"] = stat, score.astype(a["score"].dtype), alarm, gs
            r2["L100"] = a
            n_scan_gated[d] = int(gs.sum())
        lid_g["drives"][d] = r2
    info["lidar_scans_gated"] = n_scan_gated
    info["union_tau"] = [float(x) for x in union.tau]
    S_u = T.Sources31(ug, cveh, lid, can, v2x, net, has_v3)
    S_g = T.Sources31(gk, cveh, lid_g, can, v2x, net, has_v3)
    for S in (S_u, S_g):
        for key, s in S.K.items():
            s["gps"]["gate"] = (ug if S is S_u else gk)["series"][key]["gate"].astype(float)
    return S_u, S_g, info


def gate_of(c):
    p = c["parts"].get("gps")
    return p["gate"] > 0.5 if p is not None and "gate" in p else np.zeros(c["n"], bool)


def health_stats(F):
    """Gate bookkeeping on a family's composites: health-flag ticks / episodes on clean timelines, gated share of attack-labelled ticks."""
    out = {"clean": {"ticks": 0, "gated_ticks": 0, "episodes": 0, "hours": 0.0}, "attack": {}}
    for c in F.clean:
        g = gate_of(c)
        out["clean"]["ticks"] += c["n"]
        out["clean"]["gated_ticks"] += int(g.sum())
        out["clean"]["episodes"] += int((g & ~np.r_[False, g[:-1]]).sum())
        out["clean"]["hours"] += c["n"] / 3600.0
    lab_t = {}
    for i, c in enumerate(F.att):
        g = gate_of(c)
        lab = np.asarray(c["label"], bool)
        k = c["attacked_key"]
        a = out["attack"].setdefault(k, {"composites": 0, "labelled_ticks": 0, "labelled_gated": 0, "composites_overlapping": 0})
        a["composites"] += 1
        a["labelled_ticks"] += int(lab.sum())
        a["labelled_gated"] += int((lab & g).sum())
        a["composites_overlapping"] += int((lab & g).any())
        lab_t[i] = bool((lab & g).any())
    return out, lab_t


def run_one(F, sysobj, kw, fam, tag, name):
    part = S7.PARTS / f"sim_{tag}_{name}_{fam}.pkl"
    if part.exists():
        ra, rc = pickle.load(open(part, "rb"))
        log(name, fam, "chunk on disk, skipped")
        return ra, rc
    journal(f"sim {tag} {name} {fam}: start", "chunk " + part.name)
    ra, rc, store = T.run_all(F, sysobj, keep_scores=True, **kw)
    T.save_scores(store, fam, f"{tag}_{name}")
    tmp = part.with_suffix(".tmp")
    pickle.dump((ra, rc), open(tmp, "wb"), protocol=4)
    tmp.replace(part)
    journal(f"sim {tag} {name} {fam}: done", "chunk " + part.name)
    return ra, rc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--material", default="h31")
    a = ap.parse_args()
    tag = "s8_" + a.material
    S7.PARTS.mkdir(parents=True, exist_ok=True)
    journal(f"system simulation {tag}: start", f"material {a.material}; chunks results/WP8/S8/parts/sim_{tag}_*; log results/WP8/logs/S8_sim_{a.material}.log")
    S_u, S_g, ginfo = gate_sources(a.material)
    M.PART_KEYS["gps"] = tuple(M.PART_KEYS["gps"]) + ("gate",)
    SYS = T.systems(False)["v31"]
    kw = SYS[2]
    res = {"tag": tag, "material": a.material, "exposure": ("V31_val (choices and no-harm check)" if a.material == "val" else "re-used hold-out, exposure 2 (post-M4 fix), NOT fresh"),
           "gate": {"pos_acc_max_m": H.POS_ACC_MAX, "vel_acc_max_mps": H.VEL_ACC_MAX}, "gate_sources": ginfo, "runs": {}, "health": {}, "paired_gated_minus_ungated": {}}
    recs = {}
    fams = {}
    for f in "KC":
        Fu, Fg = M.Fam(S_u, f), M.Fam(S_g, f)
        fams[f] = (Fu, Fg)
        for name, F in (("v31_ungated", Fu), ("v31_gated", Fg)):
            ra, rc = run_one(F, SYS[1][f], kw, f, tag, name)
            recs[(name, f)] = (ra, rc)
            res["runs"].setdefault(name, {})[f] = {**M.report_run(F, ra, rc), "threshold": float(SYS[1][f].threshold if hasattr(SYS[1][f], "threshold") else SYS[1][f].fusion.threshold)}
        # identical composites: labels / lengths equal in both families
        assert len(Fu.att) == len(Fg.att) and all(np.array_equal(x["label"], y["label"]) for x, y in zip(Fu.att, Fg.att)), "composites differ"
        hs, ov = health_stats(Fg)
        ra_u, rc_u = recs[("v31_ungated", f)]
        ra_g, rc_g = recs[("v31_gated", f)]
        for side, rc in (("ungated", rc_u), ("gated", rc_g)):
            ticks = sum(r["n"] for r in rc)
            alarms = sum(r["alarm_ticks"] for r in rc)
            hs["clean"][f"fa_tick_{side}_all_ticks"] = alarms / ticks
            hs["clean"][f"fa_tick_{side}_evaluable_ticks"] = alarms / max(ticks - hs["clean"]["gated_ticks"], 1) if side == "gated" else alarms / ticks
            hs["clean"][f"events_per_hour_{side}"] = sum(r["events"] for r in rc) / sum(r["hours"] for r in rc)
        hs["clean"]["health_flag_ticks_per_hour"] = hs["clean"]["gated_ticks"] / hs["clean"]["hours"]
        hs["clean"]["health_episodes_per_hour"] = hs["clean"]["episodes"] / hs["clean"]["hours"]
        hs["clean"]["blind_share_of_ticks"] = hs["clean"]["gated_ticks"] / max(hs["clean"]["ticks"], 1)
        # detection on attack composites overlapping gated labelled ticks vs the others (single-domain composites only), gated vs ungated system
        idx = list(Fg.single)
        o = [i for i in idx if ov[i]]
        n_ = [i for i in idx if not ov[i]]
        hs["attack_detection_split"] = {"overlapping_gated": {"n": len(o), "event_detection_ungated": float(np.mean([ra_u[i]["detected"] for i in o])) if o else None,
                                                             "event_detection_gated": float(np.mean([ra_g[i]["detected"] for i in o])) if o else None},
                                        "not_overlapping": {"n": len(n_), "event_detection_ungated": float(np.mean([ra_u[i]["detected"] for i in n_])) if n_ else None,
                                                            "event_detection_gated": float(np.mean([ra_g[i]["detected"] for i in n_])) if n_ else None}}
        res["health"][f] = hs
        res["paired_gated_minus_ungated"][f] = T.paired_block(Fg, ra_g, ra_u, rc_g, rc_u)
        log(f, {m: (res["runs"]["v31_ungated"][f][m], res["runs"]["v31_gated"][f][m]) for m in ("fa_tick", "events_per_hour", "SAFE_STOP_per_hour", "det_single", "det_heldout")})
    S7.write_json(res, S8_OUT / f"system_{tag}.json")
    journal(f"system simulation {tag}: done", f"results/WP8/S8/system_{tag}.json")


if __name__ == "__main__":
    main()
