"""make_report_v31.py (WP8 S7): builds the M4 verdict (results/WP8/S7/m4_verdict.json), reports/M4.md, reports/WP8_S7.md, RESULTS_v31.md and results/WP8/S7/exposure.json from the saved
S7 result files. Every number printed is read from a JSON file listed next to it; verdicts are computed from the pre-registered rules (notes/WP8_v31.md section 2 and "S7 protocol clarifications").
New script (the v3 make_report.py is untouched). Added after the freeze commit (hash in results/WP8/S7/freeze_addendum.json). Run: python -u -W ignore make_report_v31.py"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
S7 = ROOT / "results" / "WP8" / "S7"


def J(name, default=None):
    p = S7 / name
    return json.loads(p.read_text()) if p.exists() else default


def pct(x, d=1):
    return "n/a" if x is None else f"{100 * x:.{d}f} %"


def ci(c, d=1, scale=100):
    return "" if not c else f" [{scale * c[0]:.{d}f}, {scale * c[1]:.{d}f}]"


def row(label, rule, met, v31, v3, evid, exposure, extra=""):
    return {"row": label, "rule": rule, "verdict": "MET" if met is True else ("NOT MET" if met is False else "NOT EVALUATED"), "v31": v31, "v3": v3, "evidence": evid, "exposure": exposure, "note": extra}


def verdict():
    sysr, dom, bl, net, can, lc, v2a, reg, ver = (J("system_h31.json"), J("domains.json"), J("blame.json"), J("network.json"), J("can_summary.json"), J("lidar_check.json"), J("v2aix.json"),
                                                  J("regression.json"), J("h31_verify.json"))
    rows = []
    P = "partially fresh (vehicle block fresh; CAN / network / V2X streams re-used)"
    R31, R3, PD = sysr["runs"]["v31"], sysr["runs"]["v3"], sysr["paired_v31_minus_v3"]
    for fam, nm in (("K", "KITTI"), ("C", "comma RAV4")):
        a, b = R31[fam], R3[fam]
        pd_ = PD[fam]
        rows.append(row(f"M4-1 clean tick FA ({fam})", "<= 3.0 %", a["fa_tick"] <= 0.03, f"{pct(a['fa_tick'], 2)}{ci(a['fa_tick_ci'], 2)}", f"{pct(b['fa_tick'], 2)}{ci(b['fa_tick_ci'], 2)}",
                        "system_h31.json runs.v31/v3." + fam + ".fa_tick; paired " + f"{100 * pd_['fa_tick']['diff']:.2f} pts{ci(pd_['fa_tick']['ci'], 2)}", P))
        rows.append(row(f"M4-2 alert events per clean hour ({fam})", "<= 10", a["events_per_hour"] <= 10, f"{a['events_per_hour']:.2f}{ci(a['events_per_hour_ci'], 2, 1)}", f"{b['events_per_hour']:.2f}{ci(b['events_per_hour_ci'], 2, 1)}",
                        f"paired {pd_['events_per_hour']['diff']:.2f}/h{ci(pd_['events_per_hour']['ci'], 2, 1)}", P))
        rows.append(row(f"M4-3 SAFE_STOP per clean hour ({fam})", "<= 1", a["SAFE_STOP_per_hour"] <= 1, f"{a['SAFE_STOP_per_hour']:.2f}{ci(a['SAFE_STOP_per_hour_ci'], 2, 1)}", f"{b['SAFE_STOP_per_hour']:.2f}{ci(b['SAFE_STOP_per_hour_ci'], 2, 1)}",
                        f"paired {pd_['safe_stop_per_hour']['diff']:.2f}/h", P))
    a, b, pd_ = R31["K"], R3["K"], PD["K"]
    rows.append(row("M4-4 K mean event detection, single-domain types", ">= 70 %", a["det_single"] >= 0.70, f"{pct(a['det_single'])}{ci(a['det_single_ci'])}", f"{pct(b['det_single'])}{ci(b['det_single_ci'])}",
                    f"paired {100 * pd_['det_single']['diff']:.1f} pts{ci(pd_['det_single']['ci'])}", P))
    rows.append(row("M4-5 K held-out (zero-day) types", ">= 60 %", a["det_heldout"] >= 0.60, f"{pct(a['det_heldout'])}{ci(a['det_heldout_ci'])}", f"{pct(b['det_heldout'])}{ci(b['det_heldout_ci'])}",
                    f"paired {100 * pd_['det_heldout']['diff']:.1f} pts{ci(pd_['det_heldout']['ci'])}", P))
    rows.append(row("M4-6 blame equal weight per type (K): correct / wrong", ">= 75 % / <= 10 %", a["blame_correct"] >= 0.75 and a["blame_wrong"] <= 0.10,
                    f"{pct(a['blame_correct'])} / {pct(a['blame_wrong'])}", f"{pct(b['blame_correct'])} / {pct(b['blame_wrong'])}",
                    f"paired correct {100 * pd_['blame_correct']['diff']:.1f}{ci(pd_['blame_correct']['ci'])}, wrong {100 * pd_['blame_wrong']['diff']:.1f}{ci(pd_['blame_wrong']['ci'])}", P,
                    f"C: {pct(R31['C']['blame_correct'])} / {pct(R31['C']['blame_wrong'])} (v3 {pct(R3['C']['blame_correct'])} / {pct(R3['C']['blame_wrong'])})"))
    ex = all(x[0] == x[1] for fam in "KC" for x in (R31[fam]["clean_events_explained"], R31[fam]["attack_events_explained"]))
    rows.append(row("M4-7 events explained", "100 %", ex, " / ".join(f"{R31[f]['clean_events_explained'][0]}/{R31[f]['clean_events_explained'][1]} clean, {R31[f]['attack_events_explained'][0]}/{R31[f]['attack_events_explained'][1]} attack ({f})" for f in "KC"),
                    "", "system_h31.json", P))
    # M4-8 LiDAR
    lid = dom["lidar"]
    pr = {r["subset"]: r for r in lid["rows"]}
    pdr = lid["paired_scan_level_v31_minus_v3"]["PointDrop"]
    fa31 = lid["clean"]["v31_fa"]
    sp = (lc or {}).get("speed_run1_loaded", (lc or {}).get("speed", {}))
    sp2 = (lc or {}).get("speed", {}) if "speed_run1_loaded" in (lc or {}) else {}
    bt =R31["K"]["by_type"]
    pd_scan, pd_ep = bt.get("lidar_scan|PointDrop", {}).get("event_detection"), bt.get("lidar_episode|ep_PointDrop", {}).get("event_detection")
    c = {"speed": bool(sp.get("met")), "stream_eq_batch": bool(sp and sp["stream_equals_batch"]["mismatches"] == 0), "pointdrop_scan": pdr["v31"] >= 0.65, "scan_fa": fa31 <= 0.015,
         "in_system": bool(pd_scan is not None and pd_ep is not None and pd_scan >= 0.6 and pd_ep >= 0.6)}
    rows.append(row("M4-8 LiDAR", "median <= 0.10 s/scan, stream == batch, PointDrop per scan >= 65 %, scan FA <= 1.5 %, in-system PointDrop events >= 60 % (both scenarios)", all(c.values()),
                    f"median {sp.get('median_ms', float('nan')):.0f} ms, p99 {sp.get('p99_ms', float('nan')):.0f} ms (repeat: {sp2.get('median_ms', float('nan')):.0f} / {sp2.get('p99_ms', float('nan')):.0f} ms); PointDrop {pct(pdr['v31'])}; FA {pct(fa31, 2)}; in-system per-scan {pct(pd_scan)} / episodes {pct(pd_ep)}",
                    f"v3 PointDrop {pct(pdr['v3'])}; FA {pct(lid['clean']['v3_fa'], 2)}; in-system {pct(R3['K']['by_type'].get('lidar_scan|PointDrop', {}).get('event_detection'))} / {pct(R3['K']['by_type'].get('lidar_episode|ep_PointDrop', {}).get('event_detection'))}",
                    "lidar_check.json, domains.json lidar, system_h31.json; components: " + json.dumps(c), "fresh H31"))
    # M4-9 network
    cn = net["candidates"]
    d1 = cn["F1"]["delay_flow_level"]["all_flows"]
    pv = cn["F1"]["paired_vs_v3"]
    c9 = {"d10_delay": d1["median_s"] <= 60 and d1["max_s"] <= 120, "macro": pv["macro_diff_points"] >= -3.0, "d23": None}
    rows.append(row("M4-9 network", "D10 delay median <= 60 s, max <= 120 s (amended); D23 <= 15 / 45 s; stack H macro >= v3 - 3 pts (paired)", None if c9["d23"] is None else all(c9.values()),
                    f"F1 delay median {d1['median_s']:.0f} s / max {d1['max_s']:.0f} s; macro {pct(cn['F1']['macro'])} ({pv['macro_diff_points']:+.2f} pts{ci(pv['macro_diff_ci'], 2, 1)}); FA {pct(cn['F1']['fa'], 2)}",
                    f"v3 delay median {cn['v3']['delay_flow_level']['all_flows']['median_s']:.0f} s / max {cn['v3']['delay_flow_level']['all_flows']['max_s']:.0f} s; macro {pct(cn['v3']['macro'])}; FA {pct(cn['v3']['fa'], 2)}",
                    "network.json; D10 half: " + ("met" if c9["d10_delay"] and c9["macro"] else "not met") + "; D23 half NOT evaluated (no D23 cache; F1 tick 60 s)", "re-used (D10 test, exposure n+1)",
                    f"RC5 variant: macro {pct(cn['RC5']['macro'])} ({cn['RC5']['paired_vs_v3']['macro_diff_points']:+.2f} pts), delay 0 s"))
    # M4-10 CAN
    p99 = [r["window_ms"]["p99"] for r in can]
    mism = sum(r["alarm_mismatch"] + r["id_mismatch"] + r["reason_mismatch"] + r["motion_mismatch"] for r in can)
    gro = [r["growth"]["ratio"] for r in can if "growth" in r]
    idle = J("can_idle_timing.json")
    p99_idle = [r["p99_ms"] for r in idle] if idle else None
    use = p99                      # judged on the first (loaded) run, decision journalled before the idle re-run
    ok = max(use) <= 150 and mism == 0 and (not gro or max(gro) <= 1.5)
    rows.append(row("M4-10 CAN", "p99 window <= 0.15 s on every capture, growth ratio <= 1.5, Evidence == v3 batch", ok,
                    f"mismatches {mism}; p99 max {max(p99):.0f} ms (loaded run, 5 processes)" + (f"; repeat (up to 7 other python processes) p99 max {max(p99_idle):.0f} ms" if p99_idle else "") + f"; growth ratio max {max(gro):.2f}" if gro else "",
                    "same frozen object (v3 batch scoring is the reference)", "can_summary.json" + (", can_idle_timing.json" if idle else ""), "re-used (ROAD test)",
                    "growth ratio measurable only on captures with windows before 100k and after 600k frames"))
    # M4-11 V2X V2AIX
    if v2a:
        rt = v2a["runtime"]
        fa_m = v2a["envs"]["Mobile"]["false_alarms"]["physics"]["per_message"]
        fa_s = v2a["envs"]["Stationary"]["false_alarms"]["physics"]["per_message"]
        c11 = {"compute": rt["compute_per_stream_s_max"] <= 0.5, "fa": max(fa_m, fa_s) <= 0.015, "injected": rt["mismatch_rows_unexplained"] == 0}
        rows.append(row("M4-11 V2X (V2AIX)", "compute <= 0.5 s per stream s; genuine FA <= 1.5 % per message (V31_val thresholds); injected mean >= v3 - 3 pts", all(c11.values()),
                        f"compute max {rt['compute_per_stream_s_max']:.3f} s/s on {rt['egos']} Mobile egos; FA Mobile {pct(fa_m, 2)}, Stationary {pct(fa_s, 2)}; injected mean Mobile {pct(v2a['envs']['Mobile']['injected_mean_over_types'])}, Stationary {pct(v2a['envs']['Stationary']['injected_mean_over_types'])}",
                        "v3 batch = same frozen object; stream rows differing from the batch: " + f"{rt['mismatch_rows_total']} of {rt['messages_total']} (unexplained {rt['mismatch_rows_unexplained']})", "v2aix.json; " + json.dumps(c11),
                        "fresh H31 (same site-day as calibration for 672 / 674)"))
    else:
        rows.append(row("M4-11 V2X (V2AIX)", "see rule", None, "", "", "v2aix.json missing", ""))
    # M4-12 / 13
    g = bl["K"]["A1"]["gps_can"]
    g3 = bl["K"]["V3"]["gps_can"]
    rows.append(row("M4-12 KITTI gps_can blame", "wrong <= 25 %, correct >= 40 %", g["wrong"] <= 0.25 and g["correct"] >= 0.40, f"A1 correct {pct(g['correct'])} / wrong {pct(g['wrong'])} (detected {g['detected']}/{g['runs']})",
                    f"v3 correct {pct(g3['correct'])} / wrong {pct(g3['wrong'])}", "blame.json K.A1/V3.gps_can; A3 variant " + f"{pct(bl['K']['A3']['gps_can']['correct'])} / {pct(bl['K']['A3']['gps_can']['wrong'])}", "fresh H31"))
    b2 = bl["C"]["A1"]["B2"]
    b23 = bl["C"]["V3"]["B2"]
    rows.append(row("M4-13 comma GNSS spoof blame", "correct >= 60 %, wrong <= 15 %", b2["correct"] >= 0.60 and b2["wrong"] <= 0.15, f"A1 correct {pct(b2['correct'])} / wrong {pct(b2['wrong'])}", f"v3 correct {pct(b23['correct'])} / wrong {pct(b23['wrong'])}",
                    "blame.json C.A1/V3.B2", "fresh H31"))
    rows.append(row("M4-14 regression R2 before H31", "all checks pass; H31 sha256 verified", bool(reg and reg.get("all_pass") and ver and ver.get("all_ok")), f"regression.json all_pass={reg.get('all_pass')}; h31_verify.json all_ok={ver.get('all_ok')}", "", "", "-"))
    npz = len(list((ROOT / "results" / "WP8" / "scores" / "S7").glob("*.npz")))
    curves = len(list((S7 / "curves").glob("*_roc.png")))
    rows.append(row("M4-15 scores saved, curves + AUC", "per-sample scores saved; curves / AUC with group-bootstrap CI for GPS, CAN, LiDAR, network, V2X, cross, system", npz >= 20 and curves >= 8, f"{npz} score files, {curves} curve figures", "", "results/WP8/scores/S7, results/WP8/S7/curves", "-"))
    met = [r for r in rows if r["verdict"] == "MET"]
    return {"rows": rows, "n_rows": len(rows), "n_met": len(met), "m4": "MET" if len(met) == len(rows) else "NOT MET"}


def improvement(V):
    """G4 per row: fresh H31, bound met, paired CI excludes 0 in the good direction."""
    out = []
    sysr = J("system_h31.json")
    PD = sysr["paired_v31_minus_v3"]
    good = {"fa_tick": -1, "events_per_hour": -1, "safe_stop_per_hour": -1, "det_single": 1, "det_heldout": 1, "blame_correct": 1, "blame_wrong": -1}
    for fam in "KC":
        for k, s in good.items():
            p = PD[fam].get(k)
            if not p or "ci" not in p:
                continue
            lo, hi = p["ci"]
            exc = (lo > 0 and s > 0) or (hi < 0 and s < 0)
            bad = (hi < 0 and s > 0) or (lo > 0 and s < 0)
            out.append({"family": fam, "metric": k, "diff": p["diff"], "ci": p["ci"], "ci_excludes_0_good_direction": bool(exc), "ci_excludes_0_bad_direction": bool(bad), "material": "partially fresh", "claim": "paired CI excludes 0 (partially fresh material)" if exc else "no claim"})
    return out


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows]
    return "\n".join(out)


def system_tables():
    sysr = J("system_h31.json")
    out = []
    for fam, nm in (("K", "K = KITTI H31 (13 drives)"), ("C", "C = comma RAV4 Chunk_2 (21 routes)")):
        comp = sysr["composites"][fam]
        out.append(f"### {nm}: {comp['attack']} attack composites, {comp['clean_timelines']} clean timelines ({comp['clean_hours']:.2f} h), {comp['single_types']} single-domain types ({comp['held_out_types']} held out)\n")
        names = [("v3", "v3 frozen"), ("v31", "v3.1 primary"), ("v31_RC5", "v3.1 + network RC5"), ("v31_blameA3", "v3.1 + blame A3"), ("v31_b15", "v3.1 + budget 1.5 %"), ("v31_mcSS", "v3.1 + motion-critical SAFE_STOP")]
        names = [(k, n) for k, n in names if k in sysr["runs"]]
        hdr = ["metric (95 % CI)"] + [n for _, n in names]
        cells = []
        for lab, key, f in (("clean tick FA", "fa_tick", lambda r: pct(r["fa_tick"], 2) + ci(r["fa_tick_ci"], 2)), ("alert events / clean hour", "events", lambda r: f"{r['events_per_hour']:.2f}" + ci(r["events_per_hour_ci"], 2, 1)),
                            ("SAFE_STOP / clean hour", "ss", lambda r: f"{r['SAFE_STOP_per_hour']:.2f}"), ("DEGRADE / clean hour", "dg", lambda r: f"{r['DEGRADE_per_hour']:.2f}"),
                            ("mean event detection, single-domain types", "det", lambda r: pct(r["det_single"]) + ci(r["det_single_ci"])), ("held-out types", "held", lambda r: pct(r["det_heldout"]) + ci(r["det_heldout_ci"])),
                            ("blame correct / wrong", "bl", lambda r: f"{pct(r['blame_correct'])} / {pct(r['blame_wrong'])}"), ("time-to-visible, persistent types (median s)", "ttv", lambda r: str(r["ttv_persistent_median"])),
                            ("threshold", "thr", lambda r: f"{r['threshold']:.5f}")):
            cells.append([lab] + [f(sysr["runs"][k][fam]) for k, _ in names])
        out.append(md_table(hdr, cells))
        out.append("\nBy attacked domain (event detection of single-domain types; median seconds to visible alarm):\n")
        doms = sorted(sysr["runs"]["v31"][fam]["by_attacked_domain"])
        out.append(md_table(["domain"] + [n for _, n in names[:2]] + ["paired v3.1 - v3 (pts) [95 % CI]"],
                            [[d] + [f"{pct(sysr['runs'][k][fam]['by_attacked_domain'][d]['event_detection'])} ({sysr['runs'][k][fam]['by_attacked_domain'][d]['delay_available_median']} s)" for k, _ in names[:2]] +
                             [(f"{100 * sysr['paired_v31_minus_v3'][fam]['by_attacked_domain'][d]['diff']:+.1f}" + ci(sysr['paired_v31_minus_v3'][fam]['by_attacked_domain'][d]['ci'])) if sysr['paired_v31_minus_v3'][fam]['by_attacked_domain'].get(d) else ""] for d in doms]))
        pv = sysr["paired_v31_minus_v3"][fam]
        out.append("\nPaired v3.1 - v3 (same composites; group bootstrap B = 2000, seed 31): " + "; ".join(
            f"{k} {100 * pv[k]['diff']:+.2f}{' pts' if k not in ('events_per_hour', 'safe_stop_per_hour') else '/h'}{ci(pv[k].get('ci'), 2, 100 if k not in ('events_per_hour', 'safe_stop_per_hour') else 1)}" for k in ("fa_tick", "events_per_hour", "det_single", "det_heldout", "blame_correct", "blame_wrong") if pv.get(k)) + "\n")
    return "\n".join(out)


def main():
    V = verdict()
    V["improvement_G4"] = improvement(V)
    (S7 / "m4_verdict.json").write_text(json.dumps(V, indent=1, default=float))
    import make_report_v31_docs as D
    D.write_exposure()
    D.write_docs(V, V["improvement_G4"])
    print(V["n_met"], "of", V["n_rows"], "rows MET ->", V["m4"])
    for r in V["rows"]:
        print(r["verdict"], "|", r["row"], "|", r["v31"][:110])


if __name__ == "__main__":
    main()
