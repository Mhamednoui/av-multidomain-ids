"""WP7 S2 simulation, part 2: the enumeration of the composites (attack episodes, multi-domain scenarios, long network blocks, clean timelines) and the run of the frozen system v2.
See tools/WP7_S2_sim.py for the builder / evaluation and notes/WP7_system.md "S2 start" for the construction and the acceptance rule. One run, no re-seeding.
Usage: python -u -W ignore tools/WP7_S2_sim_main.py [attacks] [clean]       Output: ../data_extra/cache_v3/WP7/S2_sim_attacks.pkl, S2_sim_clean.pkl, results/WP7/S2_sim_stats.json
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP7_S2_lib as L
import WP7_S2_sim as M

import numpy as np

from fusion import correlator as CR
from fusion.system import load_system
from system.fusion_runner import LEVEL

ONSET = L.ONSET
GPS_FAMS = ["drift", "accel_drift", "doppler_spoof", "meaconing"]
COORD = {"K": ["gps_can"], "C": ["gnss_can", "can_bus"]}
log = M.log


def vehicle_attacked(fam, famset):
    return "gps+can" if fam in COORD[famset] else ("gps" if fam in GPS_FAMS else "cross")


def runs_of(mask):
    """Onsets and ends of the True runs of a bool array."""
    m = np.asarray(mask, bool)
    on = np.flatnonzero(m & ~np.r_[False, m[:-1]])
    off = np.flatnonzero(m & ~np.r_[m[1:], False])
    return list(zip(on, off))


def chain_domain(b, P, d, pool, n, seg_len=120):
    pos = 0
    while pos < n:
        s, st = b.clean_segment(pool, seg_len)
        k = b.place(P, d, pos, s, st, min(seg_len, n - pos), label=False)
        if not k:
            break
        pos += min(seg_len, n - pos)


def chain_vehicle(b, P, n):
    S = b.S
    pos = 0
    while pos < n:
        key = b.clean_vehicle_key()
        if b.fam == "K":
            v = S.veh_K["series"][key]
            m = min(v["n"], n - pos)
            b.place(P, "gps", pos, v["gps"], 0, m, label=False)
            b.place(P, "cross", pos, v["cross"], 0, m, label=False)
            lp = M.lidar_part(M.scan_table(S.lidar["clean"][key[0]]["rows"]), key[1] / 10.0, m)
            for kk in ("score", "count", "layers", "dom_alarm", "layer_alarm", "present"):
                P["lidar"][kk][pos:pos + m] = lp[kk][:m]
            pos += m
        else:
            s = S.veh_C["series"][key]
            m = min(len(s["score"]), n - pos)
            b.place(P, "cross", pos, s, 0, m, label=False)
            pos += m


def finish(b, cid, scenario, atype, attacked_key, attacked, P, n, label, group, extra=None):
    c = b.comp(cid, scenario, atype, attacked, P, n, label, group, extra)
    c["true_sensors"] = M.S5L.true_sensor(atype.split(":")[0], attacked_key) if scenario not in ("multi_can_gps", "multi_can_lidar") else (
        {"gps", "can"} if scenario == "multi_can_gps" else {"can", "lidar"})
    c["attacked_domain_key"] = attacked_key
    return c


def attack_composites(S, famset):
    b = M.Builder(S, famset)
    cid = 0
    cats = {}

    def nxt(prefix):
        nonlocal cid
        cid += 1
        return f"{famset}{cid:05d}-{prefix}"

    # ---- vehicle-block attacks (GPS, motion-sensor spoofs, coordinated)
    keys = sorted(S.veh_K["series"]) if famset == "K" else sorted(S.veh_C["series"])
    for key in keys:
        f = key[2]
        if f == "none":
            continue
        P, n, lab, grp = b.vehicle(key)
        b.fill_clean(P, n)
        att = vehicle_attacked(f, famset)
        yield finish(b, nxt("veh"), "vehicle", f, att, ["gps" if att in ("gps", "gps+can") else "cross"] + (["can"] if att == "gps+can" else []), P, n, lab, grp)
    # ---- LiDAR (K only): per-scan kinds, persistent episodes
    if famset == "K":
        for (d, kind), job in sorted(S.lidar["scan"].items()):
            P, n, _, grp = b.vehicle((d, 0, "none"))
            b.fill_clean(P, n)
            tab = M.scan_table(S.lidar["clean"][d]["rows"])
            ov = M.scan_table(job["rows"], len(tab["t"]))
            m = np.isfinite(ov["t"])
            for key in ("t", "score", "alarm", "layers", "layer_alarm", "attacked"):
                tab[key][m] = ov[key][m]
            lp = M.lidar_part(tab, 0.0, n)
            b.place_lidar(P, lp)
            yield finish(b, nxt("lidar"), "lidar_scan", kind, "lidar", ["lidar"], P, n, lp["label"], d)
        for (d, mode), job in sorted(S.lidar["ep"].items()):
            clean_tab = M.scan_table(S.lidar["clean"][d]["rows"])
            for e in job["episodes"]:
                tab = {k: v.copy() for k, v in clean_tab.items()}
                ov = M.scan_table(e["rows"], len(tab["t"]))
                m = np.isfinite(ov["t"])
                for key in ("t", "score", "alarm", "layers", "layer_alarm", "attacked"):
                    tab[key][m] = ov[key][m]
                j0 = max(0, int(np.floor(clean_tab["t"][e["s0"]])) - ONSET)
                P, n, _, grp = b.vehicle((d, 0, "none"), j0=j0)
                b.fill_clean(P, n)
                lp = M.lidar_part(tab, float(j0), n)
                b.place_lidar(P, lp)
                on = int(np.flatnonzero(lp["label"])[0]) if lp["label"].any() else -1
                yield finish(b, nxt("lidar_ep"), "lidar_episode", e["kind"], "lidar", ["lidar"], P, n, lp["label"], d, {"onset_true": on})
    # ---- ROAD CAN episodes (+ multi-domain scripted blocks), V2X episodes
    can_eps = []
    for s in b.can_att:
        for (a, z) in runs_of(s["label"]):
            can_eps.append((s, int(a)))
    for s, o in can_eps:
        key = b.clean_vehicle_key()
        P, n, _, grp = b.vehicle(key)
        b.fill_clean(P, n, skip=("can",))
        b.place(P, "can", 0, s, o - ONSET, n)
        P["can"]["label"][:ONSET - min(ONSET, o)] = False
        lab = P["can"]["label"] & (np.arange(n) >= min(ONSET, o))
        yield finish(b, nxt("can"), "can_episode", s["family"], "can", ["can"], P, n, lab, s["name"], {"onset_true": min(ONSET, o)})
    if famset == "K":
        for s, o in can_eps:
            # (a) CAN attack + GPS spoof on the same car
            gk = sorted(k for k in S.veh_K["series"] if k[2] in GPS_FAMS)
            key = gk[int(b.rng.integers(len(gk)))]
            P, n, vlab, grp = b.vehicle(key)
            b.fill_clean(P, n, skip=("can",))
            b.place(P, "can", 0, s, o - ONSET, n)
            lab = vlab | (P["can"]["label"] & (np.arange(n) >= min(ONSET, o)))
            yield finish(b, nxt("multi"), "multi_can_gps", f"{s['family']}+{key[2]}", "multi", ["can", "gps"], P, n, lab, f"{key[0]}|{s['name']}")
            # (b) CAN attack + LiDAR PointDrop on the same car
            d = sorted(S.lidar["clean"])[int(b.rng.integers(len(S.lidar["clean"])))]
            job = S.lidar["scan"].get((d, "PointDrop"))
            if job is None:
                continue
            P, n, _, grp = b.vehicle((d, 0, "none"))
            b.fill_clean(P, n, skip=("can",))
            tab = M.scan_table(S.lidar["clean"][d]["rows"])
            ov = M.scan_table(job["rows"], len(tab["t"]))
            m = np.isfinite(ov["t"])
            for k2 in ("t", "score", "alarm", "layers", "layer_alarm", "attacked"):
                tab[k2][m] = ov[k2][m]
            lp = M.lidar_part(tab, 0.0, n)
            b.place_lidar(P, lp)
            b.place(P, "can", 0, s, o - ONSET, n)
            lab = lp["label"] | (P["can"]["label"] & (np.arange(n) >= min(ONSET, o)))
            yield finish(b, nxt("multi"), "multi_can_lidar", f"{s['family']}+PointDrop", "multi", ["can", "lidar"], P, n, lab, f"{d}|{s['name']}")
    for s in b.v2x_att:
        fams = sorted(set(f for f in s["fam"] if f))
        for f in fams:
            for (a, z) in runs_of(np.asarray(s["fam"], object) == f):
                key = b.clean_vehicle_key()
                P, n, _, grp = b.vehicle(key)
                b.fill_clean(P, n, skip=("v2x",))
                b.place(P, "v2x", 0, s, int(a) - ONSET, n)
                o = min(ONSET, int(a))
                lab = P["v2x"]["label"] & (np.arange(n) >= o)
                yield finish(b, nxt("v2x"), "v2x_episode", f, "v2x", ["v2x"], P, n, lab, s["name"], {"onset_true": o})
    # ---- long network blocks (vehicle domains chained clean underneath)
    for s in b.net_att:
        fam = np.asarray(s["fam"], object)
        lab = np.asarray(s["label"], bool)
        runs = []
        for f in sorted(set(x for x in fam[lab])):
            runs += [(f, int(a), int(z)) for a, z in runs_of(lab & (fam == f))]
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
            chain_vehicle(b, P, n)
            for d in ("can", "v2x"):
                chain_domain(b, P, d, b.can_clean if d == "can" else b.v2x_clean, n)
            nl = np.zeros(n, bool)
            nl[a - j0:z - j0 + 1] = True
            yield finish(b, nxt("net"), "network_block", f, "network", ["network"], P, n, nl & P["network"]["label"], s["name"], {"onset_true": flow_on - j0, "t_block0": s.get("t_block0")})


def clean_timelines(S, famset):
    b = M.Builder(S, famset, seed_tag=1)
    for s in b.net_clean:
        n = len(s["score"])
        P = b.new_parts(n)
        b.place(P, "network", 0, s, 0, n, label=False)
        chain_vehicle(b, P, n)
        for d in ("can", "v2x"):
            chain_domain(b, P, d, b.can_clean if d == "can" else b.v2x_clean, n)
        c = {"id": f"{famset}-clean-{s['name']}", "family": famset, "scenario": "clean_timeline", "type": "none", "attacked": [], "n": n, "parts": P, "label": np.zeros(n, bool),
             "onset": -1, "onset_true": -1, "group": s["name"], "host_flows": s["host_flows"], "audit_flows": s["audit_flows"]}
        yield c


def clean_record(c, fr, sysm):
    fin = fr.final()
    ev = fin["events"]
    over = {lv: sum(e.response == lv for e in ev) for lv in CR.LEVELS[1:]}
    var = {"SAFE_STOP": 0}
    for e in ev:
        nd = len([d for d in e.domains if d in M.MC_OR_CROSS])
        var["SAFE_STOP"] += CR.respond(e.blame_counts, e.blamed, e.end - e.start + 1, nd, 2)[0] == "SAFE_STOP"
    return {"id": c["id"], "family": c["family"], "group": c["group"], "n": c["n"], "hours": c["n"] / 3600.0, "alarm_ticks": int(fin["alarm"].sum()), "events": len(ev), "levels": over,
            "safe_stop_variant": int(var["SAFE_STOP"]), "explained": int(sum("first alarm: system alarm" in e.explanation for e in ev)),
            "event_domains": [e.domains for e in ev], "event_blamed": [e.blamed for e in ev], "event_duration": [e.end - e.start + 1 for e in ev],
            "own_alarm_share": {d: float(fin["own"][:, j].mean()) for j, d in enumerate(sysm.domains)}, "step_ms_median": float(np.median(fr.step_ns) / 1e6),
            "present_share": {d: float(c["parts"][d]["present"].mean()) for d in sysm.domains}}


def main():
    stages = [a for a in sys.argv[1:] if a in ("attacks", "clean")] or ["attacks", "clean"]
    S = M.Sources()
    sysd = load_system(2)
    out = {}
    if "attacks" in stages:
        recs, checks = [], []
        for famset in ("K", "C"):
            sysm = sysd[famset]
            n = 0
            for c in attack_composites(S, famset):
                fr = M.run_composite(sysm, c, track=True)
                r, fin = M.evaluate(c, fr, sysm)
                ok, det = M.stream_batch_check(sysm, fr, c)
                r["stream_equals_batch"] = bool(ok)
                if not ok:
                    r["check_detail"] = det
                r["label_ticks"] = int(c["label"].sum())
                r["step_ms"] = fr.step_ns[:]
                recs.append(r)
                n += 1
                if n % 200 == 0:
                    log(famset, "composites", n)
            log(famset, "attack composites", n)
        L.save_pickle(recs, "S2_sim_attacks.pkl")
        out["attacks"] = len(recs)
        log("attacks saved", len(recs), "A1 mismatches", sum(not r["stream_equals_batch"] for r in recs))
    if "clean" in stages:
        recs = []
        for famset in ("K", "C"):
            sysm = sysd[famset]
            for c in clean_timelines(S, famset):
                fr = M.run_composite(sysm, c, track=False)
                ok, det = M.stream_batch_check(sysm, fr, c)
                r = clean_record(c, fr, sysm)
                r["stream_equals_batch"] = bool(ok)
                recs.append(r)
                log(famset, c["group"], "n", c["n"], "alarm ticks", r["alarm_ticks"], "events", r["events"], "levels", r["levels"], "A1", ok)
        L.save_pickle(recs, "S2_sim_clean.pkl")
        out["clean"] = len(recs)
    (L.OUT / "S2_sim_stats.json").write_text(json.dumps(out))


if __name__ == "__main__":
    main()
