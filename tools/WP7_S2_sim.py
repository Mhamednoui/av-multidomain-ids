"""WP7 S2 simulation: composite drives from the STREAMED domain logs (tools/WP7_S2_{veh,lidar,can,net,v2x}.py) fed second by second through the FROZEN system v2
(fusion.system.load_system(2), system/fusion_runner.py). Construction and acceptance rule: notes/WP7_system.md "S2 start" (seed [42, 77, 2, ord(family)]).
Stages: python -u -W ignore tools/WP7_S2_sim.py attacks | clean | all    Outputs: ../data_extra/cache_v3/WP7/S2_sim_attacks.pkl, S2_sim_clean.pkl (per-composite records, no arrays of the system).
Enumeration (no random subset): see build_attack_specs(); fill-in segments (CAN, V2X, vehicle block of domain attacks) are drawn with the family rng in a fixed order.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP7_S2_lib as L

import numpy as np
import pandas as pd

from fusion import correlator as CR
from fusion.system import load_system
from system.fusion_runner import LEVEL, replay
import WP6_S4_lib as S4L
import WP6_S5_lib as S5L

ONSET = L.ONSET
T0 = time.time()
MC_OR_CROSS = ("gps", "lidar", "can", "cross")          # design variant: who may corroborate a SAFE_STOP
CAN_HEAD = 3


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


# ------------------------------------------------------------------------------------------------------------------------------ sources
class Sources:
    def __init__(self):
        self.veh_K = L.load_pickle("S2_veh_K.pkl")
        self.veh_C = L.load_pickle("S2_veh_C.pkl")
        can = []
        for f in ("S2_can_attack.pkl", "S2_can_ambient.pkl"):
            can += L.load_pickle(f)["series"]
        self.can = sorted(can, key=lambda s: s["name"])
        self.v2x = sorted([s for f in sorted(L.CACHE.glob("S2_v2x_p*.pkl")) for s in L.load_pickle(f.name)["series"]], key=lambda s: s["name"])
        self.net = []
        for f in sorted(L.CACHE.glob("S2_net_p*.pkl")):
            self.net += L.load_pickle(f.name)["series"]
        self.net = sorted(self.net, key=lambda s: s["name"])
        self.scan = {}
        self.lidar = self._load_lidar()
        self.widths = {"gps": 16, "lidar": 4, "can": 3, "v2x": 12, "network": len(self.net[0]["layer_names"]), "cross_K": 7, "cross_C": 6}
        log("sources: K vehicle", len(self.veh_K["series"]), "C", len(self.veh_C["series"]), "can", len(self.can), "v2x", len(self.v2x), "net", len(self.net),
            "lidar clean drives", len(self.lidar["clean"]), "scan jobs", len(self.lidar["scan"]), "ep jobs", len(self.lidar["ep"]))

    def _load_lidar(self):
        out = {"clean": {}, "scan": {}, "ep": {}}
        for f in sorted(L.LIDAR_DIR.glob("*.pkl")):
            r = L.pickle.load(open(f, "rb"))
            if f.name.startswith("clean_"):
                out["clean"][r["drive"]] = r
            elif f.name.startswith("scan_"):
                out["scan"][(r["drive"], r["kind"])] = r
            elif f.name.startswith("ep_"):
                out["ep"][(r["drive"], "world" if r["world"] else "sensor")] = r
        return out


def scan_table(rows, n_scans=None):
    n = (max(r["idx"] for r in rows) + 1) if n_scans is None else n_scans
    t = np.full(n, np.nan)
    tab = {"t": t, "score": np.zeros(n, np.float32), "alarm": np.zeros(n, bool), "layers": np.zeros((n, 4), np.float32), "layer_alarm": np.zeros((n, 4), bool),
           "attacked": np.zeros(n, bool)}
    for r in rows:
        i = r["idx"]
        tab["t"][i], tab["score"][i], tab["alarm"][i] = r["t"], r["score"], r["alarm"]
        tab["layers"][i], tab["layer_alarm"][i], tab["attacked"][i] = r["layers"], r["layer_alarm"], r["attacked"]
    return tab


def lidar_part(tab, off, n):
    """Scan table -> 1 s ticks aligned to a vehicle run that starts at drive time `off` (tick k = scans with t in [off + k, off + k + 1))."""
    k = np.floor(tab["t"] - off).astype(int)
    ok = (k >= 0) & (k < n) & np.isfinite(tab["t"])
    kk = k[ok]
    out = {"score": np.zeros(n, np.float32), "layers": np.zeros((n, 4), np.float32), "dom_alarm": np.zeros(n, bool), "layer_alarm": np.zeros((n, 4), bool),
           "count": np.zeros(n, np.float32), "label": np.zeros(n, bool), "present": np.zeros(n, bool)}
    np.maximum.at(out["score"], kk, tab["score"][ok])
    for j in range(4):
        np.maximum.at(out["layers"][:, j], kk, tab["layers"][ok, j])
        out["layer_alarm"][kk[tab["layer_alarm"][ok, j]], j] = True
    out["dom_alarm"][kk[tab["alarm"][ok]]] = True
    np.add.at(out["count"], kk, 1.0)
    out["label"][kk[tab["attacked"][ok]]] = True
    out["present"][np.unique(kk)] = True
    return out


# ------------------------------------------------------------------------------------------------------------------------------ builder
class Builder:
    def __init__(self, S, fam, seed_tag=0):
        self.S, self.fam = S, fam
        self.domains = L.K_DOMAINS if fam == "K" else L.C_DOMAINS
        self.rng = np.random.default_rng([L.SEED, 77, 2 + seed_tag, ord(fam)])
        self.can_clean = [s for s in S.can if s["kind"] == "clean"]
        self.can_att = [s for s in S.can if s["kind"] == "attack"]
        self.v2x_clean = [s for s in S.v2x if s["kind"] == "clean"]
        self.v2x_att = [s for s in S.v2x if s["kind"] == "attack"]
        self.net_clean = [s for s in S.net if s["kind"] == "clean"]
        self.net_att = [s for s in S.net if s["kind"] == "attack"]
        sk = S.veh_K["series"]
        self.k_clean = sorted(k for k in sk if k[2] == "none")
        self.c_clean = sorted(k for k in S.veh_C["series"] if k[2] == "none")

    # ---- containers
    def new_parts(self, n):
        W = self.S.widths
        P = {}
        for d in self.domains:
            w = W["cross_" + self.fam] if d == "cross" else W[d]
            P[d] = {"score": np.zeros(n, np.float32), "count": np.zeros(n, np.float32), "layers": np.zeros((n, w), np.float32), "dom_alarm": np.zeros(n, bool),
                    "layer_alarm": np.zeros((n, w), bool), "blame": np.full(n, None, object), "present": np.zeros(n, bool), "avail": np.arange(n) + 1.0, "label": np.zeros(n, bool)}
        return P

    def place(self, P, d, pos, s, start, length, label=True):
        """Copy source ticks [start, start+length) of series s into composite ticks [pos, ...)."""
        n = len(P[d]["score"])
        a = max(start, 0)
        b = min(start + length, len(s["score"]), start + (n - pos))
        if b <= a:
            return 0
        o = pos + (a - start)
        k = b - a
        p = P[d]
        p["score"][o:o + k] = s["score"][a:b]
        p["count"][o:o + k] = s["count"][a:b] if "count" in s else 1.0
        p["layers"][o:o + k] = s["layers"][a:b]
        p["dom_alarm"][o:o + k] = s["dom_alarm"][a:b]
        p["layer_alarm"][o:o + k] = s["layer_alarm"][a:b]
        if s.get("blame") is not None:
            p["blame"][o:o + k] = s["blame"][a:b]
        p["present"][o:o + k] = s["present"][a:b] if "present" in s else True
        p["avail"][o:o + k] = np.asarray(s["avail"], float)[a:b] - start + pos
        if label:
            p["label"][o:o + k] = np.asarray(s["label"], bool)[a:b]
        return k

    def place_lidar(self, P, lp):
        n = len(P["lidar"]["score"])
        p = P["lidar"]
        for key in ("score", "count", "layers", "dom_alarm", "layer_alarm", "present", "label"):
            p[key][:] = lp[key][:n]

    # ---- clean fill-in
    def clean_segment(self, pool, n, minlen=None):
        long = [s for s in pool if len(s["score"]) >= n]
        s = long[self.rng.integers(len(long))] if long else pool[int(np.argmax([len(x["score"]) for x in pool]))]
        start = int(self.rng.integers(0, len(s["score"]) - n + 1)) if len(s["score"]) > n else 0
        return s, start

    def fill_clean(self, P, n, skip=()):
        for d, pool in (("can", self.can_clean), ("v2x", self.v2x_clean)):
            if d in skip or d not in self.domains:
                continue
            s, st = self.clean_segment(pool, n)
            self.place(P, d, 0, s, st, n, label=False)

    # ---- vehicle block
    def vehicle(self, key, n=None, j0=0):
        """K: (drive, phase, family) of veh_K; C: (route, window, family, rep) of veh_C. -> parts with the vehicle domains, n, label of the vehicle attack, group."""
        S = self.S
        if self.fam == "K":
            v = S.veh_K["series"][key]
            d, ph, f = key
            n0 = v["n"]
            n = n0 - j0 if n is None else n
            P = self.new_parts(n)
            self.place(P, "gps", 0, v["gps"], j0, n)
            self.place(P, "cross", 0, v["cross"], j0, n)
            tab = scan_table(S.lidar["clean"][d]["rows"])
            self.place_lidar(P, lidar_part(tab, ph / 10.0 + j0, n))
            lab = P["cross"]["label"].copy()
            if f in ("drift", "accel_drift", "doppler_spoof", "meaconing", "gps_can"):
                lab |= P["gps"]["label"]
            return P, n, lab, d
        s = S.veh_C["series"][key]
        n = len(s["score"]) if n is None else n
        P = self.new_parts(n)
        self.place(P, "cross", 0, s, j0, n)
        return P, n, P["cross"]["label"].copy(), key[0]

    def clean_vehicle_key(self):
        keys = self.k_clean if self.fam == "K" else self.c_clean
        return keys[int(self.rng.integers(len(keys)))]

    # ---- helpers for the results
    def comp(self, cid, scenario, atype, attacked, P, n, label, group, extra=None):
        lab = np.asarray(label, bool).copy()
        lab[:0] = False
        on = np.flatnonzero(lab)
        return {"id": cid, "family": self.fam, "scenario": scenario, "type": atype, "attacked": list(attacked), "n": int(n), "parts": P, "label": lab,
                "onset": int(on[0]) if len(on) else -1, "onset_true": ONSET, "group": group, **(extra or {})}


# ------------------------------------------------------------------------------------------------------------------------------ run + evaluate
def run_composite(sysm, c, track=True):
    P = c["parts"]
    fr = replay(sysm, {d: P[d] for d in sysm.domains}, {d: P[d]["avail"] for d in sysm.domains}, c["n"], track_events=track)
    return fr


def true_sensor(c):
    f, d = c["type"], c["attacked_domain_key"]
    return S5L.true_sensor(f, d)


def evaluate(c, fr, sysm):
    fin = fr.final()
    alarm, ev = fin["alarm"], fin["events"]
    n = c["n"]
    lab = c["label"]
    conf = np.zeros(n, bool)
    for e in ev:
        conf[np.flatnonzero(alarm[e.start:e.end + 1]) + e.start] = True
    r = {"id": c["id"], "family": c["family"], "scenario": c["scenario"], "type": c["type"], "attacked": c["attacked"], "n": n, "onset": c["onset"], "group": c["group"],
         "alarm_ticks": int(alarm.sum()), "events": len(ev), "tick_detected": bool((alarm & lab).any()), "detected": False,
         "alarm_in_label": int((alarm & lab).sum()), "label_ticks_n": int(lab.sum()), "alarm_outside_label": int((alarm & ~lab).sum())}
    if lab.any():
        hit = np.flatnonzero(conf & lab)
        r["tick_delay"] = float(np.flatnonzero(alarm & lab)[0] - c["onset"]) if (alarm & lab).any() else None
        if len(hit):
            t0 = int(hit[0])
            e0 = next(e for e in ev if e.start <= t0 <= e.end)
            r["detected"] = True
            r["delay"] = float(t0 - c["onset"])
            seen = fr.visible_time(e0.start, e0.end, "WARN")
            r["t_visible"] = float(max(seen if seen else 0, fr.first_known[t0]))
            r["delay_available"] = float(r["t_visible"] - c["onset_true"])
            r["blamed"] = e0.blamed
            ts = c["true_sensors"]
            r["blame"] = "undecided" if e0.blamed == "undecided" else ("correct" if e0.blamed in ts else "wrong")
            r["event_domains"] = e0.domains
        over = [e for e in ev if e.end >= c["onset"]]
        if over:
            worst = max(over, key=lambda e: LEVEL[e.response])
            r["response_max"] = worst.response
            r["degraded"] = list(worst.degraded)
            r["actions"] = list(worst.actions)
            for lv in ("DEGRADE", "SAFE_STOP"):
                r[f"t_{lv}"] = fr.visible_time(worst.start, worst.end, lv) if LEVEL[worst.response] >= LEVEL[lv] else None
            # design variant (labelled): the corroborating second domain must be motion-critical or cross-domain
            vr = []
            for e in over:
                nd = len([d for d in e.domains if d in MC_OR_CROSS])
                vr.append(CR.respond(e.blame_counts, e.blamed, e.end - e.start + 1, nd, 2)[0])
            r["response_max_variant"] = max(vr, key=lambda x: LEVEL[x])
        r["event_levels"] = [e.response for e in over]
    r["explained"] = int(sum("first alarm: system alarm" in e.explanation for e in ev))
    r["step_ms_median"] = float(np.median(fr.step_ns) / 1e6) if fr.step_ns else None
    return r, fin


def stream_batch_check(sysm, fr, c):
    """A1: the streaming state equals SystemV2.run on the same final per-domain arrays and on the composite as built."""
    parts_stream = fr.parts()
    ref = sysm.run({d: {k: v for k, v in c["parts"][d].items() if k in ("score", "count", "layers", "dom_alarm", "layer_alarm", "blame")} for d in sysm.domains}, explain=True)
    fin = fr.final()
    ok_alarm = bool((ref["alarm"] == fin["alarm"]).all())
    same = len(ref["events"]) == len(fin["events"]) and all(
        (a.start, a.first_alarm, a.end, a.blamed, a.response, a.domains, a.explanation) == (b.start, b.first_alarm, b.end, b.blamed, b.response, b.domains, b.explanation)
        for a, b in zip(ref["events"], fin["events"]))
    same_in = all(np.array_equal(parts_stream[d]["score"], c["parts"][d]["score"]) for d in sysm.domains if d in fr.part)
    return ok_alarm and same and same_in, {"alarm": ok_alarm, "events": same, "inputs": same_in, "score_diff": float(np.abs(ref["score"] - fin["score"]).max())}
