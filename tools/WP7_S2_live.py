"""WP7 S2 live co-simulation (acceptance A3): six composite drives are driven FULLY LIVE: every domain's raw samples (GPS fixes, motion-witness estimates, LiDAR scans, ROAD CAN frames,
VeReMi messages, D10 flows, comma witness residual rows) are pushed in stream-time order into the S1 runners (which publish on one EvidenceBus), the runners' Evidence is turned into 1 s tick
values, handed to the FusionRunner at the second it exists, and the frozen system v2 fires second by second. The result (per-domain tick arrays, alarms, events, blame, response) is
compared with the REPLAY of the same composite from the stored domain passes (the construction used for the S2 numbers). Equality = the replay is a faithful stand-in for the live system.
Sources that start before the composite (warm context of the CAN / V2X / network streams) are pushed from their stream start, as a running monitor would have.
Rule: step T pushes every sample with stream time < T (a sample of tick k is therefore known at T = k + 1; a CAN window when the first frame of the next second arrives, a network bin
when the first flow of the next bin arrives). The composites are specified explicitly (no random draw): 1 K clean drive 0052, 2 K gps_can drive 0052, 3 K ROAD CAN attack (fuzzing),
4 C comma gnss_can window, 5 K V2X attack ego view, 6 network attack block (network alone). Output: results/WP7/S2_live.json. Usage: python -u -W ignore tools/WP7_S2_live.py [ids ...]
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP7_S2_lib as L
import WP7_S2_sim as M
import WP7_S2_sim_main as MM
import WP7_S2_veh as V
import WP7_S2_can as CANP
import WP7_S2_v2x as V2P
import WP7_S2_net as NETP

import numpy as np

from can.domain import CanDomain
from fusion.system import load_system
from gps import stream as GS
from lidar import ego
from lidar.data import load as load_scan, scan_files
from network.domain import RAW_COLUMNS, NetworkDomain
from system.bus import EvidenceBus
from system.can_runner import CANRunner
from system.cross_runner import CrossRunner
from system.fusion_runner import FusionRunner, replay
from system.gps_runner import GPSRunner
from system.lidar_runner import LidarRunner
from system.net_runner import NetworkRunner
from system.v2x_runner import V2XPhysicsDomain, V2XRunner
from tools.WP4_S3_lib import load as load_net, stream as net_stream
import WP5_S5_dev as dev5
from v2x import splitting

log = M.log
ROOT = L.ROOT
SKIP = set(x for x in os.environ.get("S2_LIVE_SKIP", "").split(",") if x)       # debugging aid only: domains left out of BOTH the live and the replay side
FROZEN_LIDAR = ROOT / "results" / "WP3" / "S9" / "frozen_lidar"


class Handler:
    """A raw sample stream of one domain: sorted (t_rel, sample) pairs, pushed into the runner when the system clock passes them."""

    def __init__(self, name, runner, samples):
        self.name, self.runner = name, runner
        self.samples = sorted(samples, key=lambda x: x[0])
        self.i = 0
        self.flushed = False

    def maybe_flush(self, T, live):
        """End of the stream (all samples pushed and the clock is past the last one): the runner emits what it still holds, as a monitor does when its input ends."""
        if not self.flushed and self.i == len(self.samples) and (not self.samples or self.samples[-1][0] < T):
            self.flushed = True
            self.on_push(self.runner.flush(), None, T, live)

    def advance(self, T, live):
        while self.i < len(self.samples) and self.samples[self.i][0] < T:
            sample = self.samples[self.i][1]
            self.i += 1
            self.on_push(self.runner.push(sample), sample, T, live)
        self.maybe_flush(T, live)
        self.on_tick(T, live)

    def on_push(self, out, sample, T, live):
        pass

    def on_tick(self, T, live):
        pass


class GpsH(Handler):
    def __init__(self, runner, df):
        t0 = float(df["t"].iloc[0])
        super().__init__("gps", runner, [(float(r["t"]) - t0, r) for r in V.samples(df)])
        self.t0 = t0

    def on_push(self, out, sample, T, live):
        if not out:
            return
        comb, lay = out[0], out[1:]
        live.submit("gps", int(round(comb.t - self.t0)), comb.score, 1.0, [e.score for e in lay], comb.alarm, [e.alarm for e in lay])


class CrossH(Handler):
    """MotionEstimates (KITTI) or residual rows (comma) of the cross-domain witnesses."""

    def __init__(self, runner, samples, grid):
        super().__init__("cross", runner, [(t - grid[0], s) for t, s in samples])
        self.grid = grid

    def on_push(self, out, sample, T, live):
        for ev in out:
            score, layers, alarm, blame, present = L.cross_ticks([ev], self.grid)
            k = int(np.flatnonzero(present)[0])
            live.submit("cross", k, score[k], 1.0, layers[k], alarm[k], layers[k] > 0, blame[k])


class TickAcc(Handler):
    """Handler that accumulates per-sample results into 1 s tick maxima and submits tick T-1 at step T."""

    def __init__(self, name, runner, samples, n, width):
        super().__init__(name, runner, samples)
        self.n, self.width, self.acc = n, width, {}

    def add(self, k, comb, lay):
        if 0 <= k < self.n:
            a = self.acc.setdefault(k, {"score": np.float32(0), "layers": np.zeros(self.width, np.float32), "alarm": False, "lalarm": np.zeros(self.width, bool), "count": 0.0})
            a["score"] = max(a["score"], np.float32(comb.score))
            a["layers"] = np.maximum(a["layers"], np.array([e.score for e in lay], np.float32))
            a["alarm"] |= bool(comb.alarm)
            a["lalarm"] |= np.array([e.alarm for e in lay], bool)
            a["count"] += 1.0

    def on_tick(self, T, live):
        k = int(T) - 1
        if 0 <= k < self.n:
            a = self.acc.pop(k, None)
            if a is None:
                live.submit(self.name, k, 0.0, 0.0, np.zeros(self.width), False, np.zeros(self.width, bool))
            else:
                live.submit(self.name, k, a["score"], a["count"], a["layers"], a["alarm"], a["lalarm"])


class LidarH(TickAcc):
    def __init__(self, runner, drive, n):
        files, pose = scan_files(drive), ego.poses(drive)
        t = np.asarray(GS.load_oxts(drive)["t"], float)
        self.files, self.pose, self.t = files, pose, t
        super().__init__("lidar", runner, [(float(t[i]), i) for i in range(len(files))], n, 4)

    def advance(self, T, live):
        while self.i < len(self.samples) and self.samples[self.i][0] < T:
            i = self.samples[self.i][1]
            self.i += 1
            out = self.runner.push({"points": load_scan(self.files[i]), "pose": self.pose[i], "t": float(self.t[i]), "sample_id": f"{i}"})
            self.add(int(np.floor(self.t[i])), out[0], out[1:])
        self.maybe_flush(T, live)
        self.on_tick(T, live)


class CanH(Handler):
    def __init__(self, runner, name, folder, start, n, series):
        t, ids, dlc, B = CANP.load(name)
        self.tab = dict(np.load(CANP.TAB / folder / (name + ".npz")))
        self.s0, self.start, self.n = int(series["sec0"]), start, n
        self.row = {int(s): j for j, s in enumerate(self.tab["sec"])}
        super().__init__("can", runner, [(float(t[i]) - (self.s0 + start), (t[i], ids[i], dlc[i], B[i])) for i in range(len(t))])

    def on_push(self, out, sample, T, live):
        k_ = len(self.runner.dom.layers) + 1
        for j in range(0, len(out), k_):
            comb, lay = out[j], out[j + 1:j + k_]
            sec = int(comb.sample_id.split("/")[-1])
            if sec not in self.row or not bool(self.tab["ok"][self.row[sec]]):
                continue
            k = sec - self.s0 - self.start
            if 0 <= k < self.n:
                live.submit("can", k, comb.score, 1.0, [e.score for e in lay], comb.alarm, [e.alarm for e in lay])


class V2xH(TickAcc):
    def __init__(self, runner, blk, ego_id, start, n, clean):
        lab, snd, t = blk["label"].to_numpy(), blk["sender"].to_numpy(), blk["t"].to_numpy(float)
        x, y = blk["x"].to_numpy(float), blk["y"].to_numpy(float)
        me = snd == ego_id
        te = t[me]
        t0, t1 = te.min(), te.max()
        w = (t >= t0) & (t <= t1) & ~me
        ex, ey = np.interp(t[w], te, x[me]), np.interp(t[w], te, y[me])
        near = np.hypot(x[w] - ex, y[w] - ey) <= V2P.RADIUS_M
        heard = np.zeros(len(blk), bool)
        heard[np.flatnonzero(w)[near]] = True
        if clean:
            heard &= lab == 0
        self.heard = heard
        self.k = np.floor(t - t0).astype(int) - start
        super().__init__("v2x", runner, [(float(t[i]) - (t0 + start), i) for i in range(len(blk))], n, 12)
        self.recs = blk.to_dict("records")

    def advance(self, T, live):
        while self.i < len(self.samples) and self.samples[self.i][0] < T:
            i = self.samples[self.i][1]
            self.i += 1
            out = self.runner.push(self.recs[i])
            if self.heard[i]:
                self.add(int(self.k[i]), out[0], out[1:])
        self.maybe_flush(T, live)
        self.on_tick(T, live)


class NetH(Handler):
    """Flows of one D10 block (all hosts); the host's flows become minute-hold ticks at the moment their bin closes."""

    def __init__(self, runner, blk, t_block0, j0, n, host=NETP.HOST):
        recs = blk[RAW_COLUMNS].to_dict("records")
        ts = blk["t"].to_numpy(float)
        self.host = (blk["src_id"].to_numpy() == host) | (blk["dst_id"].to_numpy() == host)
        self.ts, self.j0, self.n = ts, j0, n
        self.umin = int(ts[self.host].min() // 60)
        super().__init__("network", runner, [(float(ts[i]) - (t_block0 + j0), r) for i, r in enumerate(recs)])

    def on_push(self, out, sample, T, live):
        if not out:
            return
        g = sum(1 for e in out if e.sample_id == out[0].sample_id)
        by_min = {}
        for j in range(0, len(out), g):
            i = int(out[j].sample_id)
            if self.host[i]:
                by_min.setdefault(int(self.ts[i] // 60), []).append((out[j], out[j + 1:j + g]))
        for m, items in by_min.items():
            V_ = np.max([[e.score for e in lay] for _, lay in items], axis=0).astype(np.float32)
            A_ = np.any([[e.alarm for e in lay] for _, lay in items], axis=0)
            sc = np.float32(max(np.float32(c.score) for c, _ in items))
            al = bool(any(c.alarm for c, _ in items))
            j = m - self.umin + 1
            for s in range(60):
                k = j * 60 + s - self.j0
                if 0 <= k < self.n:
                    live.submit("network", k, sc, float(len(items)), V_, al, A_)


class Live:
    def __init__(self, sysm, n):
        self.fr = FusionRunner(sysm, track_events=True)
        self.fr.reset(n)
        self.handlers = []

    def submit(self, d, k, score, count, layers, dom_alarm, layer_alarm, blame=None):
        self.fr.submit(d, k, score, count, layers, dom_alarm, layer_alarm, blame)

    def run(self, H):
        for T in range(1, int(H) + 1):
            for h in self.handlers:
                h.advance(T, self)
            self.fr.step(T)
        return self.fr


def compare(sysm, live_fr, c, H):
    """Live fusion state vs the replay of the composite c from the stored passes (same horizon)."""
    rp = replay(sysm, {d: c["parts"][d] for d in sysm.domains}, {d: c["parts"][d]["avail"] for d in sysm.domains}, c["n"], track_events=True, horizon=H)
    pl, pr = live_fr.parts(), rp.parts()
    diffs = {}
    for d in sysm.domains:
        a, b = pl[d], pr[d]
        diffs[d] = {k: bool(np.array_equal(np.asarray(a[k]), np.asarray(b[k]))) for k in ("score", "count", "dom_alarm")}
        if a["layers"].shape == b["layers"].shape:
            diffs[d]["layers"] = bool(np.array_equal(a["layers"], b["layers"]))
            diffs[d]["layer_alarm"] = bool(np.array_equal(a["layer_alarm"], b["layer_alarm"]))
        else:
            diffs[d]["layers"] = bool(not a["layers"].any() and not b["layers"].any())
        diffs[d]["blame"] = bool(all((x is None and y is None) or str(x) == str(y) for x, y in zip(a["blame"], b["blame"])))
    fl, fr_ = live_fr.final(), rp.final()
    ev_same = len(fl["events"]) == len(fr_["events"]) and all((x.start, x.end, x.blamed, x.response, x.domains, x.explanation) == (y.start, y.end, y.blamed, y.response, y.domains, y.explanation)
                                                              for x, y in zip(fl["events"], fr_["events"]))
    ok = all(all(v.values()) for v in diffs.values()) and bool((fl["alarm"] == fr_["alarm"]).all()) and ev_same
    lag = np.nan_to_num(live_fr.first_known - rp.first_known, nan=0.0)
    return {"equal": bool(ok), "parts_equal": diffs, "alarm_ticks": int(fl["alarm"].sum()), "events": len(fl["events"]), "events_equal": bool(ev_same),
            "first_known_equal": bool(np.array_equal(np.nan_to_num(live_fr.first_known, nan=-1), np.nan_to_num(rp.first_known, nan=-1))), "max_first_known_lag_s": float(np.abs(lag).max()),
            "n": c["n"], "horizon": int(H)}


def horizon(c, doms):
    mx = 0.0
    for d in doms:
        p = c["parts"][d]
        if p["present"].any():
            mx = max(mx, float(np.max(p["avail"][p["present"]])))
    return int(max(c["n"], np.ceil(mx)))


def build_composite(S, fam, spec):
    """The replay-side composite of a live case (from the stored passes) plus the facts the live side needs. spec as in the case list; no random draw."""
    b = M.Builder(S, fam)
    aux = {}
    if "net" in spec:
        s, f0, run_i = spec["net"]
        fam_t, lab = np.asarray(s["fam"], object), np.asarray(s["label"], bool)
        a, z = MM.runs_of(lab & (fam_t == f0))[run_i]
        j0 = max(max(a - 60, 0) - L.ONSET, 0)
        n = min(z + 361, len(lab)) - j0
        P = b.new_parts(n)
        b.place(P, "network", 0, s, j0, n)
        aux.update(series=s, j0=j0)
        return {"n": n, "parts": P}, aux
    key = spec.get("veh") or spec["vehC"]
    P, n, vlab, grp = b.vehicle(key)
    cname, folder, start = spec["can"]
    cs = next(x for x in S.can if x["name"] == cname)
    if start is None:
        start = int(MM.runs_of(cs["label"])[0][0]) - L.ONSET
    b.place(P, "can", 0, cs, start, n, label=False)
    vs, vstart, vclean = spec["v2x"]
    if vstart is None and vs is not None:
        fam_s = sorted(set(f for f in vs["fam"] if f))[0]
        vstart = int(MM.runs_of(np.asarray(vs["fam"], object) == fam_s)[0][0]) - L.ONSET
    if "v2x" not in SKIP and vs is not None:
        b.place(P, "v2x", 0, vs, vstart, n, label=False)
    aux.update(key=key, cname=cname, folder=folder, cstart=start, cseries=cs, vs=vs, vstart=vstart, vclean=vclean)
    return {"n": n, "parts": P}, aux


def n_events(sysm, c):
    P = c["parts"]
    fr = replay(sysm, {d: P[d] for d in sysm.domains}, {d: P[d]["avail"] for d in sysm.domains}, c["n"], track_events=False)
    return len(fr.final()["events"])


def main():
    t_start = time.time()
    S = M.Sources()
    if "lidar" in SKIP:
        rows = [{"idx": i, "t": 0.1032 * i, "score": 0.0, "alarm": False, "layers": [0.0] * 4, "layer_alarm": [False] * 4, "ns": 1, "attacked": False, "tag": ""} for i in range(500)]
        S.lidar["clean"] = {d: {"rows": rows, "drive": d} for d in ["0001", "0005", "0028", "0039", "0052", "0079", "0095"]}
    sysd = load_system(2)
    want = [a for a in sys.argv[1:]] or None
    results = []
    dom_can = CanDomain.load(V.FROZEN_CAN)
    bus = EvidenceBus()
    clean_v2x = next((s for s in S.v2x if s["kind"] == "clean" and len(s["score"]) >= 60), None)
    att_v2x = [s for s in S.v2x if s["kind"] == "attack" and any(f for f in set(s["fam"]) if f) and len(s["score"]) >= 60]
    vf, sp = dev5.load_frames()
    te = splitting.rows_of(vf, sp["test"])
    te = te[te["label"] != 12].sort_values("t", kind="stable").reset_index(drop=True)
    v2dom = V2XPhysicsDomain.load(L.OUT / "frozen_v2x")
    amb = ("ambient_dyno_reverse", "test", 0)
    can_att = sorted([s for s in S.can if s["kind"] == "attack"], key=lambda s: s["frames"])
    gnss = [k for k in sorted(S.veh_C["series"]) if k[2] == "gnss_can"]
    netc = sorted([(x["host_flows"], x) for x in S.net if x["kind"] == "attack"], key=lambda t: t[0])

    def first_with_events(fam, specs):
        """The first candidate whose replay composite has at least one alert event (selection by the replay of the stored passes; falls back to the first candidate)."""
        for sp_ in specs:
            c, _ = build_composite(S, fam, sp_)
            if n_events(sysd[fam], c) > 0:
                return sp_
        return specs[0]

    def net_spec(x):
        return {"net": (x, sorted(set(np.asarray(x["fam"], object)[np.asarray(x["label"], bool)]))[0], 0)}

    cases = [("live1_K_clean", "K", lambda: {"veh": ("0052", 0, "none"), "can": amb, "v2x": (clean_v2x, 0, True)}),
             ("live2_K_gps_can", "K", lambda: first_with_events("K", [{"veh": (d, ph, "gps_can"), "can": amb, "v2x": (clean_v2x, 0, True)} for d in ("0052", "0079", "0001") for ph in range(10)])),
             ("live3_K_can_attack", "K", lambda: first_with_events("K", [{"veh": ("0052", 0, "none"), "can": (s["name"], "test", None), "v2x": (clean_v2x, 0, True)} for s in can_att])),
             ("live4_C_gnss_can", "C", lambda: first_with_events("C", [{"vehC": k, "can": amb, "v2x": (clean_v2x, 0, True)} for k in gnss])),
             ("live5_K_v2x_attack", "K", lambda: first_with_events("K", [{"veh": ("0052", 0, "none"), "can": amb, "v2x": (s, None, False)} for s in att_v2x[:40]])),
             ("live6_net_block", "K", lambda: first_with_events("K", [net_spec(x) for _, x in netc]))]
    for cid, fam, mk in cases:
        if want and cid not in want:
            continue
        t0 = time.time()
        sysm = sysd[fam]
        spec = mk()
        c, aux = build_composite(S, fam, spec)
        n = c["n"]
        bus.clear()
        live = Live(sysm, n)
        if "net" in spec:
            s = aux["series"]
            allf = net_stream(load_net("D10"), "test")
            allf["src_ip"], allf["dst_ip"] = "h" + allf["src_id"].astype(str), "h" + allf["dst_id"].astype(str)
            allf["blk"] = allf["day"].astype(str) + "|" + allf["period"].astype(str)
            blk = allf[allf["blk"] == s["name"]].sort_values(["t", "row"], kind="stable").reset_index(drop=True)
            runner = NetworkRunner(NetworkDomain.load(NETP.FROZEN), bus=bus, per_layer=True)
            runner.reset("live")
            live.handlers = [NetH(runner, blk, s["t_block0"], aux["j0"], n)]
            what = f"network {s['name']}"
        else:
            key = aux["key"]
            what = f"{key}"
            if "veh" in spec:
                d, ph, f = key
                wm, ox = V.wheel_motion(d, dom_can)
                vi = V.vehicle_inputs(d, ph, ox, wm)
                grid = vi["grid"]
                grun = GPSRunner(V.FROZEN_GPS, bus=bus)
                grun.reset(f"{d}/{f}")
                crun = CrossRunner(L.kitti_cross_object(), bus=bus)
                crun.reset(f"{d}/{f}")
                mes = sorted([m for ms in vi["fams"][f].values() for m in ms], key=lambda m: (m.t, V.SRC_ORDER[m.source]))
                live.handlers += [GpsH(grun, vi["runs"][f if f in vi["runs"] else "none"]), CrossH(crun, [(m.t, m) for m in mes], grid)]
                if "lidar" not in SKIP:
                    lrun = LidarRunner(FROZEN_LIDAR, bus=bus)
                    lrun.reset(d)
                    live.handlers.append(LidarH(lrun, d, n))
            else:
                objs, clsall, setup = L.comma_cross_objects()
                for (rn, ri, wi, fm, rp, g, rr, t_on) in V.comma_windows():
                    if (rn, wi, fm, rp) == key:
                        break
                crun = CrossRunner(objs[clsall[rn]], bus=bus)
                crun.reset("live")
                edges = [e.name for e in crun.obj.edges]
                live.handlers += [CrossH(crun, [(float(g[i]), {"t": float(g[i]), "r": {k: float(rr[k][0][i]) for k in edges if k in rr}, "v": {k: float(rr[k][1][i]) for k in edges if k in rr}})
                                                 for i in range(len(g))], g)]
            crunner = CANRunner(V.FROZEN_CAN, bus=bus, per_layer=True, explain=True)
            crunner.reset(aux["cname"])
            live.handlers.append(CanH(crunner, aux["cname"], aux["folder"], aux["cstart"], n, aux["cseries"]))
            if "v2x" not in SKIP and aux["vs"] is not None:
                vrunner = V2XRunner(v2dom, bus=bus, per_layer=True)
                vrunner.reset("live")
                grp_v, ego_id = aux["vs"]["name"].split("/")[0], aux["vs"]["name"].split("/")[1][3:]
                blk = te[te["group"] == grp_v].reset_index(drop=True)
                ego_val = type(blk["sender"].iloc[0])(ego_id)
                live.handlers.append(V2xH(vrunner, blk, ego_val, aux["vstart"], n, aux["vclean"]))
        H = horizon(c, sysm.domains)
        log(cid, what, "n", n, "horizon", H, "handlers", [h.name for h in live.handlers])
        live.run(H)
        res = compare(sysm, live.fr, c, H)
        by = {}
        for r in bus.records:
            by.setdefault(r.runner, []).append(r.delay_ms)
        res.update({"id": cid, "family": fam, "what": what, "wall_s": time.time() - t0, "bus_records": len(bus.records),
                    "bus_delay_ms": {k: {"n": len(v), "median": float(np.median(v)), "p99": float(np.percentile(v, 99)), "max": float(np.max(v))} for k, v in by.items()}})
        results.append(res)
        log(cid, {k: v for k, v in res.items() if k not in ("parts_equal", "bus_delay_ms")})
        if not res["equal"]:
            log("  parts_equal", res["parts_equal"])
    out = {"n": len(results), "mismatches": int(sum(not r["equal"] for r in results)), "composites": results, "wall_s": time.time() - t_start}
    (L.OUT / ("S2_live.json" if not want else "S2_live_partial.json")).write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
