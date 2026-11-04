"""WP8 S2 simulation and candidate evaluation on V31_val (notes/WP8_v31.md "S2 round 1": material, composites, calibration protocol, grid, selection).

Sources: ../data_extra/cache_v3/WP8/S2/{kveh,cveh,lidar,can,v2x,net}.pkl (tools/WP8_S2_build.py). Every source series is calibrated LEAVE-ONE-GROUP-OUT per entry
(ECDF of the clean ticks of the other groups of its domain; V2X density transform G(M)^k with G from the other blocks), then composites are assembled with the WP7 S2
construction (vehicle runs, LiDAR per-scan kinds / episodes, CAN / V2X episodes, network blocks, clean timelines on the clean D10 host blocks). The system threshold is
the tie-safe budget b of the fused clean-timeline ticks: leave-one-timeline-out for the clean metrics, all timelines for the attack composites.
Candidates: fusion/system31.py SystemV31 / Correlator31 settings (A, L, b, P, G, D, k); references R0 (v3 recipe) and R0b. The chosen candidate is re-run through
SystemV31.decide (explanations, tick blame) and must equal the grid summary.
Usage: python -u -W ignore tools/WP8_S2_sim.py [--tag r1]   Output: results/WP8/S2/<tag>_eval.json, <tag>_grid.json, scores in results/WP8/scores/S2/
"""
import argparse
import itertools
import json
import pickle
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True

import numpy as np

from common.calibration import ECDFCalibrator
from common.metrics import budget_threshold
from fusion import correlator as CR
from fusion.system import DensityTransform
from fusion.system31 import MC_OR_CROSS, Correlator31, SystemV31

CACHE = Path(__file__).resolve().parent.parent.parent / "data_extra" / "cache_v3" / "WP8" / "S2"
OUT = ROOT / "results" / "WP8" / "S2"
SCORES = ROOT / "results" / "WP8" / "scores" / "S2"
ONSET, PHASES, SEG = 3, 10, 120
K_DOMAINS = ["gps", "lidar", "can", "network", "v2x", "cross"]
C_DOMAINS = ["can", "network", "v2x", "cross"]
GPS_FAMS = ["drift", "accel_drift", "doppler_spoof", "meaconing"]
COORD = {"K": ["gps_can"], "C": ["gnss_can", "can_bus"]}
TRUTH = {"drift": {"gps"}, "accel_drift": {"gps"}, "doppler_spoof": {"gps"}, "meaconing": {"gps"}, "gps_can": {"gps", "can"}, "gnss_can": {"gps", "can"},
         "lidar_scale": {"lidar"}, "lidar_bias": {"lidar"}, "lidar_yaw": {"lidar"}, "can_scale": {"can"}, "can_offset": {"can"}, "can_freeze": {"can"}, "can_bus": {"can"}}
GPS_HELD = {"doppler_spoof", "meaconing"}
NET_HELD = {"PortScan", "Web-BruteForce", "Web-XSS"}
V2X_HELD = {"06_ConstSpeedOffset", "17_DataReplaySybil"}
SINGLE_SCEN = ("vehicle", "lidar_scan", "can_episode", "v2x_episode", "network_block")
PERSIST_SCEN = ("vehicle", "network_block")
V2X_PER_CLASS = 30
# ---- grid (v3 value first in every dimension)
A_OPTS = {"NO": ("noisy_or", None), "MX": ("wsplit", "equal"), "WM": ("wsplit", "motion")}
L_OPTS = ["L100", "L125"]
B_OPTS = [0.02, 0.015, 0.01]
P_OPTS = [(2, 5), (3, 5), (3, 10)]
G_OPTS = [15, 30, 60]
D_OPTS = [False, True]
K_OPTS = [1, 3]
NB, BSEED = 2000, 31
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def load(name):
    return pickle.load(open(CACHE / name, "rb"))


def weights_of(kind, entries):
    if kind is None:
        return None
    if kind == "equal":
        return {e: 1.0 for e in entries}
    return {e: (2.0 if e in ("gps", "lidar", "can", "cross") else 1.0) for e in entries}


# ================================================================================================================ LOGO calibration
def logo_cals(pools, density_samples=None):
    """pools: group -> clean tick values (already density-transformed if needed) -> group -> ECDF fitted on the other groups (+ key None = all groups)."""
    out = {}
    for g in list(pools) + [None]:
        v = np.concatenate([np.asarray(p, float) for h, p in pools.items() if h != g])
        out[g] = ECDFCalibrator().fit(v)
    return out


class Sources:
    """All calibrated source series (dicts of equal-length arrays), per domain."""

    def __init__(self):
        self.kveh = load("kveh.pkl")["series"]
        self.cveh = load("cveh.pkl")["series"]
        self.lid = load("lidar.pkl")
        self.can = load("can.pkl")["series"]
        v2 = load("v2x.pkl")
        self.v2x, self.v2x_msg = v2["series"], v2["clean_msg"]
        self.net = load("net.pkl")["series"]
        self.cal_meta = {}
        self._gps_cross()
        self._lidar()
        self._can()
        self._v2x()
        self._net()

    # ---- K / C vehicle blocks
    def _gps_cross(self):
        K, C = self.kveh, self.cveh
        pg = defaultdict(list)
        pc = defaultdict(list)
        for (d, ph, f), s in K.items():
            if f == "none":
                pg[d].append(s["gps_score"])
                pc[d].append(s["cross_score"])
        cg = logo_cals({d: np.concatenate(v) for d, v in pg.items()})
        cc = logo_cals({d: np.concatenate(v) for d, v in pc.items()})
        self.K = {}
        for key, s in K.items():
            d = key[0]
            self.K[key] = {"n": s["n"], "label": s["label"], "group": d,
                           "gps": {"X": cg[d].transform(s["gps_score"]), "own": s["gps_alarm"], "label": s["label"]},
                           "cross": {"X": cc[d].transform(s["cross_score"]), "own": s["cross_alarm"], "label": s["label"], "blame_A1": s["blame_A1"],
                                     "blame_V3": s["blame_V3"], "blame_A3": s["blame_A3"]}}
        pc2 = defaultdict(list)
        for (r, w, f, rep), s in C.items():
            if f == "none":
                pc2[r].append(s["cross_score"])
        cc2 = logo_cals({r: np.concatenate(v) for r, v in pc2.items()})
        self.C = {}
        for key, s in C.items():
            r = key[0]
            self.C[key] = {"n": s["n"], "label": s["label"], "group": r,
                           "cross": {"X": cc2[r].transform(s["cross_score"]), "own": s["cross_alarm"], "label": s["label"], "blame_A1": s["blame_A1"],
                                     "blame_V3": s["blame_V3"], "blame_A3": s["blame_A1"]}}
        self.cal_full = {"K": {"gps": cg[None], "cross": cc[None]}, "C": {"cross": cc2[None]}}
        self.cal_meta["gps_cross_groups"] = {"K": sorted(pg), "C": sorted(pc2)}

    # ---- LiDAR: per-scan calibrated scores (ECDF monotone: ECDF(tick max) = tick max of ECDF)
    def _lidar(self):
        self.scan = {}
        cal_all = {}
        for var in L_OPTS:
            pools = {}
            for d, rec in self.lid["drives"].items():
                x = rec[var]
                m = x["kind"] == "clean"
                k = np.floor(x["t"][m]).astype(int)
                v = np.zeros(k.max() + 1)
                np.maximum.at(v, k, x["score"][m])
                pres = np.zeros(k.max() + 1, bool)
                pres[k] = True
                pools[d] = v[pres]
            cal = logo_cals(pools)
            cal_all[var] = cal[None]
            for d, rec in self.lid["drives"].items():
                x = rec[var]
                self.scan.setdefault(d, {})[var] = {**x, "c": cal[d].transform(x["score"])}
        for d in self.scan:
            a, b = self.scan[d]["L100"], self.scan[d]["L125"]
            assert np.array_equal(a["i"], b["i"]) and np.array_equal(a["kind"], b["kind"]) and np.array_equal(a["attack"], b["attack"])
        self.cal_full["K"]["lidar"] = cal_all

    def lidar_ticks(self, d, off, n, overlay=None):
        """Ticks [0, n) of drive d's scans with t in [off + k, off + k + 1); overlay = boolean row mask of attacked rows replacing the clean rows of the same scan index."""
        out = {"X": np.zeros(n), "own": np.zeros(n, bool), "label": np.zeros(n, bool), "X_L125": np.zeros(n), "own_L125": np.zeros(n, bool), "present": np.zeros(n, bool)}
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
        for var, sx in (("L100", ""), ("L125", "_L125")):
            x = self.scan[d][var]
            np.maximum.at(out["X" + sx], kk, x["c"][r])
            out["own" + sx][kk[x["alarm"][r]]] = True
        att = a["kind"][r] != "clean"
        out["label"][kk[att]] = True
        out["present"][kk] = True
        return out

    # ---- CAN
    def _can(self):
        pools = {}
        for s in self.can:
            if s["kind"] == "clean":
                pools[s["group"]] = s["score"]
            else:
                on = np.flatnonzero(s["label"])
                pools[s["group"]] = s["score"][:on[0]] if len(on) else s["score"]
        cal = logo_cals(pools)
        self.cal_full["K"]["can"] = self.cal_full["C"]["can"] = cal[None]
        self.CAN = [{**s, "X": cal[s["group"]].transform(s["score"]), "own": s["dom_alarm"]} for s in self.can]

    # ---- V2X (density transform alpha 1, as v3)
    def _v2x(self):
        groups = sorted(self.v2x_msg)
        G = {}
        for g in groups + [None]:
            G[g] = DensityTransform(1.0).fit(np.concatenate([self.v2x_msg[h] for h in groups if h != g]))
        pools = defaultdict(list)
        for s in self.v2x:
            if s["kind"] == "clean":
                pools[s["group"]].append((s["score"], s["count"]))
        # the ECDF of the other blocks' clean q, with q computed by the density transform that excludes the series' own block
        cal = {}
        for g in groups + [None]:
            Gg = G[g]
            v = np.concatenate([Gg.transform(sc, k) for h in groups if h != g for sc, k in pools[h]])
            cal[g] = ECDFCalibrator().fit(v)
        self.v2x_density_full, self.cal_full["K"]["v2x"] = G[None], cal[None]
        self.cal_full["C"]["v2x"] = cal[None]
        self.V2X = [{**s, "X": cal[s["group"]].transform(G[s["group"]].transform(s["score"], s["count"])), "own": s["dom_alarm"]} for s in self.v2x]

    # ---- network (F1 headline, RC5 variant)
    def _net(self):
        cals = {}
        for var in ("F1", "RC5"):
            pools = defaultdict(list)
            for s in self.net:
                if s["kind"] == "clean":
                    pools[s["day"]].append(s[var]["score"])
            cals[var] = logo_cals({d: np.concatenate(v) for d, v in pools.items()})
        self.cal_full["K"]["network"] = self.cal_full["C"]["network"] = {v: cals[v][None] for v in cals}
        self.NET = []
        for s in self.net:
            d = s["day"]
            f1, rc = s["F1"], s["RC5"]
            self.NET.append({"name": s["name"], "group": s["name"], "day": d, "kind": s["kind"], "n": s["n"], "host_flows": s["host_flows"],
                             "X": cals["F1"][d].transform(f1["score"]), "own": f1["dom_alarm"], "label": f1["label"], "fam": f1["fam"],
                             "X_RC5": cals["RC5"][d].transform(rc["score"]), "own_RC5": rc["dom_alarm"], "label_RC5": rc["label"]})


# ================================================================================================================ composites
PART_KEYS = {"gps": ("X", "own", "label"), "cross": ("X", "own", "label", "blame_A1", "blame_V3", "blame_A3"), "lidar": ("X", "own", "label", "X_L125", "own_L125"),
             "can": ("X", "own", "label"), "v2x": ("X", "own", "label"), "network": ("X", "own", "label", "X_RC5", "own_RC5", "label_RC5")}


def zero(key, n):
    if key.startswith("blame"):
        return np.full(n, None, object)
    if key.startswith("own") or key.startswith("label"):
        return np.zeros(n, bool)
    return np.zeros(n)


class Builder:
    def __init__(self, S, fam, seed):
        self.S, self.fam = S, fam
        self.domains = K_DOMAINS if fam == "K" else C_DOMAINS
        self.rng = np.random.default_rng(seed)
        self.can_clean = [s for s in S.CAN if s["kind"] == "clean"]
        self.can_att = [s for s in S.CAN if s["kind"] == "attack"]
        self.v2x_clean = [s for s in S.V2X if s["kind"] == "clean"]
        self.v2x_att = [s for s in S.V2X if s["kind"] == "attack"]
        self.veh = S.K if fam == "K" else S.C
        self.veh_clean = sorted(k for k in self.veh if k[2] == "none")

    def new_parts(self, n):
        return {d: {k: zero(k, n) for k in PART_KEYS[d]} for d in self.domains}

    def place(self, P, d, pos, s, start, length, label=True):
        n = len(P[d]["X"])
        a = max(start, 0)
        b = min(start + length, len(s["X"]), start + (n - pos))
        if b <= a:
            return 0
        o = pos + (a - start)
        k = b - a
        for key in PART_KEYS[d]:
            if key.startswith("label") and not label:
                continue
            if key in s:
                P[d][key][o:o + k] = s[key][a:b]
        return k

    def clean_segment(self, pool, n):
        long = [s for s in pool if len(s["X"]) >= n]
        s = long[self.rng.integers(len(long))] if long else pool[int(np.argmax([len(x["X"]) for x in pool]))]
        start = int(self.rng.integers(0, len(s["X"]) - n + 1)) if len(s["X"]) > n else 0
        return s, start

    def fill_clean(self, P, n, skip=()):
        for d, pool in (("can", self.can_clean), ("v2x", self.v2x_clean)):
            if d in skip:
                continue
            s, st = self.clean_segment(pool, n)
            self.place(P, d, 0, s, st, n, label=False)

    def vehicle(self, key, n=None, j0=0):
        v = self.veh[key]
        n = v["n"] - j0 if n is None else n
        P = self.new_parts(n)
        for d in (("gps", "cross") if self.fam == "K" else ("cross",)):
            self.place(P, d, 0, v[d], j0, n)
        if self.fam == "K":
            lt = self.S.lidar_ticks(key[0], key[1] / PHASES + j0, n)
            for kk in PART_KEYS["lidar"]:
                P["lidar"][kk] = lt[kk]
        return P, n, np.asarray(v["label"][j0:j0 + n], bool).copy(), v["group"]

    def clean_vehicle_key(self):
        return self.veh_clean[int(self.rng.integers(len(self.veh_clean)))]

    def chain_vehicle(self, P, n):
        pos = 0
        while pos < n:
            key = self.clean_vehicle_key()
            v = self.veh[key]
            m = min(v["n"], n - pos)
            for d in (("gps", "cross") if self.fam == "K" else ("cross",)):
                self.place(P, d, pos, v[d], 0, m, label=False)
            if self.fam == "K":
                lt = self.S.lidar_ticks(key[0], key[1] / PHASES, m)
                for kk in ("X", "own", "X_L125", "own_L125"):
                    P["lidar"][kk][pos:pos + m] = lt[kk][:m]
            pos += m

    def chain_domain(self, P, d, pool, n):
        pos = 0
        while pos < n:
            s, st = self.clean_segment(pool, SEG)
            k = self.place(P, d, pos, s, st, min(SEG, n - pos), label=False)
            if not k:
                break
            pos += min(SEG, n - pos)


def comp(b, cid, scen, atype, attacked_key, P, n, label, group, onset_true=ONSET, label_rc=None):
    lab = np.asarray(label, bool)
    on = np.flatnonzero(lab)
    if scen in ("multi_can_gps", "multi_can_lidar"):
        ts = {"gps", "can"} if scen == "multi_can_gps" else {"can", "lidar"}
    elif scen == "vehicle":
        ts = TRUTH[atype]
    else:
        ts = {attacked_key}
    c = {"id": cid, "family": b.fam, "scenario": scen, "type": atype, "attacked_key": attacked_key, "n": int(n), "parts": P, "label": lab, "onset": int(on[0]) if len(on) else -1,
         "onset_true": int(onset_true), "group": group, "true_sensors": ts}
    if label_rc is not None:
        c["label_RC5"] = np.asarray(label_rc, bool)
        onr = np.flatnonzero(c["label_RC5"])
        c["onset_RC5"] = int(onr[0]) if len(onr) else -1
    return c


def runs_of(mask):
    m = np.asarray(mask, bool)
    on = np.flatnonzero(m & ~np.r_[False, m[:-1]])
    off = np.flatnonzero(m & ~np.r_[m[1:], False])
    return list(zip(on, off))


def v2x_episodes(b):
    eps = defaultdict(list)
    for s in b.v2x_att:
        fam = np.asarray(s["fam"], object)
        for f in sorted(set(x for x in fam if x)):
            for a, z in runs_of(fam == f):
                eps[f].append((s, int(a)))
    out = []
    for f in sorted(eps):
        e = eps[f]
        rng = np.random.default_rng([BSEED, 7, int(f[:2])])
        pick = sorted(rng.choice(len(e), size=min(V2X_PER_CLASS, len(e)), replace=False)) if len(e) > V2X_PER_CLASS else range(len(e))
        out += [(f, e[i][0], e[i][1]) for i in pick]
    return out


def vehicle_attacked(f, fam):
    return "gps+can" if f in COORD[fam] else ("gps" if f in GPS_FAMS else "cross")


def attack_composites(S, fam):
    b = Builder(S, fam, [BSEED, 2, ord(fam)])
    cid = [0]

    def nxt(p):
        cid[0] += 1
        return f"{fam}{cid[0]:05d}-{p}"
    for key in sorted(b.veh):
        f = key[2]
        if f == "none":
            continue
        P, n, lab, grp = b.vehicle(key)
        b.fill_clean(P, n)
        yield comp(b, nxt("veh"), "vehicle", f, vehicle_attacked(f, fam), P, n, lab, grp)
    if fam == "K":
        for d in sorted(S.scan):
            a = S.scan[d]["L100"]
            for kind in S.lid["kinds"]:
                ov = (a["kind"] == "att") & (a["attack"] == kind)
                if not ov.any():
                    continue
                P, n, _, grp = b.vehicle((d, 0, "none"))
                b.fill_clean(P, n)
                lt = S.lidar_ticks(d, 0.0, n, overlay=ov)
                for kk in PART_KEYS["lidar"]:
                    P["lidar"][kk] = lt[kk]
                yield comp(b, nxt("lidar"), "lidar_scan", kind, "lidar", P, n, lt["label"], d)
        for d in sorted(S.scan):
            a = S.scan[d]["L100"]
            for ep in sorted(set(a["ep"][a["kind"] == "pdep"])):
                ov = (a["kind"] == "pdep") & (a["ep"] == ep)
                s0 = int(a["i"][ov].min())
                t0 = float(S.lid["drives"][d]["t_oxts"][s0])
                j0 = max(0, int(np.floor(t0)) - ONSET)
                P, n, _, grp = b.vehicle((d, 0, "none"), j0=j0)
                b.fill_clean(P, n)
                lt = S.lidar_ticks(d, float(j0), n, overlay=ov)
                for kk in PART_KEYS["lidar"]:
                    P["lidar"][kk] = lt[kk]
                on = int(np.flatnonzero(lt["label"])[0]) if lt["label"].any() else -1
                yield comp(b, nxt("lidar_ep"), "lidar_episode", "ep_PointDrop", "lidar", P, n, lt["label"], d, onset_true=on)
    can_eps = [(s, int(a)) for s in b.can_att for a, z in runs_of(s["label"])]
    for s, o in can_eps:
        P, n, _, grp = b.vehicle(b.clean_vehicle_key())
        b.fill_clean(P, n, skip=("can",))
        b.place(P, "can", 0, s, o - ONSET, n)
        lab = P["can"]["label"] & (np.arange(n) >= min(ONSET, o))
        yield comp(b, nxt("can"), "can_episode", s["family"], "can", P, n, lab, s["name"], onset_true=min(ONSET, o))
    if fam == "K":
        for s, o in can_eps:
            gk = sorted(k for k in b.veh if k[2] in GPS_FAMS)
            key = gk[int(b.rng.integers(len(gk)))]
            P, n, vlab, grp = b.vehicle(key)
            b.fill_clean(P, n, skip=("can",))
            b.place(P, "can", 0, s, o - ONSET, n)
            lab = vlab | (P["can"]["label"] & (np.arange(n) >= min(ONSET, o)))
            yield comp(b, nxt("multi"), "multi_can_gps", f"{s['family']}+{key[2]}", "multi", P, n, lab, f"{key[0]}|{s['name']}")
            d = sorted(S.scan)[int(b.rng.integers(len(S.scan)))]
            a = S.scan[d]["L100"]
            ov = (a["kind"] == "att") & (a["attack"] == "PointDrop")
            P, n, _, grp = b.vehicle((d, 0, "none"))
            b.fill_clean(P, n, skip=("can",))
            lt = S.lidar_ticks(d, 0.0, n, overlay=ov)
            for kk in PART_KEYS["lidar"]:
                P["lidar"][kk] = lt[kk]
            b.place(P, "can", 0, s, o - ONSET, n)
            lab = lt["label"] | (P["can"]["label"] & (np.arange(n) >= min(ONSET, o)))
            yield comp(b, nxt("multi"), "multi_can_lidar", f"{s['family']}+PointDrop", "multi", P, n, lab, f"{d}|{s['name']}")
    for f, s, a in v2x_episodes(b):
        P, n, _, grp = b.vehicle(b.clean_vehicle_key())
        b.fill_clean(P, n, skip=("v2x",))
        b.place(P, "v2x", 0, s, a - ONSET, n)
        o = min(ONSET, a)
        lab = P["v2x"]["label"] & (np.arange(n) >= o)
        yield comp(b, nxt("v2x"), "v2x_episode", f, "v2x", P, n, lab, s["group"], onset_true=o)
    for s in [x for x in S.NET if x["kind"] == "attack"]:
        fam_t = np.asarray(s["fam"], object)
        lab = np.asarray(s["label"], bool)
        runs = []
        for f in sorted(set(x for x in fam_t[lab] if x)):
            runs += [(f, int(a), int(z)) for a, z in runs_of(lab & (fam_t == f))]
        runs.sort(key=lambda r: r[1])
        for i, (f, a, z) in enumerate(runs):
            flow_on = max(a - 60, 0)
            j0 = max(flow_on - ONSET, 0)
            nxt_start = runs[i + 1][1] - 60 if i + 1 < len(runs) else len(lab)
            end = min(z + 361, len(lab), nxt_start)
            n = end - j0
            if n < 120:
                continue
            P = b.new_parts(n)
            b.place(P, "network", 0, s, j0, n)
            b.chain_vehicle(P, n)
            for d in ("can", "v2x"):
                b.chain_domain(P, d, b.can_clean if d == "can" else b.v2x_clean, n)
            nl = np.zeros(n, bool)
            nl[a - j0:z - j0 + 1] = True
            lab_rc = np.zeros(n, bool)
            lab_rc[max(a - 60 - j0, 0):max(z - 60 - j0 + 1, 0)] = True
            lab_rc &= np.asarray(s["label_RC5"][j0:j0 + n], bool)
            yield comp(b, nxt("net"), "network_block", f, "network", P, n, nl & P["network"]["label"], s["name"], onset_true=flow_on - j0, label_rc=lab_rc)


def clean_timelines(S, fam):
    for i, s in enumerate([x for x in S.NET if x["kind"] == "clean"]):
        b = Builder(S, fam, [BSEED, 100 + i])
        n = s["n"]
        P = b.new_parts(n)
        b.place(P, "network", 0, s, 0, n, label=False)
        b.chain_vehicle(P, n)
        for d in ("can", "v2x"):
            b.chain_domain(P, d, b.can_clean if d == "can" else b.v2x_clean, n)
        yield {"id": f"{fam}-clean-{s['name']}", "family": fam, "scenario": "clean_timeline", "type": "none", "n": n, "parts": P, "label": np.zeros(n, bool), "onset": -1,
               "onset_true": -1, "group": s["name"]}


# ================================================================================================================ evaluation
def matrices(c, domains, lvar="L100", nvar="F1"):
    P = c["parts"]
    X, own = [], []
    for d in domains:
        p = P[d]
        sx = "_L125" if (d == "lidar" and lvar == "L125") else ("_RC5" if (d == "network" and nvar == "RC5") else "")
        X.append(p["X" + sx])
        own.append(p["own" + sx])
    return np.column_stack(X), np.column_stack(own).astype(bool)


def cross_arrays(c, blame_key):
    P = c["parts"]
    return P["cross"][blame_key], P["cross"]["own"]


def episodes_of(alarm, m, w, gap):
    return CR.TemporalCorrelator(m=m, w=w, gap=gap).episodes(alarm, None)


def summarise(eps, own, names, blame, label, onset, onset_true, dk_list, corr_variants=None):
    """Confirmed episodes -> detection, delay, event blame, worst response per (D, k) over events ending at or after the onset; clean: events and SAFE_STOP counts."""
    conf = []
    for ticks, s, _ in eps:
        if s is None:
            continue
        conf.append((ticks, s))
    out = {"events": len(conf), "alarm_ticks": int(sum(len(t) for t, _ in eps)), "detected": False}
    ss = {dk: 0 for dk in dk_list}
    worst = {dk: 0 for dk in dk_list}
    ev_info = []
    for ticks, s in conf:
        oc = own[ticks].sum(axis=0)
        u, cc = np.unique(np.asarray(blame, object)[ticks].astype(str), return_counts=True)
        bc = {str(a): int(b) for a, b in zip(u, cc)}
        blamed = CR.event_blame(bc, len(ticks), "majority_decided")
        dur = int(ticks[-1]) - s + 1
        lv = {}
        for dk, corr in corr_variants.items():
            cnt = corr.counted_domains(oc, names, blamed)
            lv[dk] = CR.LEVELS.index(CR.respond(bc, blamed, dur, len(cnt), corr.min_domains)[0])
            ss[dk] += lv[dk] == 3
        ev_info.append((ticks, s, blamed, lv))
    out["safe_stop"] = ss
    if onset >= 0:
        lab = np.asarray(label, bool)
        best = None
        for ticks, s, blamed, lv in ev_info:
            ct = ticks[ticks >= s]
            h = ct[lab[ct]]
            if len(h) and (best is None or h[0] < best[0]):
                best = (int(h[0]), blamed)
            if int(ticks[-1]) >= onset:
                for dk in dk_list:
                    worst[dk] = max(worst[dk], lv[dk])
        if best is not None:
            out.update(detected=True, delay=best[0] - onset, delay_available=best[0] + 1 - onset_true, blamed=best[1])
        out["worst"] = worst
    return out


def outcome(r, truth):
    if not r["detected"]:
        return None
    return "undecided" if r["blamed"] == "undecided" else ("correct" if r["blamed"] in truth else "wrong")


def category(c):
    t, a = c["type"], c["attacked_key"]
    if a == "gps":
        return "heldout" if t in GPS_HELD else "seen"
    if a == "can":
        return "heldout" if t.endswith("_masquerade") else "seen"
    if a == "network":
        return "heldout" if t in NET_HELD else "seen"
    if a == "v2x":
        return "heldout" if t in V2X_HELD else "seen"
    if a == "lidar":
        return "lidar_labelfree"
    return "choice_seen"


def loto_thresholds(scores_clean, budget):
    """Leave-one-timeline-out tie-safe thresholds + the all-timelines threshold."""
    out = []
    for i in range(len(scores_clean)):
        out.append(budget_threshold(np.concatenate([s for j, s in enumerate(scores_clean) if j != i]), budget))
    return out, budget_threshold(np.concatenate(scores_clean), budget)


class Fam:
    """Precomputed per family: composites, names, matrices per (L, N) variant."""

    def __init__(self, S, fam):
        self.fam = fam
        self.names = K_DOMAINS if fam == "K" else C_DOMAINS
        self.att = list(attack_composites(S, fam))
        self.clean = list(clean_timelines(S, fam))
        self.single = [i for i, c in enumerate(self.att) if c["scenario"] in SINGLE_SCEN and c["type"] not in COORD[fam]]
        self.types = sorted({(self.att[i]["scenario"], self.att[i]["type"]) for i in self.single})
        self.held = [t for t in self.types if category(self.att[next(i for i in self.single if (self.att[i]["scenario"], self.att[i]["type"]) == t)]) == "heldout"]
        log(fam, "attack composites", len(self.att), "clean timelines", len(self.clean), "hours", round(sum(c["n"] for c in self.clean) / 3600, 2),
            "single types", len(self.types), dict(Counter(c["scenario"] for c in self.att)))


def combine(method, wkind, names, X):
    sysm = SystemV31(names, method=method, weights=weights_of(wkind, names))
    return sysm.combine(X)


def grid_eval(F, lvars, nvar="F1"):
    """All candidates for one family -> {cand_key: metrics}."""
    names = F.names
    res = {}
    dk_list = [(D, k) for D in D_OPTS for k in K_OPTS]
    corr_v = {(D, k): Correlator31(dedup=D, k_corr=k) for D, k in dk_list}
    mats_a = {lv: [matrices(c, names, lv, nvar) for c in F.att] for lv in lvars}
    mats_c = {lv: [matrices(c, names, lv, nvar) for c in F.clean] for lv in lvars}
    bl_a = [cross_arrays(c, "blame_A1") for c in F.att]
    bl_c = [cross_arrays(c, "blame_A1") for c in F.clean]
    from fusion.system31 import tick_blame31
    for akey, (method, wk) in A_OPTS.items():
        for lv in lvars:
            sa = [combine(method, wk, names, X) for X, _ in mats_a[lv]]
            sc = [combine(method, wk, names, X) for X, _ in mats_c[lv]]
            tb_a = [tick_blame31(names, X, o, *bl_a[i]) for i, (X, o) in enumerate(mats_a[lv])]
            tb_c = [tick_blame31(names, X, o, *bl_c[i]) for i, (X, o) in enumerate(mats_c[lv])]
            for b in B_OPTS:
                thr_c, thr_all = loto_thresholds(sc, b)
                al_a = [s >= thr_all for s in sa]
                al_c = [s >= thr_c[i] for i, s in enumerate(sc)]
                for (m, w), gap in itertools.product(P_OPTS, G_OPTS):
                    ra = [summarise(episodes_of(al_a[i], m, w, gap), mats_a[lv][i][1], names, tb_a[i], c["label"], c["onset"], c["onset_true"], dk_list, corr_v)
                          for i, c in enumerate(F.att)]
                    rc = [summarise(episodes_of(al_c[i], m, w, gap), mats_c[lv][i][1], names, tb_c[i], c["label"], -1, -1, dk_list, corr_v)
                          for i, c in enumerate(F.clean)]
                    base = metrics(F, ra, rc, al_c)
                    for D, k in dk_list:
                        key = f"{akey}|{lv}|b{b * 100:g}|m{m}w{w}|g{gap}|d{int(D)}|k{k}"
                        res[key] = {**base, **dk_metrics(F, ra, rc, (D, k))}
            log(F.fam, "done", akey, lv, len(res))
    return res


def type_mean(F, recs, fn, types=None):
    types = F.types if types is None else types
    per = defaultdict(list)
    for i in F.single:
        c = F.att[i]
        t = (c["scenario"], c["type"])
        if t in types:
            v = fn(c, recs[i])
            if v is not None:
                per[t].append(v)
    vals = [np.mean(v) for v in per.values() if v]
    return float(np.mean(vals)) if vals else None


def metrics(F, ra, rc, al_c):
    hours = sum(c["n"] for c in F.clean) / 3600.0
    held = F.held
    out = {"fa_tick": float(sum(int(a.sum()) for a in al_c) / sum(c["n"] for c in F.clean)), "events_per_hour": float(sum(r["events"] for r in rc) / hours),
           "det_single": type_mean(F, ra, lambda c, r: float(r["detected"])), "det_heldout": type_mean(F, ra, lambda c, r: float(r["detected"]), held),
           "blame_correct": type_mean(F, ra, lambda c, r: None if not r["detected"] else float(outcome(r, c["true_sensors"]) == "correct")),
           "blame_wrong": type_mean(F, ra, lambda c, r: None if not r["detected"] else float(outcome(r, c["true_sensors"]) == "wrong"))}
    dl = [ra[i]["delay_available"] for i in F.single if F.att[i]["scenario"] in PERSIST_SCEN and ra[i]["detected"]]
    out["ttv_persistent_median"] = float(np.median(dl)) if dl else None
    return out


def dk_metrics(F, ra, rc, dk):
    hours = sum(c["n"] for c in F.clean) / 3600.0
    return {"safe_stop_per_hour": float(sum(r["safe_stop"][dk] for r in rc) / hours)}


# ================================================================================================================ selection
V3_KEY = {"A": "NO", "L": "L100", "b": "b2", "P": "m2w5", "G": "g15", "D": "d0", "K": "k1"}
ORDER = {"A": ["NO", "MX", "WM"], "L": ["L100", "L125"], "b": ["b2", "b1.5", "b1"], "P": ["m2w5", "m3w5", "m3w10"], "G": ["g15", "g30", "g60"], "D": ["d0", "d1"], "K": ["k1", "k3"]}
BOUNDS = {"fa_tick": 0.025, "events_per_hour": 8.0, "safe_stop_per_hour": 0.8}


def parts_of(key):
    return dict(zip(["A", "L", "b", "P", "G", "D", "K"], key.split("|")))


def n_changed(key):
    p = parts_of(key)
    return sum(p[k] != V3_KEY[k] for k in p)


def steps(key):
    p = parts_of(key)
    return sum(ORDER[k].index(p[k]) for k in p)


def compute_cost(key):
    p = parts_of(key)
    return (p["A"] != "NO") + (p["L"] != "L100")


def violation(rk, rc_):
    return max(max(r[m] / BOUNDS[m] for m in BOUNDS) for r in (rk, rc_))


def select(gk, gc):
    keys = sorted(gk)
    feas = [k for k in keys if all(gk[k][m] <= BOUNDS[m] and gc[k][m] <= BOUNDS[m] for m in BOUNDS)]
    if feas:
        best = max(gk[k]["det_single"] for k in feas)
        tie = [k for k in feas if gk[k]["det_single"] >= best - 0.005]
        chosen = sorted(tie, key=lambda k: (n_changed(k), steps(k), compute_cost(k), k))[0]
        return {"feasible": True, "n_feasible": len(feas), "best_det": best, "tie_set": tie[:50], "n_tie": len(tie), "chosen": chosen}
    v = {k: violation(gk[k], gc[k]) for k in keys}
    vb = min(v.values())
    tie = [k for k in keys if v[k] <= vb + 1e-12]
    chosen = sorted(tie, key=lambda k: (-gk[k]["det_single"], n_changed(k), steps(k), compute_cost(k), k))[0]
    return {"feasible": False, "n_feasible": 0, "min_violation": vb, "chosen": chosen}


# ================================================================================================================ full re-run of one configuration (frozen code path)
def config_system(key, names, budget_override=None, corroborators=None, blame="A1"):
    p = parts_of(key)
    method, wk = A_OPTS[p["A"]]
    m, w = (int(p["P"][1]), int(p["P"][3:]))
    corr = Correlator31(m=m, w=w, gap=int(p["G"][1:]), dedup=p["D"] == "d1", k_corr=int(p["K"][1:]), corroborators=corroborators)
    return SystemV31(names, method=method, weights=weights_of(wk, names), budget=float(p["b"][1:]) / 100 if budget_override is None else budget_override,
                     correlator=corr, density_alpha={"v2x": 1.0}, blame=blame)


def full_run(F, key, blame_key="blame_A1", blame="A1", nvar="F1", corroborators=None, keep_scores=False):
    """Run every composite of F through SystemV31.decide (explanations) with the LOTO / all-timeline thresholds."""
    names = F.names
    p = parts_of(key)
    sysm = config_system(key, names, corroborators=corroborators, blame=blame)
    mc = [matrices(c, names, p["L"], nvar) for c in F.clean]
    sc = [sysm.combine(X) for X, _ in mc]
    thr_c, thr_all = loto_thresholds(sc, sysm.budget)
    sysm.threshold = thr_all
    recs_c, recs_a, store = [], [], {"clean": [], "attack": []}
    for i, c in enumerate(F.clean):
        X, own = mc[i]
        cbl, cal_ = cross_arrays(c, blame_key)
        o = sysm.decide(X, own, cbl, cal_, threshold=thr_c[i])
        ev = o["events"]
        recs_c.append({"id": c["id"], "group": c["group"], "n": c["n"], "hours": c["n"] / 3600.0, "alarm_ticks": int(o["alarm"].sum()), "events": len(ev),
                       "levels": {lv: sum(e.response == lv for e in ev) for lv in CR.LEVELS[1:]},
                       "explained": int(sum("first alarm: system alarm" in e.explanation for e in ev)),
                       "event_domains": [e.domains for e in ev], "event_blamed": [e.blamed for e in ev], "event_response": [e.response for e in ev],
                       "own_share": {d: float(own[:, j].mean()) for j, d in enumerate(names)}})
        if keep_scores:
            store["clean"].append((c["id"], c["group"], o["score"], o["alarm"], np.zeros(c["n"], bool), thr_c[i]))
    for c in F.att:
        lab = c.get("label_RC5", c["label"]) if nvar == "RC5" else c["label"]
        onset = c.get("onset_RC5", c["onset"]) if nvar == "RC5" else c["onset"]
        X, own = matrices(c, names, p["L"], nvar)
        cbl, cal_ = cross_arrays(c, blame_key)
        o = sysm.decide(X, own, cbl, cal_)
        ev = o["events"]
        r = {"id": c["id"], "scenario": c["scenario"], "type": c["type"], "group": c["group"], "attacked_key": c["attacked_key"], "n": c["n"], "events": len(ev),
             "detected": False, "explained": int(sum("first alarm: system alarm" in e.explanation for e in ev)), "alarm_ticks": int(o["alarm"].sum()),
             "tick_detected": bool((o["alarm"] & lab).any())}
        best = None
        for e in ev:
            ct = np.arange(e.start, e.end + 1)
            ct = ct[o["alarm"][ct] & lab[ct]]
            if len(ct) and (best is None or ct[0] < best[0]):
                best = (int(ct[0]), e)
        if best is not None:
            r.update(detected=True, delay=best[0] - onset, delay_available=best[0] + 1 - c["onset_true"], blamed=best[1].blamed,
                     blame="undecided" if best[1].blamed == "undecided" else ("correct" if best[1].blamed in c["true_sensors"] else "wrong"),
                     event_domains=best[1].domains)
        over = [e for e in ev if e.end >= onset] if onset >= 0 else []
        r["response_max"] = max((e.response for e in over), key=lambda x: CR.LEVELS.index(x)) if over else None
        recs_a.append(r)
        if keep_scores:
            store["attack"].append((c["id"], c["group"], o["score"], o["alarm"], lab, thr_all))
    return recs_a, recs_c, store, {"threshold_all": float(thr_all), "thresholds_loto": [float(x) for x in thr_c]}


def r0_run(F):
    """R0: the v3 recipe (noisy_or, L100, 2 %, m2w5, gap 15, no de-dup, k 1) with the v3 tick_blame and the v3 cross blame."""
    return full_run(F, "NO|L100|b2|m2w5|g15|d0|k1", blame_key="blame_V3", blame="v3")


def boot_types(F, recs, fn, types, seed):
    rng = np.random.default_rng(seed)
    per = {}
    for i in F.single:
        c, r = F.att[i], recs[i]
        t = (c["scenario"], c["type"])
        if t not in types:
            continue
        v = fn(c, r)
        if v is None:
            continue
        per.setdefault(t, ([], []))
        per[t][0].append(float(v))
        per[t][1].append(c["group"])
    per = {t: (np.array(a), np.array(g)) for t, (a, g) in per.items()}
    if not per:
        return None, None
    est = float(np.mean([v.mean() for v, _ in per.values()]))
    bs = []
    for _ in range(NB):
        m = []
        for v, g in per.values():
            ug = np.unique(g)
            if len(ug) >= 3:
                pick = rng.choice(ug, len(ug))
                m.append(np.mean(np.concatenate([v[g == u] for u in pick])))
            else:
                m.append(v[rng.integers(len(v), size=len(v))].mean())
        bs.append(np.mean(m))
    return est, [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]


def ratio_ci(num, den, seed):
    rng = np.random.default_rng(seed)
    num, den = np.asarray(num, float), np.asarray(den, float)
    est = float(num.sum() / den.sum())
    bs = []
    for _ in range(NB):
        i = rng.integers(len(num), size=len(num))
        bs.append(num[i].sum() / den[i].sum())
    return est, [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]


def report_run(F, ra, rc):
    held = F.held
    hours = np.array([r["hours"] for r in rc])
    out = {"clean_timelines": len(rc), "clean_hours": float(hours.sum())}
    out["fa_tick"], out["fa_tick_ci"] = ratio_ci([r["alarm_ticks"] for r in rc], [r["n"] for r in rc], BSEED)
    out["events_per_hour"], out["events_per_hour_ci"] = ratio_ci([r["events"] for r in rc], hours, BSEED)
    for lv in CR.LEVELS[1:]:
        out[f"{lv}_per_hour"], out[f"{lv}_per_hour_ci"] = ratio_ci([r["levels"][lv] for r in rc], hours, BSEED)
    out["clean_events_explained"] = [int(sum(r["explained"] for r in rc)), int(sum(r["events"] for r in rc))]
    out["clean_event_domains"] = dict(Counter(d for r in rc for ds in r["event_domains"] for d in ds))
    out["clean_event_blamed"] = dict(Counter(b for r in rc for b in r["event_blamed"]))
    out["own_alarm_share"] = {d: float(sum(r["own_share"][d] * r["n"] for r in rc) / sum(r["n"] for r in rc)) for d in F.names}
    out["types"], out["held_out_types"] = len(F.types), len(held)
    out["det_single"], out["det_single_ci"] = boot_types(F, ra, lambda c, r: r["detected"], F.types, BSEED)
    out["det_heldout"], out["det_heldout_ci"] = boot_types(F, ra, lambda c, r: r["detected"], held, BSEED) if held else (None, None)
    out["blame_correct"], out["blame_correct_ci"] = boot_types(F, ra, lambda c, r: None if not r["detected"] else r["blame"] == "correct", F.types, BSEED)
    out["blame_wrong"], out["blame_wrong_ci"] = boot_types(F, ra, lambda c, r: None if not r["detected"] else r["blame"] == "wrong", F.types, BSEED)
    out["attack_events_explained"] = [int(sum(r["explained"] for r in ra)), int(sum(r["events"] for r in ra))]
    dl = [ra[i]["delay_available"] for i in F.single if F.att[i]["scenario"] in PERSIST_SCEN and ra[i]["detected"]]
    out["ttv_persistent_median"] = float(np.median(dl)) if dl else None
    by = defaultdict(list)
    for i in F.single:
        by[F.att[i]["attacked_key"]].append(i)
    out["by_attacked_domain"] = {}
    for dk, idx in sorted(by.items()):
        ts = sorted({(F.att[i]["scenario"], F.att[i]["type"]) for i in idx})
        dd = [ra[i]["delay_available"] for i in idx if ra[i]["detected"]]
        out["by_attacked_domain"][dk] = {"types": len(ts), "event_detection": boot_types(F, ra, lambda c, r: r["detected"], ts, BSEED)[0],
                                         "delay_available_median": float(np.median(dd)) if dd else None}
    tt = {}
    for i, c in enumerate(F.att):
        k = f"{c['scenario']}|{c['type']}"
        tt.setdefault(k, []).append(ra[i])
    out["by_type"] = {k: {"n": len(v), "event_detection": float(np.mean([r["detected"] for r in v])), "tick_detection": float(np.mean([r["tick_detected"] for r in v])),
                          "blame": dict(Counter(r.get("blame") for r in v if r["detected"])), "response_max": dict(Counter(r.get("response_max") for r in v if r["detected"])),
                          "delay_available_median": (float(np.median([r["delay_available"] for r in v if r["detected"]])) if any(r["detected"] for r in v) else None)}
                      for k, v in sorted(tt.items())}
    return out


def save_scores(store, fam, tag):
    SCORES.mkdir(parents=True, exist_ok=True)
    for part, rows in store.items():
        if not rows:
            continue
        np.savez_compressed(SCORES / f"{fam}_{part}_val_{tag}.npz", ids=np.array([r[0] for r in rows]), groups=np.array([str(r[1]) for r in rows]),
                            lens=np.array([len(r[2]) for r in rows]), score=np.concatenate([r[2] for r in rows]).astype(np.float32),
                            alarm=np.concatenate([r[3] for r in rows]), label=np.concatenate([r[4] for r in rows]), threshold=np.array([r[5] for r in rows]))


def accept(rk, rc_, r0k):
    a = {}
    a["fa_tick"] = bool(rk["fa_tick"] <= 0.025 and rc_["fa_tick"] <= 0.025)
    a["events_per_hour"] = bool(rk["events_per_hour"] <= 8 and rc_["events_per_hour"] <= 8)
    a["safe_stop_per_hour"] = bool(rk["SAFE_STOP_per_hour"] <= 0.8 and rc_["SAFE_STOP_per_hour"] <= 0.8)
    a["det_single_70"] = bool(rk["det_single"] is not None and rk["det_single"] >= 0.70)
    a["det_heldout_60"] = bool(rk["det_heldout"] is not None and rk["det_heldout"] >= 0.60)
    a["blame_B3"] = bool(rk["blame_correct"] >= 0.75 and rk["blame_wrong"] <= 0.10)
    a["explained_100"] = bool(all(x[0] == x[1] for x in (rk["clean_events_explained"], rk["attack_events_explained"], rc_["clean_events_explained"], rc_["attack_events_explained"])))
    a["ttv"] = bool(rk["ttv_persistent_median"] is not None and r0k["ttv_persistent_median"] is not None and rk["ttv_persistent_median"] <= r0k["ttv_persistent_median"] + 5)
    a["verdict"] = "MET" if all(a.values()) else "NOT MET"
    return a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="r1")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    S = Sources()
    log("sources calibrated")
    fams = {f: Fam(S, f) for f in ("K", "C")}
    grid_f = OUT / f"{a.tag}_grid.json"
    if grid_f.exists():
        grid = json.loads(grid_f.read_text())
    else:
        grid = {"K": grid_eval(fams["K"], L_OPTS), "C": grid_eval(fams["C"], ["L100"])}
        grid["C"] = {k: grid["C"][k.replace("|L125|", "|L100|")] for k in grid["K"]}       # C has no LiDAR: L125 rows equal L100 rows
        tmp = grid_f.with_suffix(".tmp")
        tmp.write_text(json.dumps(grid))
        tmp.replace(grid_f)
    log("grid", len(grid["K"]))
    sel = select(grid["K"], grid["C"])
    key = sel["chosen"]
    log("chosen", key, sel.get("feasible"), grid["K"][key], grid["C"][key])
    res = {"tag": a.tag, "selection": sel, "chosen": key, "grid_K_chosen": grid["K"][key], "grid_C_chosen": grid["C"][key], "runs": {}}
    refs = {"chosen": (key, "blame_A1", "A1", "F1", None), "R0": ("NO|L100|b2|m2w5|g15|d0|k1", "blame_V3", "v3", "F1", None),
            "R0b": ("NO|L100|b2|m2w5|g15|d0|k1", "blame_A1", "A1", "F1", None),
            "variant_motion_critical_safe_stop": (key, "blame_A1", "A1", "F1", MC_OR_CROSS), "variant_network_RC5": (key, "blame_A1", "A1", "RC5", None),
            "variant_blame_v3": (key, "blame_V3", "v3", "F1", None), "variant_blame_A3": (key, "blame_A3", "A1", "F1", None)}
    for name, (k_, bk, bl, nv, corr) in refs.items():
        res["runs"][name] = {"key": k_, "blame": f"{bl}/{bk}", "network": nv, "corroborators": corr}
        for f, F in fams.items():
            ra, rc, store, thr = full_run(F, k_, blame_key=bk, blame=bl, nvar=nv, corroborators=corr, keep_scores=name in ("chosen", "R0"))
            res["runs"][name][f] = {**report_run(F, ra, rc), **thr}
            if name in ("chosen", "R0"):
                save_scores(store, f, f"{a.tag}_{name}")
            if name == "chosen":
                g = grid[f][key]
                rr = res["runs"][name][f]
                res["runs"][name][f]["grid_equals_full_run"] = bool(abs(g["fa_tick"] - rr["fa_tick"]) < 1e-12 and abs(g["events_per_hour"] - rr["events_per_hour"]) < 1e-9
                                                                    and abs(g["safe_stop_per_hour"] - rr["SAFE_STOP_per_hour"]) < 1e-9
                                                                    and (g["det_single"] is None or abs(g["det_single"] - rr["det_single"]) < 1e-12))
                pickle.dump({"att": ra, "clean": rc}, open(CACHE / f"{a.tag}_chosen_records_{f}.pkl", "wb"), protocol=4)
        log(name, {f: {m: res["runs"][name][f].get(m) for m in ("fa_tick", "events_per_hour", "SAFE_STOP_per_hour", "det_single", "det_heldout", "blame_correct", "blame_wrong",
                                                                   "ttv_persistent_median")} for f in fams})
    res["acceptance"] = accept(res["runs"]["chosen"]["K"], res["runs"]["chosen"]["C"], res["runs"]["R0"]["K"])
    res["composites"] = {f: {"attack": len(F.att), "clean_timelines": len(F.clean), "clean_hours": sum(c["n"] for c in F.clean) / 3600.0, "single_types": len(F.types),
                             "by_scenario": dict(Counter(c["scenario"] for c in F.att))} for f, F in fams.items()}
    res["calibration"] = S.cal_meta
    (OUT / f"{a.tag}_eval.json").write_text(json.dumps(res, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else (list(o) if isinstance(o, (set, tuple)) else str(o))))
    log("acceptance", res["acceptance"])


if __name__ == "__main__":
    main()
