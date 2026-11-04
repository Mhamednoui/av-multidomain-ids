"""WP8 S7 system simulation (M3-style) on the H31 sources: the FROZEN v3 system (fusion.system.load_system(2), results/WP6/system_v2.pkl) and the FROZEN v3.1 system (frozen_system31, MX|L100|b2|m2w5|g15|d0|k1)
on the SAME composites, paired, plus the labelled variants (network RC5, blame A3, budget 1.5 %, motion-critical SAFE_STOP). One scoring: no threshold, calibration or parameter is fitted here.
Composite construction = tools/WP8_S2_sim.py (WP7 S2 construction: vehicle runs, LiDAR per-scan kinds and PointDrop episodes, CAN / V2X episodes, network blocks, clean timelines on the clean D10 host blocks,
seeds [31, 2, ord(family)] and [31, 100 + i]) with the H31 sources: K = 13 H31 KITTI drives, C = 21 comma Chunk_2 routes, CAN = ROAD test captures, V2X = VeReMi test egos, network = D10 test host view.
Composites carry RAW tick values (score, count, own alarm); each system applies its own frozen density transform, entry ECDFs, combiner, threshold and correlator (nothing is recalibrated on H31).
v3 inputs differ from v3.1 only where the domain changed: LiDAR (v3 stack score / alarm), network (v3 stack H, placed in the flow minute, hold 0, RC5 labels), blame (v3 consistency blame + v3 tick_blame).
`--material val` = dry run on the V31_val sources of tools/WP8_S2_build.py (S2 caches): the frozen v3.1 system in-sample numbers must equal results/WP8/S2/frozen_system31/system31.json "in_sample_check".
Output: results/WP8/S7/system_<tag>.json (+ per-chunk parts results/WP8/S7/parts/sim_<tag>_<run>_<fam>.pkl, resumable), scores results/WP8/scores/S7/system_<fam>_<run>.npz.
Run: python -u -W ignore tools/WP8_S7_sim.py [--material h31|val] [--tag h31] [--runs v31,v3,...]"""
import argparse
import copy
import json
import pickle
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S7_lib as S7

import numpy as np

import WP8_S2_sim as M
from fusion import correlator as CR
from fusion.system import load_system
from fusion.system31 import MC_OR_CROSS, Correlator31, load_system31

T0 = time.time()
log = M.log

PART_KEYS = {"gps": ("X", "own", "label"), "cross": ("X", "own", "label", "blame_A1", "blame_V3", "blame_A3"),
             "lidar": ("X", "own", "label", "X_V3", "own_V3"), "can": ("X", "own", "label"), "v2x": ("X", "own", "label", "cnt"),
             "network": ("X", "own", "label", "X_RC5", "own_RC5", "label_RC5", "X_V3", "own_V3")}
M.PART_KEYS.clear()
M.PART_KEYS.update(PART_KEYS)


def chain_vehicle(self, P, n):
    """Builder.chain_vehicle of WP8_S2_sim with the S7 LiDAR keys (clean vehicle runs chained to n ticks)."""
    pos = 0
    while pos < n:
        key = self.clean_vehicle_key()
        v = self.veh[key]
        m = min(v["n"], n - pos)
        for d in (("gps", "cross") if self.fam == "K" else ("cross",)):
            self.place(P, d, pos, v[d], 0, m, label=False)
        if self.fam == "K":
            lt = self.S.lidar_ticks(key[0], key[1] / M.PHASES, m)
            for kk in ("X", "own", "X_V3", "own_V3"):
                P["lidar"][kk][pos:pos + m] = lt[kk][:m]
        pos += m


M.Builder.chain_vehicle = chain_vehicle


# ================================================================================================================ sources
class Sources31:
    """Raw tick sources in the interface of WP8_S2_sim.Builder / attack_composites / clean_timelines (X = RAW tick value)."""

    def __init__(self, kveh, cveh, lid, can, v2x, net, has_v3=True):
        self.has_v3 = has_v3
        self.K, self.C = {}, {}
        for key, s in kveh["series"].items():
            self.K[key] = {"n": s["n"], "label": s["label"], "group": key[0],
                           "gps": {"X": s["gps_score"].astype(float), "own": s["gps_alarm"], "label": s["label"]},
                           "cross": {"X": s["cross_score"].astype(float), "own": s["cross_alarm"], "label": s["label"], "blame_A1": s["blame_A1"], "blame_V3": s["blame_V3"], "blame_A3": s["blame_A3"]}}
        for key, s in cveh["series"].items():
            self.C[key] = {"n": s["n"], "label": s["label"], "group": key[0],
                           "cross": {"X": s["cross_score"].astype(float), "own": s["cross_alarm"], "label": s["label"], "blame_A1": s["blame_A1"], "blame_V3": s["blame_V3"], "blame_A3": s["blame_A1"]}}
        self.lid = lid
        self.scan = {}
        for d, rec in lid["drives"].items():
            self.scan[d] = {v: rec[v] for v in ("L100", "V3") if v in rec}
        self.CAN = [{**s, "X": s["score"].astype(float), "own": s["dom_alarm"]} for s in can]
        self.V2X = [{**s, "X": s["score"].astype(float), "own": s["dom_alarm"], "cnt": s["count"]} for s in v2x["series"]]
        self.NET = []
        for s in net["series"]:
            f1, rc, v3 = s["F1"], s["RC5"], s.get("V3")
            e = {"name": s["name"], "group": s["name"], "day": s["day"], "kind": s["kind"], "n": s["n"], "host_flows": s["host_flows"],
                 "X": f1["score"].astype(float), "own": f1["dom_alarm"], "label": f1["label"], "fam": f1["fam"],
                 "X_RC5": rc["score"].astype(float), "own_RC5": rc["dom_alarm"], "label_RC5": rc["label"]}
            if v3 is not None:
                e["X_V3"], e["own_V3"] = v3["score"].astype(float), v3["dom_alarm"]
            self.NET.append(e)

    def lidar_ticks(self, d, off, n, overlay=None):
        out = {"X": np.zeros(n), "own": np.zeros(n, bool), "label": np.zeros(n, bool), "X_V3": np.zeros(n), "own_V3": np.zeros(n, bool), "present": np.zeros(n, bool)}
        a = self.scan[d]["L100"]
        clean = np.flatnonzero(a["kind"] == "clean")
        rows = clean
        if overlay is not None:
            ov = np.flatnonzero(overlay)
            keep = ~np.isin(a["i"][clean], a["i"][ov])
            rows = np.r_[clean[keep], ov]
        k = np.floor(a["t"][rows] - off).astype(int)
        ok = (k >= 0) & (k < n)
        r, kk = rows[ok], k[ok]
        for var, sx in (("L100", ""), ("V3", "_V3")):
            if var not in self.scan[d]:
                continue
            x = self.scan[d][var]
            np.maximum.at(out["X" + sx], kk, x["score"][r].astype(float))
            out["own" + sx][kk[x["alarm"][r]]] = True
        out["label"][kk[a["kind"][r] != "clean"]] = True
        out["present"][kk] = True
        return out


def load_sources(material):
    if material == "val":
        c = M.CACHE
        lid = pickle.load(open(c / "lidar.pkl", "rb"))
        for d, rec in lid["drives"].items():          # S2 caches carry the LODO scores of frozen_lidar31 (no v3 column): dry run of the v3.1 path only
            rec.pop("L125", None)
        can = pickle.load(open(c / "can.pkl", "rb"))["series"]
        v2 = pickle.load(open(c / "v2x.pkl", "rb"))
        net = pickle.load(open(c / "net.pkl", "rb"))
        for s in net["series"]:
            for tag in ("F1", "RC5"):
                s[tag] = dict(s[tag])
        return Sources31(pickle.load(open(c / "kveh.pkl", "rb")), pickle.load(open(c / "cveh.pkl", "rb")), lid, can, v2, net, has_v3=False)
    c = S7.CACHE
    can = pickle.load(open(c / "can.pkl", "rb"))["series"]
    return Sources31(pickle.load(open(c / "kveh.pkl", "rb")), pickle.load(open(c / "cveh.pkl", "rb")), pickle.load(open(c / "lidar.pkl", "rb")), can,
                     pickle.load(open(c / "v2x.pkl", "rb")), pickle.load(open(c / "net.pkl", "rb")), has_v3=True)


# ================================================================================================================ one run of one system over all composites of a family
def parts_for(c, names, lvar, nvar, blame_key):
    P, n = c["parts"], c["n"]
    parts = {}
    for d in names:
        p = P[d]
        sx = "_V3" if (d == "lidar" and lvar == "V3") else ("_RC5" if (d == "network" and nvar == "RC5") else ("_V3" if (d == "network" and nvar == "V3") else ""))
        parts[d] = {"score": p["X" + sx], "count": p["cnt"] if d == "v2x" else np.ones(n), "dom_alarm": p["own" + sx], "layers": np.zeros((n, 1)), "layer_alarm": np.zeros((n, 1), bool)}
        if d == "cross":
            parts[d]["blame"] = p[blame_key]
    return parts


def run_all(F, sysobj, lvar="L100", nvar="F1", blame_key="blame_A1", keep_scores=False):
    """Every clean timeline and attack composite of F through sysobj.run (explanations on) with the FROZEN thresholds."""
    names = F.names
    rc_, ra_, store = [], [], {"clean": [], "attack": []}
    rc_label = nvar in ("RC5", "V3")
    for c in F.clean:
        o = sysobj.run(parts_for(c, names, lvar, nvar, blame_key))
        ev = o["events"]
        own = o["own"]
        rc_.append({"id": c["id"], "group": c["group"], "n": c["n"], "hours": c["n"] / 3600.0, "alarm_ticks": int(o["alarm"].sum()), "events": len(ev),
                    "levels": {lv: sum(e.response == lv for e in ev) for lv in CR.LEVELS[1:]},
                    "explained": int(sum("first alarm: system alarm" in e.explanation for e in ev)), "event_domains": [e.domains for e in ev], "event_blamed": [e.blamed for e in ev],
                    "event_response": [e.response for e in ev], "own_share": {d: float(own[:, j].mean()) for j, d in enumerate(names)}})
        if keep_scores:
            store["clean"].append((c["id"], c["group"], o["score"], o["alarm"], np.zeros(c["n"], bool), float(sysobj.threshold if hasattr(sysobj, "threshold") else sysobj.fusion.threshold)))
    for c in F.att:
        lab = c.get("label_RC5", c["label"]) if rc_label else c["label"]
        onset = c.get("onset_RC5", c["onset"]) if rc_label else c["onset"]
        o = sysobj.run(parts_for(c, names, lvar, nvar, blame_key))
        ev = o["events"]
        r = {"id": c["id"], "scenario": c["scenario"], "type": c["type"], "group": c["group"], "attacked_key": c["attacked_key"], "n": c["n"], "events": len(ev), "detected": False,
             "explained": int(sum("first alarm: system alarm" in e.explanation for e in ev)), "alarm_ticks": int(o["alarm"].sum()), "tick_detected": bool((o["alarm"] & lab).any())}
        best = None
        for e in ev:
            ct = np.arange(e.start, e.end + 1)
            ct = ct[o["alarm"][ct] & lab[ct]]
            if len(ct) and (best is None or ct[0] < best[0]):
                best = (int(ct[0]), e)
        if best is not None:
            r.update(detected=True, delay=best[0] - onset, delay_available=best[0] + 1 - c["onset_true"], blamed=best[1].blamed,
                     blame="undecided" if best[1].blamed == "undecided" else ("correct" if best[1].blamed in c["true_sensors"] else "wrong"), event_domains=best[1].domains)
        over = [e for e in ev if e.end >= onset] if onset >= 0 else []
        r["response_max"] = max((e.response for e in over), key=lambda x: CR.LEVELS.index(x)) if over else None
        ra_.append(r)
        if keep_scores:
            store["attack"].append((c["id"], c["group"], o["score"], o["alarm"], lab, float(sysobj.threshold if hasattr(sysobj, "threshold") else sysobj.fusion.threshold)))
    return ra_, rc_, store


def save_scores(store, fam, run):
    S7.SCORES.mkdir(parents=True, exist_ok=True)
    for part, rows in store.items():
        if not rows:
            continue
        np.savez_compressed(S7.SCORES / f"system_{fam}_{part}_{run}.npz", ids=np.array([r[0] for r in rows]), groups=np.array([str(r[1]) for r in rows]), lens=np.array([len(r[2]) for r in rows]),
                            score=np.concatenate([r[2] for r in rows]).astype(np.float32), alarm=np.concatenate([r[3] for r in rows]), label=np.concatenate([r[4] for r in rows]),
                            threshold=np.array([r[5] for r in rows]))


# ================================================================================================================ paired comparison (group bootstrap, B = 2000, seed 31)
def per_type(F, recs, fn):
    per = {}
    for i in F.single:
        c, r = F.att[i], recs[i]
        v = fn(c, r)
        if v is None:
            continue
        per.setdefault((c["scenario"], c["type"]), []).append((float(v), c["group"], i))
    return per


def paired_types(F, ra, rb, fn, types=None, seed=M.BSEED, nb=M.NB):
    """mean over types of the mean of fn (a) minus (b) on the SAME composites; CI = bootstrap over groups inside every type (the same group draw for both systems)."""
    A, Bv = per_type(F, ra, fn), per_type(F, rb, fn)
    keys = [t for t in A if t in Bv and (types is None or t in types)]
    if not keys:
        return None
    data = []
    for t in keys:
        ia = {i: v for v, g, i in A[t]}
        ib = {i: v for v, g, i in Bv[t]}
        common = sorted(set(ia) & set(ib))
        grp = np.array([F.att[i]["group"] for i in common])
        data.append((np.array([ia[i] for i in common]), np.array([ib[i] for i in common]), grp))
    est = float(np.mean([a.mean() - b.mean() for a, b, _ in data if len(a)]))
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(nb):
        m = []
        for a, b, g in data:
            if not len(a):
                continue
            ug = np.unique(g)
            if len(ug) >= 3:
                pick = rng.choice(ug, len(ug))
                sel = np.concatenate([np.flatnonzero(g == u) for u in pick])
            else:
                sel = rng.integers(len(a), size=len(a))
            m.append(a[sel].mean() - b[sel].mean())
        bs.append(np.mean(m))
    return {"diff": est, "ci": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))], "types": len(keys)}


def paired_clean(rca, rcb, key, seed=M.BSEED, nb=M.NB):
    """difference of the pooled rates (alarm ticks / ticks, events / hour, ...) a - b, bootstrap over clean timelines."""
    num = lambda rc: np.array([r[key] if not isinstance(r[key], dict) else r[key]["SAFE_STOP"] for r in rc], float)
    den = np.array([r["n"] if key == "alarm_ticks" else r["hours"] for r in rca], float)
    na, nbv = num(rca), num(rcb)
    est = float(na.sum() / den.sum() - nbv.sum() / den.sum())
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(nb):
        i = rng.integers(len(na), size=len(na))
        bs.append(na[i].sum() / den[i].sum() - nbv[i].sum() / den[i].sum())
    return {"diff": est, "ci": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]}


def paired_block(F, ra, rb, rca, rcb):
    out = {"det_single": paired_types(F, ra, rb, lambda c, r: r["detected"]), "det_heldout": paired_types(F, ra, rb, lambda c, r: r["detected"], set(F.held)) if F.held else None,
           "blame_correct": paired_types(F, ra, rb, lambda c, r: None if not r["detected"] else r["blame"] == "correct"),
           "blame_wrong": paired_types(F, ra, rb, lambda c, r: None if not r["detected"] else r["blame"] == "wrong"),
           "fa_tick": paired_clean(rca, rcb, "alarm_ticks"), "events_per_hour": paired_clean(rca, rcb, "events")}
    ss_a, ss_b = [r["levels"]["SAFE_STOP"] for r in rca], [r["levels"]["SAFE_STOP"] for r in rcb]
    hrs = np.array([r["hours"] for r in rca])
    out["safe_stop_per_hour"] = {"diff": float(np.sum(ss_a) / hrs.sum() - np.sum(ss_b) / hrs.sum())}
    by = {}
    for dom in sorted({F.att[i]["attacked_key"] for i in F.single}):
        ts = {(F.att[i]["scenario"], F.att[i]["type"]) for i in F.single if F.att[i]["attacked_key"] == dom}
        by[dom] = paired_types(F, ra, rb, lambda c, r: r["detected"], ts)
    out["by_attacked_domain"] = by
    return out


# ================================================================================================================ main
def systems(has_v3):
    S31 = load_system31()
    out = {"v31": ("v3.1 primary (frozen_system31 MX|L100|b2|m2w5|g15|d0|k1, F1, blame A1)", {f: S31[f] for f in "KC"}, dict(lvar="L100", nvar="F1", blame_key="blame_A1"))}
    if has_v3:
        S3 = load_system(2)
        out["v3"] = ("v3 frozen (load_system(2), v3 LiDAR / network / blame)", {f: S3[f] for f in "KC"}, dict(lvar="V3", nvar="V3", blame_key="blame_V3"))
    out["v31_RC5"] = ("v3.1 variant: network RC5 (Evidence at flow arrival)", {f: S31[f] for f in "KC"}, dict(lvar="L100", nvar="RC5", blame_key="blame_A1"))
    out["v31_blameA3"] = ("v3.1 variant: blame A3 (accelerometer-anchored inertial edges)", {f: S31[f] for f in "KC"}, dict(lvar="L100", nvar="F1", blame_key="blame_A3"))
    b15 = S7.OUT / "frozen_system31_b15" / "system31.pkl"
    if b15.exists():
        sb = pickle.load(open(b15, "rb"))
        out["v31_b15"] = ("v3.1 variant: system budget 1.5 % (frozen_system31_b15)", {f: sb[f] for f in "KC"}, dict(lvar="L100", nvar="F1", blame_key="blame_A1"))
    mc = {}
    for f in "KC":
        s = copy.copy(S31[f])
        cr = S31[f].correlator.to_dict()
        cr["corroborators"] = MC_OR_CROSS
        s.correlator = Correlator31(**cr)
        mc[f] = s
    out["v31_mcSS"] = ("v3.1 variant: motion-critical SAFE_STOP corroboration (gps, lidar, can, cross)", mc, dict(lvar="L100", nvar="F1", blame_key="blame_A1"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--material", default="h31")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--runs", default=None)
    a = ap.parse_args()
    tag = a.tag or a.material
    if a.material == "h31":
        S7.open_guard()
    S7.journal("S7", f"system simulation {tag}: start", f"material {a.material}; chunks results/WP8/S7/parts/sim_{tag}_*; log results/WP8/logs/S7_sim_{tag}.log")
    S = load_sources(a.material)
    fams = {f: M.Fam(S, f) for f in ("K", "C")}
    S7.PARTS.mkdir(parents=True, exist_ok=True)
    SYS = systems(S.has_v3)
    want = a.runs.split(",") if a.runs else list(SYS)
    res = {"tag": tag, "material": a.material, "runs": {}, "composites": {f: {"attack": len(F.att), "clean_timelines": len(F.clean), "clean_hours": sum(c["n"] for c in F.clean) / 3600.0,
                                                                                "single_types": len(F.types), "held_out_types": len(F.held),
                                                                                "by_scenario": dict(Counter(c["scenario"] for c in F.att))} for f, F in fams.items()}}
    recs = {}
    for name in want:
        if name not in SYS:
            continue
        desc, sysd, kw = SYS[name]
        res["runs"][name] = {"description": desc, "kwargs": kw}
        for f, F in fams.items():
            part = S7.PARTS / f"sim_{tag}_{name}_{f}.pkl"
            if part.exists():
                ra, rc = pickle.load(open(part, "rb"))
                log(name, f, "chunk on disk, skipped")
            else:
                S7.journal("S7", f"sim {tag} {name} {f}: start", "chunk " + part.name)
                ra, rc, store = run_all(F, sysd[f], keep_scores=name in ("v31", "v3"), **kw)
                if name in ("v31", "v3"):
                    save_scores(store, f, f"{tag}_{name}")
                tmp = part.with_suffix(".tmp")
                pickle.dump((ra, rc), open(tmp, "wb"), protocol=4)
                tmp.replace(part)
                S7.journal("S7", f"sim {tag} {name} {f}: done", "chunk " + part.name)
            recs[(name, f)] = (ra, rc)
            res["runs"][name][f] = {**M.report_run(F, ra, rc), "threshold": float(sysd[f].threshold if hasattr(sysd[f], "threshold") else sysd[f].fusion.threshold)}
        log(name, {f: {m: res["runs"][name][f].get(m) for m in ("fa_tick", "events_per_hour", "SAFE_STOP_per_hour", "det_single", "det_heldout", "blame_correct", "blame_wrong")} for f in fams})
    if "v31" in res["runs"] and "v3" in res["runs"]:
        res["paired_v31_minus_v3"] = {f: paired_block(fams[f], recs[("v31", f)][0], recs[("v3", f)][0], recs[("v31", f)][1], recs[("v3", f)][1]) for f in fams}
    for v in want:
        if v.startswith("v31_") and v in res["runs"] and "v31" in res["runs"]:
            res.setdefault("paired_variant_minus_v31", {})[v] = {f: paired_block(fams[f], recs[(v, f)][0], recs[("v31", f)][0], recs[(v, f)][1], recs[("v31", f)][1]) for f in fams}
    S7.write_json(res, S7.OUT / f"system_{tag}.json")
    S7.journal("S7", f"system simulation {tag}: done", f"results/WP8/S7/system_{tag}.json")


if __name__ == "__main__":
    main()
