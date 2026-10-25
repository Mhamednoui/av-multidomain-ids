"""WP7 S2 report: aggregates the per-composite records of tools/WP7_S2_sim_main.py (attack composites, clean timelines), the pass logs (latency, checks) and the live co-simulation check
into results/WP7/S2_results.json, S2_tables.md and results/WP7/S2_acceptance.json (the make_report slot "M3 simulation"). No number is typed: every value is computed here from the stored records.
Usage: python -u -W ignore tools/WP7_S2_report.py
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP7_S2_lib as L

import numpy as np

import WP6_S4_lib as S4L
from fusion.correlator import LEVELS

OUT = L.OUT
GPS_FAMS = ["drift", "accel_drift", "doppler_spoof", "meaconing"]
COORD = {"K": ["gps_can"], "C": ["gnss_can", "can_bus"]}
SINGLE_SCEN = ("vehicle", "lidar_scan", "can_episode", "v2x_episode", "network_block")
RNG = np.random.default_rng([L.SEED, 77, 9])
NB = 1000


def attacked_key(r):
    s, t = r["scenario"], r["type"]
    if s == "vehicle":
        return "gps+can" if t in COORD[r["family"]] else ("gps" if t in GPS_FAMS else "cross")
    return {"lidar_scan": "lidar", "lidar_episode": "lidar", "can_episode": "can", "v2x_episode": "v2x", "network_block": "network"}.get(s, "multi")


def pct(x, d=1):
    return None if x is None else float(round(100 * x, d))


def boot_mean_over_types(recs, key, types, nb=NB):
    """Mean over types of the per-type mean of `key`; bootstrap: groups resampled when a type has >= 3 groups, else its episodes."""
    per = {}
    for t in types:
        rs = [r for r in recs if (r["scenario"], r["type"]) == t]
        if rs:
            per[t] = (np.array([float(key(r)) for r in rs]), np.array([r["group"] for r in rs]))
    if not per:
        return None, None
    est = float(np.mean([v[0].mean() for v in per.values()]))
    out = []
    for _ in range(nb):
        m = []
        for v, g in per.values():
            ug = np.unique(g)
            if len(ug) >= 3:
                pick = RNG.choice(ug, len(ug))
                m.append(np.mean(np.concatenate([v[g == u] for u in pick])))
            else:
                m.append(v[RNG.integers(len(v), size=len(v))].mean())
        out.append(np.mean(m))
    return est, [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))]


def ratio_ci(num, den, nb=NB):
    num, den = np.asarray(num, float), np.asarray(den, float)
    est = num.sum() / den.sum()
    out = []
    for _ in range(nb):
        i = RNG.integers(len(num), size=len(num))
        out.append(num[i].sum() / den[i].sum())
    return float(est), [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))]


def median_iqr(x):
    x = [v for v in x if v is not None]
    if not x:
        return None
    return {"median": float(np.median(x)), "q25": float(np.percentile(x, 25)), "q75": float(np.percentile(x, 75)), "n": len(x)}


def type_table(recs):
    out = {}
    for (fam, scen, t), rs in groupby(recs, lambda r: (r["family"], r["scenario"], r["type"])).items():
        det = [r for r in rs if r["detected"]]
        row = {"family": fam, "scenario": scen, "type": t, "n": len(rs), "groups": len({r["group"] for r in rs}), "event_detection": float(np.mean([r["detected"] for r in rs])),
               "tick_detection": float(np.mean([r["tick_detected"] for r in rs])), "delay_tick": median_iqr([r["delay"] for r in det]),
               "delay_available": median_iqr([r["delay_available"] for r in det]), "alarm_ticks_in_composite": float(np.mean([r["alarm_ticks"] for r in rs]))}
        if det:
            bl = Counter(r["blame"] for r in det)
            row["blame"] = {k: float(bl.get(k, 0) / len(det)) for k in ("correct", "wrong", "undecided")}
            rm = Counter(r.get("response_max") for r in det)
            row["response_max"] = {k: float(rm.get(k, 0) / len(det)) for k in LEVELS[1:]}
            rv = Counter(r.get("response_max_variant") for r in det)
            row["response_max_variant"] = {k: float(rv.get(k, 0) / len(det)) for k in LEVELS[1:]}
            ac = Counter(a for r in det for a in r.get("actions", []))
            row["actions"] = {k: float(v / len(det)) for k, v in ac.most_common(4)}
            dg = Counter(d for r in det for d in r.get("degraded", []))
            row["degraded_domains"] = {k: float(v / len(det)) for k, v in dg.most_common(4)}
            row["t_degrade"] = median_iqr([r.get("t_DEGRADE") for r in det if r.get("t_DEGRADE") is not None])
            row["t_safe_stop"] = median_iqr([r.get("t_SAFE_STOP") for r in det if r.get("t_SAFE_STOP") is not None])
            row["share_degrade_or_more"] = float(np.mean([r.get("response_max") in ("DEGRADE", "SAFE_STOP") for r in det]))
        out[f"{fam}|{scen}|{t}"] = row
    return out


def groupby(items, key):
    d = defaultdict(list)
    for x in items:
        d[key(x)].append(x)
    return d


def main():
    att = L.load_pickle("S2_sim_attacks.pkl")
    cln = L.load_pickle("S2_sim_clean.pkl")
    res = {"exposure": "5th scoring of fusion test data (S3, S4, S5, S5b before); one run; seed [42, 77, 2, ord(family)]"}
    import hashlib
    from fusion.system import load_system
    sysd = load_system(2)
    pk = L.ROOT / "results" / "WP6" / "system_v2.pkl"
    res["system"] = {"file": "results/WP6/system_v2.pkl", "sha256": hashlib.sha256(pk.read_bytes()).hexdigest(), "config_version": sysd["K"].config_version,
                     **{fam: {"entries": sysd[fam].entries, "threshold": float(sysd[fam].fusion.threshold), "method": sysd[fam].fusion.method, "correlator": sysd[fam].correlator.to_dict()} for fam in ("K", "C")}}
    # ------------------------------------------------------------- A1 stream integrity
    n_att, n_cl = len(att), len(cln)
    mism = [r["id"] for r in att if not r["stream_equals_batch"]] + [r["id"] for r in cln if not r["stream_equals_batch"]]
    res["A1"] = {"attack_composites": n_att, "clean_timelines": n_cl, "mismatches": len(mism), "mismatch_ids": mism[:20]}
    # ------------------------------------------------------------- per type tables
    tabs = {fam: type_table([r for r in att if r["family"] == fam]) for fam in ("K", "C")}
    res["by_type"] = tabs
    # ------------------------------------------------------------- aggregates per family
    agg = {}
    for fam in ("K", "C"):
        recs = [r for r in att if r["family"] == fam]
        single = [r for r in recs if r["scenario"] in SINGLE_SCEN and r["type"] not in COORD[fam]]
        types = sorted({(r["scenario"], r["type"]) for r in single})
        cat = {t: S4L.category(t[1], attacked_key(next(r for r in single if (r["scenario"], r["type"]) == t))) for t in types}
        held = [t for t in types if cat[t] == "heldout"]
        a = {"types": len(types), "composites_single": len(single)}
        a["mean_event_detection_single"], a["ci_event_detection_single"] = boot_mean_over_types(single, lambda r: r["detected"], types)
        a["mean_tick_detection_single"], _ = boot_mean_over_types(single, lambda r: r["tick_detected"], types, nb=1)
        a["held_out_types"] = len(held)
        a["mean_event_detection_heldout"], a["ci_event_detection_heldout"] = boot_mean_over_types(single, lambda r: r["detected"], held) if held else (None, None)
        det = [r for r in single if r["detected"]]
        bl = Counter(r["blame"] for r in det)
        a["blame_single_pooled"] = {k: float(bl.get(k, 0) / max(len(det), 1)) for k in ("correct", "wrong", "undecided")} | {"n_detected": len(det)}
        a["by_attacked_domain"] = {}
        for dk in ("gps", "cross", "lidar", "can", "v2x", "network"):
            ts = [t for t in types if attacked_key(next(r for r in single if (r["scenario"], r["type"]) == t)) == dk]
            if ts:
                a["by_attacked_domain"][dk] = {"types": len(ts), "event_detection": boot_mean_over_types(single, lambda r: r["detected"], ts, nb=1)[0],
                                               "delay_tick_median": median_iqr([r["delay"] for r in single if (r["scenario"], r["type"]) in ts and r["detected"]]),
                                               "delay_available_median": median_iqr([r["delay_available"] for r in single if (r["scenario"], r["type"]) in ts and r["detected"]])}
        # coordinated / multi-domain
        multi = [r for r in recs if r["scenario"].startswith("multi") or r["type"] in COORD[fam]]
        a["coordinated"] = {}
        for (scen, t), rs in groupby(multi, lambda r: (r["scenario"], r["type"].split("+")[0] if r["scenario"].startswith("multi") else r["type"])).items():
            dd = [r for r in rs if r["detected"]]
            a["coordinated"][f"{scen}|{t}"] = {"n": len(rs), "event_detection": float(np.mean([r["detected"] for r in rs])), "delay_tick": median_iqr([r["delay"] for r in dd]),
                                                "blame": dict(Counter(r["blame"] for r in dd)), "response_max": dict(Counter(r.get("response_max") for r in dd)),
                                                "response_max_variant": dict(Counter(r.get("response_max_variant") for r in dd))}
        a["response_max_single"] = {k: float(sum(r.get("response_max") == k for r in det) / max(len(det), 1)) for k in LEVELS[1:]}
        a["response_max_single_variant"] = {k: float(sum(r.get("response_max_variant") == k for r in det) / max(len(det), 1)) for k in LEVELS[1:]}
        a["events_explained"] = {"with": int(sum(r["explained"] for r in recs)), "events": int(sum(r["events"] for r in recs))}
        agg[fam] = a
    res["aggregate"] = agg
    # ------------------------------------------------------------- clean timelines
    clean = {}
    for fam in ("K", "C"):
        cs = [r for r in cln if r["family"] == fam]
        hours = np.array([r["hours"] for r in cs])
        n = np.array([r["n"] for r in cs])
        d = {"timelines": len(cs), "hours": float(hours.sum()), "ticks": int(n.sum())}
        d["fa_tick"], d["fa_tick_ci"] = ratio_ci([r["alarm_ticks"] for r in cs], n)
        d["events_per_hour"], d["events_per_hour_ci"] = ratio_ci([r["events"] for r in cs], hours)
        for lv in LEVELS[1:]:
            d[f"{lv}_per_hour"], d[f"{lv}_per_hour_ci"] = ratio_ci([r["levels"][lv] for r in cs], hours)
        d["SAFE_STOP_variant_per_hour"], d["SAFE_STOP_variant_per_hour_ci"] = ratio_ci([r["safe_stop_variant"] for r in cs], hours)
        d["events_total"] = int(sum(r["events"] for r in cs))
        d["explained"] = {"with": int(sum(r["explained"] for r in cs)), "events": d["events_total"]}
        dom = Counter()
        blamed = Counter()
        ss_dom = Counter()
        for r in cs:
            for doms, bl, lv in zip(r["event_domains"], r["event_blamed"], [None] * len(r["event_blamed"])):
                dom.update(doms)
                blamed[bl] += 1
        d["clean_event_domains"] = dict(dom)
        d["clean_event_blamed"] = dict(blamed)
        d["own_alarm_share_weighted"] = {k: float(sum(r["own_alarm_share"][k] * r["n"] for r in cs) / n.sum()) for k in cs[0]["own_alarm_share"]}
        d["per_timeline"] = [{"group": r["group"], "hours": r["hours"], "events": r["events"], "alarm_ticks": r["alarm_ticks"], "levels": r["levels"]} for r in cs]
        d["step_ms_median"] = float(np.median([r["step_ms_median"] for r in cs]))
        clean[fam] = d
    res["clean"] = clean
    # ------------------------------------------------------------- timing from the pass logs
    res["timing"] = timing()
    # ------------------------------------------------------------- v2 side by side
    res["v2_side_by_side"] = v2_side(agg, clean, att)
    # ------------------------------------------------------------- coverage (A2)
    res["coverage"] = coverage(att)
    # ------------------------------------------------------------- live check
    live = OUT / "S2_live.json"
    res["live"] = json.loads(live.read_text()) if live.exists() else None
    (OUT / "S2_results.json").write_text(json.dumps(res, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else list(o) if isinstance(o, (set, tuple)) else str(o)))
    acceptance(res)
    tables(res)
    print("written")


def lat_stats(ns):
    ms = np.asarray(ns, float) / 1e6
    return {"n": int(len(ms)), "median_ms": float(np.median(ms)), "p95_ms": float(np.percentile(ms, 95)), "p99_ms": float(np.percentile(ms, 99)), "max_ms": float(ms.max()), "total_s": float(ms.sum() / 1e3)}


def timing():
    out = {}
    vk = L.load_pickle("S2_veh_K.pkl")["latency"]
    vc = L.load_pickle("S2_veh_C.pkl")["latency"]
    for d, per in (("gps", 1.0), ("cross_kitti", 1.0)):
        lg = vk["gps" if d == "gps" else "cross"]
        ns = np.array(lg["ns"])
        out[d] = {"period_s": per, **lat_stats(ns), "stream_s": float(len(ns)), "ratio_compute_per_stream_s": float(ns.sum() / 1e9 / len(ns) / per)}
    ns = np.array(vc["ns"])
    out["cross_comma_residual"] = {"period_s": 1.0, **lat_stats(ns), "stream_s": float(len(ns)), "ratio_compute_per_stream_s": float(ns.sum() / 1e9 / len(ns))}
    # CAN
    ns_f, ns_w, stream_s = [], [], 0.0
    sz_w = []
    for f in ("S2_can_attack.pkl", "S2_can_ambient.pkl"):
        p = L.load_pickle(f)
        for name, lg in p["latency"].items():
            ns, em, sz = np.array(lg["ns"]), np.array(lg["emit"]), np.array(lg["size"])
            ns_f += list(ns[em == 0])
            ns_w += list(ns[em > 0])
            sz_w += list(sz[em > 0])
        stream_s += sum(len(s["score"]) for s in p["series"])
    out["can_frame"] = {"period_s": 0.001, **lat_stats(ns_f), "stream_s": stream_s, "ratio_compute_per_stream_s": float((np.sum(ns_f) + np.sum(ns_w)) / 1e9 / stream_s)}
    out["can_window"] = {"period_s": 1.0, **lat_stats(ns_w), "stream_s": stream_s}
    sz_w, nw = np.array(sz_w, float), np.array(ns_w, float) / 1e6
    out["can_window_by_context_frames"] = {f"{lo:.0f}-{hi:.0f}": {"n": int(((sz_w >= lo) & (sz_w < hi)).sum()), "median_ms": float(np.median(nw[(sz_w >= lo) & (sz_w < hi)])),
                                                                "p99_ms": float(np.percentile(nw[(sz_w >= lo) & (sz_w < hi)], 99))}
                                           for lo, hi in ((0, 1e5), (1e5, 3e5), (3e5, 6e5), (6e5, 2e6)) if ((sz_w >= lo) & (sz_w < hi)).any()}
    # V2X
    parts = [L.load_pickle(f.name) for f in sorted(L.CACHE.glob("S2_v2x_p*.pkl"))]
    v = {"latency": {"ns": [x for p in parts for x in p["latency"]["ns"]]}, "blocks": {k: b for p in parts for k, b in p["blocks"].items()}}
    ns = np.array(v["latency"]["ns"])
    span = sum(b["t1"] - b["t0"] for b in v["blocks"].values())
    out["v2x_message"] = {"period_s": float(span / max(len(ns), 1)), **lat_stats(ns), "stream_s": float(span), "messages": int(len(ns)), "ratio_compute_per_stream_s": float(ns.sum() / 1e9 / span),
                          "blocks": {k: {"messages": b["n"], "span_s": b["t1"] - b["t0"]} for k, b in v["blocks"].items()}}
    # network
    ns_all, ns_bin, span, flows = [], [], 0.0, 0
    for f in sorted(L.CACHE.glob("S2_net_p*.pkl")):
        p = L.load_pickle(f.name)
        for b, lg in p["latency"].items():
            ns, em = np.array(lg["ns"]), np.array(lg["emit"])
            ns_all += list(ns[em == 0])
            ns_bin += list(ns[em > 0])
            span += p["blocks"][b]["span_s"]
            flows += p["blocks"][b]["flows"]
    out["network_flow_push"] = {"period_s": 0.001, **lat_stats(ns_all), "stream_s": float(span), "flows": int(flows), "ratio_compute_per_stream_s": float((np.sum(ns_all) + np.sum(ns_bin)) / 1e9 / span)}
    out["network_bin_close"] = {"period_s": 300.0, **lat_stats(ns_bin)}
    ev_delay = []
    for f in sorted(L.CACHE.glob("S2_net_p*.pkl")):
        for s in L.load_pickle(f.name)["series"]:
            pres = s["count"] > 0
            ev_delay += list((s["avail"] - np.arange(len(s["avail"])) - 1.0)[pres])
    out["network_evidence_delay_s"] = {"median": float(np.median(ev_delay)), "p95": float(np.percentile(ev_delay, 95)), "max": float(np.max(ev_delay)), "n_ticks": len(ev_delay)}
    # LiDAR
    ns_l, scans = [], 0
    for f in sorted(L.LIDAR_DIR.glob("clean_*.pkl")):
        r = L.pickle.load(open(f, "rb"))
        ns_l += [x["ns"] for x in r["rows"]]
        scans += len(r["rows"])
    ns_all_l = list(ns_l)
    for f in sorted(L.LIDAR_DIR.glob("scan_*.pkl")):
        ns_all_l += [x["ns"] for x in L.pickle.load(open(f, "rb"))["rows"]]
    for f in sorted(L.LIDAR_DIR.glob("ep_*.pkl")):
        for e in L.pickle.load(open(f, "rb"))["episodes"]:
            ns_all_l += [x["ns"] for x in e["rows"]]
    out["lidar_scan"] = {"period_s": 0.1032, **lat_stats(ns_all_l), "scans": int(len(ns_all_l)), "clean_pass_scans": scans,
                         "ratio_compute_per_stream_s": float(np.median(ns_all_l) / 1e9 / 0.1032), "cores_needed_for_real_time_median": float(np.median(ns_all_l) / 1e9 / 0.1032)}
    for k, t in out.items():
        if isinstance(t, dict) and "p99_ms" in t and "period_s" in t:
            t["keeps_up_p99_per_sample"] = bool(t["p99_ms"] / 1000.0 < t["period_s"])
            if "ratio_compute_per_stream_s" in t:
                t["keeps_up_amortised"] = bool(t["ratio_compute_per_stream_s"] <= 1.0)
    return out


def v2_side(agg, clean, att):
    """v2 live simulation (codes_v2/RESULTS_v2.md, 7,800 rows, 13 alternating blocks, strategy meta) next to the v3 analogue of every block. NOT like-for-like (stated in the report)."""
    K = [r for r in att if r["family"] == "K"]

    def blk(pred, name):
        rs = [r for r in K if pred(r)]
        if not rs:
            return None
        det = [r for r in rs if r["detected"]]
        lab_t = sum(r["label_ticks_n"] for r in rs)
        return {"v3_block": name, "composites": len(rs), "event_detection": float(np.mean([r["detected"] for r in rs])), "tick_flagged_share": float(sum(r["alarm_in_label"] for r in rs) / max(lab_t, 1)),
                "median_first_alarm_delay_s": median_iqr([r["delay"] for r in det]), "median_available_delay_s": median_iqr([r["delay_available"] for r in det])}

    sim = json.loads((L.ROOT.parent / "codes_v2" / "results" / "simulation.json").read_text())      # read-only reference
    wc = sim["with_correlator"]
    normal = [v for k, v in sim["per_block"].items() if "Normal" in k]
    v2 = {"overall": {"accuracy": wc["accuracy"], "precision": wc["precision"], "recall": wc["recall"], "f1": wc["f1"], "false_alarm_rate": wc["fpr"], "rows": sim["rows"], "normal_rows": sim["normal_rows"],
                      "attack_rows": sim["attack_rows"], "source": "codes_v2/results/simulation.json (live simulation, strategy meta, with correlator)"},
          "blocks": {k: {"flagged": sim["per_block"][k], "first_alert_rows": sim["first_alert_delay_rows"][k]} for k in sim["first_alert_delay_rows"]},
          "normal_blocks_flagged_range": [float(min(normal)), float(max(normal))]}
    v3 = {"02 GPS spoofing": blk(lambda r: r["scenario"] == "vehicle" and r["type"] in GPS_FAMS, "GPS drift / accel_drift / doppler_spoof / meaconing"),
          "04 CAN DoS": blk(lambda r: r["scenario"] == "can_episode" and r["type"] == "fuzzing", "ROAD fuzzing (injection flood)"),
          "06 Network DoS": blk(lambda r: r["scenario"] == "network_block" and (r["type"].startswith("DoS") or r["type"].startswith("DDoS")), "D10 DoS / DDoS families"),
          "08 LiDAR phantom object (per scan)": blk(lambda r: r["scenario"] == "lidar_scan" and r["type"].startswith("ph_"), "single-return phantoms, 4 kinds"),
          "08 LiDAR phantom object (persistent episode)": blk(lambda r: r["scenario"] == "lidar_episode", "30-scan persistent phantoms, sensor- and world-fixed"),
          "10 CAN + GPS spoofing": blk(lambda r: r["scenario"] == "multi_can_gps", "ROAD CAN attack + KITTI GPS attack, same car"),
          "12 CAN spoof + LiDAR blind spot": blk(lambda r: r["scenario"] == "multi_can_lidar", "ROAD CAN attack + PointDrop (blind sector)"),
          "normal blocks": {"clean_tick_FA_K": clean["K"]["fa_tick"], "events_per_clean_hour_K": clean["K"]["events_per_hour"], "SAFE_STOP_per_clean_hour_K": clean["K"]["SAFE_STOP_per_hour"]}}
    return {"v2": v2, "v3": v3, "caveat": "NOT like-for-like: v2 rows are single samples scored by a supervised meta-classifier on attack classes seen in training, long attack blocks, random halves; its LiDAR phantom/box-cloud "
                                          "attacks add a multi-return cloud that a single-return sensor cannot produce; v3 composites are drives with persistent attacks from tick 3, label-free fusion, a correlator, events per hour."}


def coverage(att):
    """Expected number of composites per (family, scenario, type), recomputed from the SOURCES (not from the composites), versus the composites built."""
    import WP7_S2_sim as M
    import WP7_S2_sim_main as MM
    S = M.Sources()
    got = Counter((r["family"], r["scenario"], r["type"]) for r in att)
    exp = Counter()
    for k in S.veh_K["series"]:
        if k[2] != "none":
            exp[("K", "vehicle", k[2])] += 1
    for k in S.veh_C["series"]:
        if k[2] != "none":
            exp[("C", "vehicle", k[2])] += 1
    for (d, kind) in S.lidar["scan"]:
        exp[("K", "lidar_scan", kind)] += 1
    for (d, mode), job in S.lidar["ep"].items():
        for e in job["episodes"]:
            exp[("K", "lidar_episode", e["kind"])] += 1
    can_att = [s for s in S.can if s["kind"] == "attack"]
    n_can = 0
    for fam in ("K", "C"):
        for s in can_att:
            for _ in MM.runs_of(s["label"]):
                exp[(fam, "can_episode", s["family"])] += 1
                n_can += 1 if fam == "K" else 0
    for s in can_att:
        for _ in MM.runs_of(s["label"]):
            exp[("K", "multi_can_gps", None)] += 0
    for fam in ("K", "C"):
        for s in [x for x in S.v2x if x["kind"] == "attack"]:
            for f in sorted(set(x for x in s["fam"] if x)):
                for _ in MM.runs_of(np.asarray(s["fam"], object) == f):
                    exp[(fam, "v2x_episode", f)] += 1
    skipped_net = 0
    for fam in ("K", "C"):
        for s in [x for x in S.net if x["kind"] == "attack"]:
            fam_t, lab = np.asarray(s["fam"], object), np.asarray(s["label"], bool)
            runs = []
            for f in sorted(set(x for x in fam_t[lab])):
                runs += [(f, int(a), int(z)) for a, z in MM.runs_of(lab & (fam_t == f))]
            runs.sort(key=lambda r: r[1])
            for i, (f, a, z) in enumerate(runs):
                j0 = max(max(a - 60, 0) - L.ONSET, 0)
                nxt = runs[i + 1][1] - 60 if i + 1 < len(runs) else len(lab)
                n = min(z + 361, len(lab), nxt) - j0
                if n < 120:
                    skipped_net += 1
                    continue
                exp[(fam, "network_block", f)] += 1
    for (fam, scen, t), v in list(exp.items()):
        if scen == "multi_can_gps" and t is None:
            del exp[(fam, scen, t)]
    multi = sum(1 for r in att if r["scenario"] == "multi_can_gps"), sum(1 for r in att if r["scenario"] == "multi_can_lidar")
    diff = {"|".join(map(str, k)): [exp.get(k, 0), got.get(k, 0)] for k in set(exp) | {k for k in got if not k[1].startswith("multi")} if exp.get(k, 0) != got.get(k, 0)}
    return {"composites_by_type": {"|".join(map(str, k)): v for k, v in sorted(got.items(), key=str)}, "expected_by_type": {"|".join(map(str, k)): v for k, v in sorted(exp.items(), key=str)},
            "multi_domain_composites": {"can_plus_gps": multi[0], "can_plus_lidar": multi[1], "expected_each": n_can}, "network_windows_skipped_shorter_than_120_s": skipped_net,
            "differences_expected_vs_built": diff, "complete": bool(not diff and multi[0] == n_can and multi[1] == n_can), "vehicle_complete": bool(all(got.get(k, 0) == v for k, v in exp.items() if k[1] == "vehicle"))}


def acceptance(res):
    A = {}
    a1 = res["A1"]
    A["A1_stream_integrity"] = {"rule": "FusionRunner final alarms and events (start, end, blamed, response, explanation) equal SystemV2.run on the same per-domain arrays for every attack composite and every clean timeline (0 mismatches)",
                                "met": a1["mismatches"] == 0, "composites": a1["attack_composites"], "clean_timelines": a1["clean_timelines"], "mismatches": a1["mismatches"]}
    cov = res["coverage"]
    A["A2_coverage"] = {"rule": "every test episode enumerated from the SOURCES (70 per KITTI vehicle type, 32 per comma type, 7 per LiDAR per-scan kind, 21 per LiDAR episode kind, every CAN / V2X / network attack run) is a composite; no difference between expected and built counts", "met": bool(cov["complete"]),
                        "types": len(cov["composites_by_type"]), "composites": int(sum(cov["composites_by_type"].values())), "differences": len(cov["differences_expected_vs_built"])}
    live = res.get("live")
    A["A3_live_cosimulation"] = {"rule": "at least 6 composites driven fully live through the runners and the bus equal the replay from the stored domain passes (0 mismatches)",
                                 "met": bool(live and live.get("n", 0) >= 6 and live.get("mismatches", 1) == 0), "composites": 0 if not live else live.get("n", 0), "mismatches": None if not live else live.get("mismatches")}
    t = res["timing"]
    ok_t = all(k in t for k in ("gps", "cross_kitti", "can_frame", "v2x_message", "network_flow_push", "lidar_scan"))
    A["A4_timing"] = {"rule": "per-domain compute latency (median, p95, p99), Evidence delay, real-time ratio and a keeps-up statement, all from measured passes", "met": bool(ok_t),
                      "lidar_median_ms": t["lidar_scan"]["median_ms"], "lidar_ratio": t["lidar_scan"]["ratio_compute_per_stream_s"], "network_evidence_delay_median_s": t["network_evidence_delay_s"]["median"],
                      "network_evidence_delay_max_s": t["network_evidence_delay_s"]["max"]}
    A["A5_completeness"] = {"rule": "every reported item exists in S2_results.json (by type, by domain, blame, response, clean hours with CI, timing, v2 side by side)", "met": all(k in res for k in ("by_type", "aggregate", "clean", "timing", "v2_side_by_side")),
                            "types_K": len(res["by_type"]["K"]), "types_C": len(res["by_type"]["C"])}
    K, C = res["aggregate"]["K"], res["aggregate"]["C"]
    cK, cC = res["clean"]["K"], res["clean"]["C"]
    A["B1_clean_tick_fa"] = {"rule": "clean raw tick FA <= 3.0% (K and C)", "met": bool(cK["fa_tick"] <= 0.03 and cC["fa_tick"] <= 0.03), "K": cK["fa_tick"], "C": cC["fa_tick"]}
    A["B2_events_per_clean_hour"] = {"rule": "alert events per clean hour <= 10 (K and C)", "met": bool(cK["events_per_hour"] <= 10 and cC["events_per_hour"] <= 10), "K": cK["events_per_hour"], "C": cC["events_per_hour"]}
    A["B3_event_detection_single"] = {"rule": "K mean event detection over the single-domain attack types >= 70%", "met": bool(K["mean_event_detection_single"] >= 0.7), "K": K["mean_event_detection_single"], "types": K["types"]}
    A["B4_heldout_types"] = {"rule": "K mean event detection over the S4 held-out types >= 60%", "met": bool(K["mean_event_detection_heldout"] is not None and K["mean_event_detection_heldout"] >= 0.6),
                            "K": K["mean_event_detection_heldout"], "types": K["held_out_types"]}
    b = K["blame_single_pooled"]
    A["B5_blame"] = {"rule": "K blame of detected single-domain events: correct >= 75% and wrong <= 10%", "met": bool(b["correct"] >= 0.75 and b["wrong"] <= 0.10), "correct": b["correct"], "wrong": b["wrong"], "undecided": b["undecided"]}
    A["B6_safe_stop_per_clean_hour"] = {"rule": "SAFE_STOP recommendations per clean hour <= 1 (K and C)", "met": bool(cK["SAFE_STOP_per_hour"] <= 1 and cC["SAFE_STOP_per_hour"] <= 1), "K": cK["SAFE_STOP_per_hour"], "C": cC["SAFE_STOP_per_hour"],
                                       "K_variant": cK["SAFE_STOP_variant_per_hour"], "C_variant": cC["SAFE_STOP_variant_per_hour"]}
    ex = [cK["explained"], cC["explained"], K["events_explained"], res["aggregate"]["C"]["events_explained"]]
    A["B7_explanations"] = {"rule": "100% of alert events carry the system's explanation", "met": all(e["with"] == e["events"] for e in ex), "events": int(sum(e["events"] for e in ex)), "explained": int(sum(e["with"] for e in ex))}
    A["M3_verdict"] = {"rule": "M3 = MET only if A1-A5 and B1-B7 all hold", "met": all(v["met"] for v in A.values()), "rows_met": int(sum(v["met"] for k, v in A.items() if k != "M3_verdict")), "rows": len(A)}
    (OUT / "S2_acceptance.json").write_text(json.dumps(A, indent=1, default=float))


def tables(res):
    lines = ["# WP7 S2 tables (generated by tools/WP7_S2_report.py from results/WP7/S2_results.json)", ""]
    f = lambda x, d=1: "-" if x is None else f"{100 * x:.{d}f}%"
    m = lambda s: "-" if s is None else f"{s['median']:.0f} [{s['q25']:.0f}, {s['q75']:.0f}]"
    for fam in ("K", "C"):
        lines += [f"## 1.{fam} Detection, first-alert delay, blame and response per attack type, family {fam}", "",
                  "| scenario | type | n | groups | event det. | tick det. | delay ticks (median [q25,q75]) | available delay s | blame c/w/u | worst response W/D/S | variant S | t DEGRADE s | t SAFE_STOP s |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for k, r in sorted(res["by_type"][fam].items()):
            b = r.get("blame")
            rm = r.get("response_max")
            rv = r.get("response_max_variant")
            lines.append(f"| {r['scenario']} | {r['type']} | {r['n']} | {r['groups']} | {f(r['event_detection'])} | {f(r['tick_detection'])} | {m(r['delay_tick'])} | {m(r['delay_available'])} | "
                         + (f"{f(b['correct'], 0)}/{f(b['wrong'], 0)}/{f(b['undecided'], 0)}" if b else "-") + " | "
                         + (f"{f(rm['WARN'], 0)}/{f(rm['DEGRADE'], 0)}/{f(rm['SAFE_STOP'], 0)}" if rm else "-") + " | " + (f(rv['SAFE_STOP'], 0) if rv else "-") + " | " + m(r.get("t_degrade")) + " | " + m(r.get("t_safe_stop")) + " |")
        lines.append("")
    lines += ["## 2 Clean timelines", "", "| family | timelines | hours | tick FA | events / h | WARN / h | DEGRADE / h | SAFE_STOP / h | SAFE_STOP / h (variant) |", "|---|---|---|---|---|---|---|---|---|"]
    for fam, d in res["clean"].items():
        ci = lambda k: f"{d[k]:.2f} [{d[k + '_ci'][0]:.2f}, {d[k + '_ci'][1]:.2f}]"
        lines.append(f"| {fam} | {d['timelines']} | {d['hours']:.2f} | {100 * d['fa_tick']:.2f}% [{100 * d['fa_tick_ci'][0]:.2f}, {100 * d['fa_tick_ci'][1]:.2f}] | {ci('events_per_hour')} | {ci('WARN_per_hour')} | {ci('DEGRADE_per_hour')} | "
                     f"{ci('SAFE_STOP_per_hour')} | {ci('SAFE_STOP_variant_per_hour')} |")
    lines += ["", "## 3 Timing (this machine, shared)", "", "| stream | period s | n | median ms | p95 ms | p99 ms | max ms | compute s per stream s |", "|---|---|---|---|---|---|---|---|"]
    for k, t in res["timing"].items():
        if isinstance(t, dict) and "median_ms" in t:
            lines.append(f"| {k} | {t['period_s']:.4g} | {t['n']} | {t['median_ms']:.3f} | {t['p95_ms']:.3f} | {t['p99_ms']:.3f} | {t['max_ms']:.1f} | {t.get('ratio_compute_per_stream_s', float('nan')):.4g} |")
    (OUT / "S2_tables.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
