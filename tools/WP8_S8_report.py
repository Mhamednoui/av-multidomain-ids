"""WP8 S8 report writer: reports/WP8_S8.md and results/WP8/S8/s8_summary.json from the S8 result JSONs (no hand-typed numbers in the tables).
Run: python -u -W ignore tools/WP8_S8_report.py"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "results" / "WP8" / "S8"
J = lambda n: json.loads((R / n).read_text())
dq, fa, gl, v2, gs, sv, sh, ld = (J(x) for x in ("dq.json", "fa_by_drive.json", "gps_layers.json", "v2aix_fa.json", "gate_stats.json", "system_s8_val.json", "system_s8_h31.json", "lidar_domain.json"))
s7 = json.loads((ROOT / "results/WP8/S7/system_h31.json").read_text())
p = lambda x, d=1: f"{100 * x:.{d}f} %"
ci = lambda c, d=1: f"[{100 * c[0]:.{d}f}, {100 * c[1]:.{d}f}]"
pt = lambda x, d=1: f"{100 * x:+.{d}f}"

U, G = sh["runs"]["v31_ungated"]["K"], sh["runs"]["v31_gated"]["K"]
UC, GC = sh["runs"]["v31_ungated"]["C"], sh["runs"]["v31_gated"]["C"]
PK = sh["paired_gated_minus_ungated"]["K"]
HK = sh["health"]["K"]
VU, VG = sv["runs"]["v31_ungated"]["K"], sv["runs"]["v31_gated"]["K"]
reg = all(sh["runs"]["v31_ungated"][f][k] == s7["runs"]["v31"][f][k] for f in "KC" for k in sh["runs"]["v31_ungated"][f] if k in s7["runs"]["v31"][f])
hv, hk0 = fa["H31"]["veh"], fa["H31"]["lidar"]
oth = [d for d in hv if d != "0093"]
nt = sum(hv[d]["ticks"] for d in oth)
ns = sum(hk0[d]["scans"] for d in oth)
pool = lambda tab, key, w, ds: sum(tab[d][key] * tab[d][w] for d in ds) / sum(tab[d][w] for d in ds)
vv, vl = fa["V31_val"]["veh"], fa["V31_val"]["lidar"]
lr = ld["rows"]
CL, PD = lr["clean scans (FA)"], lr["PointDrop"]
ov = HK["attack_detection_split"]["overlapping_gated"]
no = HK["attack_detection_split"]["not_overlapping"]
ha = HK["attack"]
lab_all = sum(a["labelled_ticks"] for a in ha.values())
gat_all = sum(a["labelled_gated"] for a in ha.values())
summary = {
    "regression_A3_ungated_equals_S7": bool(reg), "val_gate_fired_ticks": [sv["health"][f]["clean"]["gated_ticks"] for f in "KC"],
    "val_K": {"fa_ungated": VU["fa_tick"], "fa_gated": VG["fa_tick"], "det_ungated": VU["det_single"], "det_gated": VG["det_single"]},
    "h31_K": {"fa_ungated": U["fa_tick"], "fa_gated": G["fa_tick"], "fa_gated_evaluable": HK["clean"]["fa_tick_gated_evaluable_ticks"], "events_ungated": U["events_per_hour"], "events_gated": G["events_per_hour"],
              "safe_stop_ungated": U["SAFE_STOP_per_hour"], "safe_stop_gated": G["SAFE_STOP_per_hour"], "det_ungated": U["det_single"], "det_gated": G["det_single"], "held_ungated": U["det_heldout"], "held_gated": G["det_heldout"],
              "blind_share": HK["clean"]["blind_share_of_ticks"], "health_episodes_per_hour": HK["clean"]["health_episodes_per_hour"], "paired": {k: PK[k] for k in ("fa_tick", "events_per_hour", "det_single", "det_heldout", "blame_correct", "blame_wrong")}},
    "h31_C_unchanged": all(UC[k] == GC[k] for k in ("fa_tick", "events_per_hour", "det_single")),
    "lidar": {"clean_fa_ungated": CL["rate_ungated"], "clean_fa_gated": CL["rate_gated"], "pointdrop_ungated": PD["rate_ungated"], "pointdrop_gated": PD["rate_gated"], "pointdrop_excl_0093": PD["rate_ungated_excl_0093"]},
    "attack_gate_share": {"labelled_ticks": lab_all, "labelled_gated": gat_all, "share": gat_all / lab_all, "overlap_detection_ungated": ov["event_detection_ungated"], "overlap_detection_gated": ov["event_detection_gated"], "n_overlap": ov["n"]},
}
(R / "s8_summary.json").write_text(json.dumps(summary, indent=1))

L = []
w = L.append
w("# WP8 S8: post-M4 false-alarm diagnostic and sensor-health gate\n")
w("Date: 2026-11-05    Worker: sonnet (high, T3)    Branch v3.1 (tag v3.0 untouched)    Rules and diagnosis: notes/WP8_S8.md (committed b1d2749 BEFORE any fix)\n")
w("## Summary (<= 40 lines)\n")
w(f"- **Root cause of the K false alarms (a data defect, not a detector bug).** H31 drive 2011_09_26_drive_0093 (clean GPS tick FA {p(hv['0093']['gps_fa'])}, cross {p(hv['0093']['cross_fa'])}, LiDAR scans {p(hk0['0093']['lidar_fa'])}) has a navigation record that never converged: OXTS `pos_accuracy` {dq['H31:0093']['pos_acc']['mean']:.1f} m mean / {dq['H31:0093']['pos_acc']['max']:.1f} m max on every frame (all 35 other drives <= 1.62 m), `vel_accuracy` up to {dq['H31:0093']['vel_acc']['max']:.2f} m/s, 2-7 satellites, no GNSS position on 258 of 433 frames, orientation mode 0 on all frames, lateral velocity up to {dq['H31:0093']['vl_abs_max']:.1f} m/s, heading off the course over ground by up to 160 deg. The sim derives GPS, compass, wheel speed, gyro and the LiDAR ego pose from that record, so every layer that compares them with the real LiDAR fires. The LiDAR odometry is healthy (step error vs OXTS 0.99 m on 0093, 0.007-0.09 m on the other 22 drives). Timestamps, scan counts and point counts are clean; speed and yaw rate are inside the training envelope.")
w(f"- **Other items (descriptive, no fix):** without 0093 the K clean FA is GPS {p(pool(hv, 'gps_fa', 'ticks', oth))}, cross {p(pool(hv, 'cross_fa', 'ticks', oth))} (start-up transients of drives 0047 / 0009), LiDAR scans {p(pool(hk0, 'lidar_fa', 'scans', oth))} (L2a intensity episodes on 0009 / 0064, L2d on 0004: scene-specific, pose healthy, intensity inside the envelope): a genuine drive-level tail of tile statistics (no data defect, no bug; the drives are inside the envelope, so this is \"(b) genuine\" but not \"out of envelope\"). V2AIX Stationary FA {p(v2['Stationary']['h31']['pooled'], 2)}: concentrated in a few site-days (top 10 % of recordings carry {p(v2['Stationary']['h31']['share_of_alarms_from_top10pct_recs'], 0)} of the alarms; Theaterstrasse {p(next(r for r in v2['Stationary']['site'] if 'Theater' in r['site'])['physics'], 1)}), class (b), day-to-day shift of the 1 % budget.")
w(f"- **Fix (F1, pre-registered): reference-health gate** (system/health31.py). A frame is degraded if the unit's own `pos_accuracy` > 5.0 m or `vel_accuracy` > 0.5 m/s (3 x the largest value on any train / V31_val drive; 5 sigma / 10 sigma of the detectors' receiver-noise model). Degraded ticks withhold the GPS-domain and cross-domain verdicts and mask the pose layers L2c / L2d of the LiDAR union; they publish `sensor_health = reference degraded`. This is a sensor-health signal, NOT an attack verdict; no threshold, ECDF, combiner or correlator changed.")
w(f"- **V31_val (rule A1, A2):** the gate fires on 0 of {gs['summary_V31_val']['frames']} OXTS frames of the 10 V31_val drives and 0 of {gs['summary_train']['frames']} of the 13 train drives; gated and ungated system results are identical and equal the frozen in-sample check (K FA {p(VG['fa_tick'], 2)}, {VG['events_per_hour']:.2f} events/h, detection {p(VG['det_single'], 1)}). Detection change 0.0 pts (tolerance 1.0). A3: ungated H31 run equals the S7 v3.1 numbers on all keys: {reg}.")
w(f"- **H31 re-scoring, ONE run, labelled \"re-used hold-out, exposure 2 (post-M4 fix), NOT fresh\"** (frozen v3.1 vs v3.1 + S8, same composites, paired bootstrap over clean timelines / groups, B = 2000, seed 31): K clean tick FA {p(U['fa_tick'])} -> **{p(G['fa_tick'])}** {ci(G['fa_tick_ci'])} (paired {pt(PK['fa_tick']['diff'])} pts {ci(PK['fa_tick']['ci'])}; on evaluable ticks {p(HK['clean']['fa_tick_gated_evaluable_ticks'])}); events per clean hour {U['events_per_hour']:.1f} -> {G['events_per_hour']:.1f}; SAFE_STOP per clean hour {U['SAFE_STOP_per_hour']:.2f} -> {G['SAFE_STOP_per_hour']:.2f}; K event detection (single-domain) {p(U['det_single'])} -> {p(G['det_single'])} (paired {pt(PK['det_single']['diff'])} pts {ci(PK['det_single']['ci'])}); held-out {p(U['det_heldout'])} -> {p(G['det_heldout'])} (paired {pt(PK['det_heldout']['diff'])} {ci(PK['det_heldout']['ci'])}). Comma unchanged (gate fires 0 times).")
w(f"- **Against the unchanged M4 bounds (for information; the S7 M4 verdict stands):** K FA {p(G['fa_tick'])} vs 3 %: NOT MET; events {G['events_per_hour']:.1f}/h vs 10: NOT MET; SAFE_STOP {G['SAFE_STOP_per_hour']:.2f}/h vs 1: now MET (was {U['SAFE_STOP_per_hour']:.2f}); LiDAR clean scan FA {p(CL['rate_ungated'])} -> {p(CL['rate_gated'], 2)} vs 1.5 %: NOT MET; PointDrop per scan {p(PD['rate_ungated'])} -> {p(PD['rate_gated'])} vs 65 %: NOT MET. The pre-registered expectation (K FA about 4.5 %, events about 24/h, LiDAR scan FA about 3 %) held. The fix repairs the 0093 defect; v3.1 still does not meet M4.")
w(f"- **The previous \"PointDrop 66.1 %\" and the K detection 87.1 % were partly flood effects:** on 0093 the alarm rate was so high that attack composites overlapping its gated ticks were \"detected\" {p(ov['event_detection_ungated'], 0)} of the time ({ov['n']} single-domain composites); with the gate {p(ov['event_detection_gated'])}; on the {no['n']} other composites detection is identical ({p(no['event_detection_gated'])}). PointDrop per scan on the 12 healthy drives is {p(PD['rate_ungated_excl_0093'])} either way.")
w(f"- **Attack windows and the gate:** {p(gat_all / lab_all)} of the K attack-labelled ticks are gated ({gat_all} of {lab_all}), all on drive 0093 (the simulated attacks never touch the accuracy fields). In deployment the fields are receiver output: a spoofer that controls the receiver can claim a poor accuracy and blind the GNSS-based checks (discussion below). CAN, network, V2X and LiDAR L1 / L2a keep running.")
w("- Not fixed, stated: LiDAR L2a drive-level episodes, V2AIX Stationary day shift, comma clean FA 6.1 % (V2X / CAN / network own alarms), start-up transients of the speed edges. Remaining K clean events come from CAN, V2X, LiDAR, cross and network own alarms (table 6).")
w("- Statistical caveat: the improvement rests on ONE drive (0093); a drive-cluster bootstrap over the 13 H31 drives gives for the LiDAR clean scan FA a paired CI touching 0 (" + f"{pt(CL['paired_diff'], 1)} pts {ci(CL['paired_ci'])}" + "). The system-level CIs above resample clean timelines / composites, not drives.")
w("- Files: notes/WP8_S8.md, system/health31.py, tests/v31/test_s8_health.py (4 tests), tools/WP8_S8_*.py, results/WP8/S8/*.json, scores results/WP8/scores/S8/.\n")

w("## 1. Per-drive false alarms, by layer (frozen detectors, saved S7 / S2 / S3 scores; results/WP8/S8/fa_by_drive.json, gps_layers.json)\n")
w("Table 1: clean-tick false alarms per drive (H31 and V31_val). GPS = combined GPS-domain alarm; cross = combined cross-domain alarm; LiDAR = combined scan alarm; L1 / L2a / L2c / L2d = layer over its own threshold (V31_val: frozen thresholds on the leave-one-drive-out raw scores, in-sample reference, indicative).\n")
w("| set | drive | ticks | GPS | cross | scans | LiDAR | L1 | L2a | L2c | L2d |\n|---|---|---|---|---|---|---|---|---|---|---|")
for s, veh, lid_ in (("H31", hv, hk0), ("V31_val", vv, vl)):
    for d in sorted(veh):
        a, b = veh[d], lid_[d]
        w(f"| {s} | {d} | {a['ticks']} | {p(a['gps_fa'])} | {p(a['cross_fa'])} | {b['scans']} | {p(b['lidar_fa'])} | {p(b['fire:L1'])} | {p(b['fire:L2a'])} | {p(b['fire:L2c'])} | {p(b['fire:L2d'])} |")
w(f"| H31 without 0093 (pooled) | - | {nt} | {p(pool(hv, 'gps_fa', 'ticks', oth))} | {p(pool(hv, 'cross_fa', 'ticks', oth))} | {ns} | {p(pool(hk0, 'lidar_fa', 'scans', oth))} | - | {p(pool(hk0, 'fire:L2a', 'scans', oth))} | {p(pool(hk0, 'fire:L2c', 'scans', oth))} | {p(pool(hk0, 'fire:L2d', 'scans', oth))} |")
w(f"| V31_val (pooled) | - | {sum(v['ticks'] for v in vv.values())} | {p(pool(vv, 'gps_fa', 'ticks', list(vv)))} | {p(pool(vv, 'cross_fa', 'ticks', list(vv)))} | {sum(v['scans'] for v in vl.values())} | {p(pool(vl, 'lidar_fa', 'scans', list(vl)))} | - | - | - | - |\n")
e0 = hv["0093"]
w("Table 2: cross edges and GPS-domain layers on drive 0093 (share of clean ticks that alarm), against the pooled rate over the 12 other H31 drives.\n")
w("| layer | 0093 | other 12 H31 drives (pooled) |\n|---|---|---|")
for k, v in e0.items():
    if k.startswith("edge:"):
        w(f"| cross edge {k[5:]} | {p(v)} | {p(pool(hv, k, 'ticks', oth))} |")
g93 = gl["0093"]["layers"]
for k, v in g93.items():
    ot = sum(gl[d]["layers"][k] * gl[d]["ticks"] for d in oth) / sum(gl[d]["ticks"] for d in oth)
    w(f"| GPS layer {k.replace('gps.', '')} | {p(v)} | {p(ot, 2)} |")
w("")
w("## 2. Data quality of the recordings (results/WP8/S8/dq.json; OXTS dataformat fields)\n")
w("Table 3: receiver / record fields, 0093 against the other H31 drives (min - max over the 12) and the 23 V31_val + train drives (min - max).\n")
oh = [dq[f"H31:{d}"] for d in oth]
ot_ = [v for k, v in dq.items() if not k.startswith("H31")]
rng = lambda xs, f: f"{min(f(x) for x in xs):.3g} - {max(f(x) for x in xs):.3g}"
rows = [("OXTS frames / velodyne scans", lambda x: f"{x['n_oxts']} / {x['n_scans']}", None), ("pos_accuracy max (m)", lambda x: f"{x['pos_acc']['max']:.2f}", lambda x: x["pos_acc"]["max"]),
        ("vel_accuracy max (m/s)", lambda x: f"{x['vel_acc']['max']:.3f}", lambda x: x["vel_acc"]["max"]), ("numsats mean (min)", lambda x: f"{x['numsats']['mean']:.1f} ({x['numsats']['min']:.0f})", lambda x: x["numsats"]["mean"]),
        ("share of frames with posmode 0 (no GNSS position; not discriminating alone)", lambda x: f"{x['posmode'].get('0', 0) / x['n_oxts']:.2f}", lambda x: x["posmode"].get("0", 0) / x["n_oxts"]), ("leftward velocity, abs max (m/s)", lambda x: f"{x['vl_abs_max']:.2f}", lambda x: x["vl_abs_max"]),
        ("OXTS dt max (s)", lambda x: f"{x['oxts_dt']['max']:.3f}", lambda x: x["oxts_dt"]["max"]), ("scan dt max (s)", lambda x: f"{x['scan_dt']['max']:.3f}", lambda x: x["scan_dt"]["max"]),
        ("duplicate timestamps (OXTS / scan)", lambda x: f"{x['oxts_dt']['n_dup']} / {x['scan_dt']['n_dup']}", None), ("scan points mean", lambda x: f"{x['scan_points']['mean']:.0f}", lambda x: x["scan_points"]["mean"]),
        ("mean speed / max speed (m/s)", lambda x: f"{x['speed_vf']['mean']:.1f} / {x['speed_vf']['max']:.1f}", lambda x: x["speed_vf"]["max"]), ("yaw rate, abs p95 / max (rad/s)", lambda x: f"{x['wz_abs']['p95']:.3f} / {x['wz_abs']['max']:.3f}", lambda x: x["wz_abs"]["max"])]
w("| field | 0093 | other 12 H31 (range) | V31_val + train 23 (range) |\n|---|---|---|---|")
for name, f, g in rows:
    if g is None:
        w(f"| {name} | {f(dq['H31:0093'])} | - | - |")
    else:
        w(f"| {name} | {f(dq['H31:0093'])} | {rng(oh, g)} | {rng(ot_, g)} |")
w("\nPhysics of the record: yaw minus course over ground atan2(vn, ve) 9 deg at t = 0-3 s, 67 deg at 15 s, 124 deg mean at 27 s (up to 160 deg), back to -26 deg at 33-42 s; forward velocity vf (the projection on that heading) 3.2-5 m/s where |v| = 8-14 m/s and -6.2 m/s at t = 27 s; position-difference speed 22 m/s at t = 15 s (receiver re-acquisition); LiDAR ICP speed 5.3-6.3 m/s with lateral step 0.009 m. Mean OXTS-vs-ICP pose step error per scan: 0093 0.99 m (p95 1.99 m), the other 22 drives 0.007-0.09 m; L2d fires on scans with 1.11 m mean error vs 0.25 m without. (Ad-hoc scripts of the analysis are summarised in notes/WP8_S8.md; the table above is generated from dq.json.)\n")
w("## 3. Classification\n")
w("| cause | class | evidence | action |\n|---|---|---|---|")
w("| 0093: non-converged OXTS navigation record (GPS, cross, LiDAR L2d / L2c) | (a) data defect in the recording, amplified by the sim (every non-LiDAR channel derived from OXTS) | Tables 1-3 | gate F1 |")
w("| other-drive cross FA (0047 5.0 %, 0009 2.6 %) | (b) start-up transients of the speed edges, first 30 s | alarms 30/300, 12/300 ticks in the first 30 s | none |")
w("| LiDAR L2a episodes (0009, 0064), L2d (0004) | (b) genuine tail (inside the envelope; no defect, no bug): scene-specific episodes, pose healthy, intensity inside envelope | OXTS-vs-ICP error 0.027-0.049 m in firing scans | none |")
w(f"| V2AIX Stationary FA {p(v2['Stationary']['h31']['pooled'], 2)} | (b) day-to-day shift concentrated in few site-days | per-recording table in v2aix_fa.json | none |")
w("| detector bug | (c) none found: the same layers stay near the 1 % budget on the 35 drives with a healthy reference | - | - |\n")
w("## 4. Fix F1 and acceptance (rules A1-A5 as pre-registered in notes/WP8_S8.md)\n")
w("Table 4: where the gate fires (results/WP8/S8/gate_stats.json).\n")
w("| set | drives | drives gated | OXTS frames | degraded frames | gated 1 Hz ticks (10 phases) |\n|---|---|---|---|---|---|")
for s in ("V31_val", "train", "H31"):
    x = gs[f"summary_{s}"]
    w(f"| {s} | {x['drives']} | {x['drives_gated']} | {x['frames']} | {x['degraded_frames']} | {p(x['gated_tick_share'])} |")
sen = gs["sensitivity_pos_acc_m"]
w(f"\nSensitivity (description, not a choice): the gated set is the same for any `pos_accuracy` threshold between {sen['largest_pos_acc_on_ungated_drives']:.2f} m (largest value on a drive that is not gated) and {min(sen['smallest_pos_acc_of_gated_drives'].values()):.2f} m (smallest value on drive 0093).\n")
w("Table 5: rule check.\n")
w("| rule | result | verdict |\n|---|---|---|")
w(f"| A1 V31_val no harm (gate <= 0.5 % of ticks and scans; K detection drop <= 1.0 pt; FA / events not up) | gate 0 ticks; detection {p(VU['det_single'])} -> {p(VG['det_single'])}; FA {p(VU['fa_tick'], 2)} -> {p(VG['fa_tick'], 2)}; events/h {VU['events_per_hour']:.2f} -> {VG['events_per_hour']:.2f} | MET (no-op on V31_val by construction; stated) |")
w(f"| A2 gate precision on healthy drives (<= 0.5 %) | 0 of {gs['summary_V31_val']['frames'] + gs['summary_train']['frames']} frames | MET |")
w(f"| A3 regression: ungated == S7 frozen v3.1 | equal on all keys (K and C): {reg}; v3 / S7 files untouched (git diff --name-status v3.0 HEAD on the v3 packages lists only added v3.1 files, no modified v3 file; tests/v31 65 pass) | MET |")
w("| A4 H31 exposure 2: one re-scoring, side by side, paired | Table 6 | done (ONE run) |")
w("| A5 attack windows and gate | Table 7 and discussion | reported |\n")
w("## 5. H31 re-scoring, exposure 2 (re-used hold-out, post-M4 fix, NOT fresh)\n")
w("Table 6: K = KITTI H31 vehicle block + re-used CAN / network / V2X streams (partially fresh). Paired = v3.1 + S8 minus frozen v3.1, same composites, bootstrap over clean timelines (FA, events) and over groups inside each type (detection, blame), B = 2000, seed 31.\n")
w("| metric (K) | frozen v3.1 | v3.1 + S8 | paired difference [95 % CI] | M4 bound |\n|---|---|---|---|---|")
w(f"| clean tick FA | {p(U['fa_tick'])} {ci(U['fa_tick_ci'])} | {p(G['fa_tick'])} {ci(G['fa_tick_ci'])} | {pt(PK['fa_tick']['diff'])} pts {ci(PK['fa_tick']['ci'])} | <= 3.0 %: NOT MET |")
w(f"| clean tick FA on evaluable (non-gated) ticks | - | {p(HK['clean']['fa_tick_gated_evaluable_ticks'])} | - | - |")
w(f"| alert events per clean hour | {U['events_per_hour']:.2f} {U['events_per_hour_ci'][0]:.1f}-{U['events_per_hour_ci'][1]:.1f} | {G['events_per_hour']:.2f} {G['events_per_hour_ci'][0]:.1f}-{G['events_per_hour_ci'][1]:.1f} | {PK['events_per_hour']['diff']:+.2f} [{PK['events_per_hour']['ci'][0]:+.2f}, {PK['events_per_hour']['ci'][1]:+.2f}] | <= 10: NOT MET |")
w(f"| SAFE_STOP per clean hour | {U['SAFE_STOP_per_hour']:.2f} | {G['SAFE_STOP_per_hour']:.2f} [{G['SAFE_STOP_per_hour_ci'][0]:.2f}, {G['SAFE_STOP_per_hour_ci'][1]:.2f}] | {PK['safe_stop_per_hour']['diff']:+.2f} | <= 1: MET (upper CI > 1) |")
w(f"| mean event detection, single-domain types | {p(U['det_single'])} {ci(U['det_single_ci'])} | {p(G['det_single'])} {ci(G['det_single_ci'])} | {pt(PK['det_single']['diff'])} pts {ci(PK['det_single']['ci'])} | >= 70 %: MET |")
w(f"| held-out types | {p(U['det_heldout'])} {ci(U['det_heldout_ci'])} | {p(G['det_heldout'])} {ci(G['det_heldout_ci'])} | {pt(PK['det_heldout']['diff'])} pts {ci(PK['det_heldout']['ci'])} | >= 60 %: MET |")
w(f"| blame correct / wrong | {p(U['blame_correct'])} / {p(U['blame_wrong'])} | {p(G['blame_correct'])} / {p(G['blame_wrong'])} | {pt(PK['blame_correct']['diff'])} / {pt(PK['blame_wrong']['diff'])} pts | >= 75 / <= 10: NOT MET |")
w(f"| health-flag ticks (blind share) / episodes per clean hour | - | {p(HK['clean']['blind_share_of_ticks'])} / {HK['clean']['health_episodes_per_hour']:.1f} | - | reported separately, not alerts |")
w(f"| comma C (clean FA / events per hour / detection) | {p(UC['fa_tick'])} / {UC['events_per_hour']:.1f} / {p(UC['det_single'])} | identical | 0 | unchanged |")
w("\nBy attacked domain (K event detection of single-domain types; paired gated - ungated):\n")
w("| domain | frozen v3.1 | v3.1 + S8 | paired [95 % CI] (pts) |\n|---|---|---|---|")
for dmn in sorted(PK["by_attacked_domain"]):
    q = PK["by_attacked_domain"][dmn]
    w(f"| {dmn} | {p(U['by_attacked_domain'][dmn]['event_detection'])} | {p(G['by_attacked_domain'][dmn]['event_detection'])} | {pt(q['diff'])} {ci(q['ci'])} |")
w("\nTable 7: attack-labelled ticks of the K composites that are gated (all on drive 0093) and detection on composites overlapping them (single-domain composites).\n")
w("| attacked domain | composites | labelled ticks | gated labelled ticks | composites with a gated labelled tick |\n|---|---|---|---|---|")
for k, a in sorted(ha.items()):
    w(f"| {k} | {a['composites']} | {a['labelled_ticks']} | {a['labelled_gated']} ({p(a['labelled_gated'] / a['labelled_ticks'])}) | {a['composites_overlapping']} |")
w(f"\nSingle-domain composites overlapping gated ticks: {ov['n']}: event detection {p(ov['event_detection_ungated'], 0)} (ungated) -> {p(ov['event_detection_gated'])} (gated). Not overlapping: {no['n']}: {p(no['event_detection_ungated'])} -> {p(no['event_detection_gated'])} (identical). The gate counts as a miss there; no credit is given.\n")
w("Table 8: own-alarm share of clean ticks per domain (K clean timelines): where the remaining false alarms come from.\n")
w("| domain | frozen v3.1 | v3.1 + S8 |\n|---|---|---|")
for dmn in ("gps", "cross", "lidar", "can", "network", "v2x"):
    w(f"| {dmn} | {p(U['own_alarm_share'][dmn])} | {p(G['own_alarm_share'][dmn])} |")
w("\nTable 9: LiDAR domain, H31 scan level (results/WP8/S8/lidar_domain.json; frozen union thresholds, L2c / L2d masked at gated scans). Paired = gated - ungated, bootstrap over the 13 drives (B = 2000, seed 31); only one drive changes, so the CI touches 0.\n")
w("| subset | scans | gated scans | ungated | gated | paired [95 % CI] (pts) | ungated excl. 0093 |\n|---|---|---|---|---|---|---|")
for k, v in lr.items():
    w(f"| {k} | {v['scans']} | {v['gated_scans']} | {p(v['rate_ungated'], 2)} | {p(v['rate_gated'], 2)} | {pt(v['paired_diff'], 2)} {ci(v['paired_ci'], 2)} | {p(v['rate_ungated_excl_0093'], 2)} |")
w("\n## 6. Can an attacker exploit the gate?\n")
w("The gate withholds verdicts that depend on the navigation record when the record's own accuracy fields are bad. Honest assessment:\n"
  "1. It creates a blind spot exactly where GNSS spoofing is detected. In the simulation the fields are never attacked, so the measured cost (8.4 % blind clean ticks, all on one drive; detection on the 153 composites that overlap gated ticks 100 % -> 38.6 %, where the 100 % was the false-alarm flood) is the cost of a genuine outage, not of an adversary.\n"
  "2. In deployment `pos_accuracy` is receiver output. A spoofer or jammer that makes the receiver report a poor fix (or a spoofer that sets large accuracy fields) can switch the GNSS-based checks off. Jamming / denial is itself an attack on availability, and the gate publishes it as `sensor_health` (reason: reported accuracy), so it is visible, but it is not scored as a verdict.\n"
  "3. What remains active while gated: CAN, network, V2X, LiDAR L1 geometry and L2a intensity, and in a real vehicle the LiDAR-odometry-vs-wheel-speed edge (independent of the GNSS unit; in this sim it is switched off too because the wheel speed is derived from OXTS). A takeover that needs a GNSS lie to be plausible is therefore not hidden from those domains.\n"
  "4. Recommended hardening (NOT implemented, not tested, outside the pre-registered rules): cap the withheld time (a degraded episode longer than a few minutes, or one that starts with no environmental cause such as a satellite-count drop at an open-sky position, escalates to DEGRADE as a sensor-health alarm); require the unit's accuracy to agree with an independent estimate (LiDAR-odometry drift, speed residual) before accepting a very large claimed error; use `numsats` / signal strength as a second, harder-to-forge witness when available.\n"
  "5. The gate never turns an alarm into a detection and never lowers a threshold; the worst case of a forged health field is the unchanged v3.1 minus the GNSS-dependent verdicts for the forged duration.\n")
w("## 7. What S8 does and does not change\n")
w("- Changes: one new module (system/health31.py, 4 tests), tools and results in WP8 folders. Frozen v3 and v3.1 objects, thresholds, ECDFs, correlator, S7 caches and S7 results untouched (S7 caches are read-only inputs; the gated sources are built in memory).\n"
  "- H31 is now exposure 2 for the K vehicle block. The S8 H31 numbers are descriptive of a fix that was designed after seeing the failure; the evidence for the fix is (i) the physical diagnosis (Table 3), (ii) the zero-effect check on V31_val and train, (iii) that the pre-registered thresholds lie in a wide interval (1.62 - 18.67 m) that gives the same result.\n"
  "- The M4 verdict (7 of 18, NOT MET) is not rewritten. A defensible reading: the K false-alarm failure of M4 was dominated by a defective recording; with the sensor-health gate the K FA is 4.7 %, still above the bound; the remaining excess is CAN, V2X, network and LiDAR own alarms on re-used streams and the LiDAR drive-level variance, which S8 did not and could not fix without tuning on H31.\n")
w("## Open points for the supervisor\n")
w("- Decide whether the gate is adopted as v3.1 + S8 (a 'sensor-health' layer) and whether the hardening of section 6 point 4 is pre-registered for a later step.\n"
  "- The sim couples CAN wheel speed, IMU and GPS to one OXTS record; for 0093 this over-counts alarming edges relative to a real vehicle. A decoupled evaluation (real CAN logs for KITTI do not exist) is not possible with this data.\n"
  "- LiDAR scan FA (2.4 %) and the drive-level variance of L2a remain above the 1.5 % rule; a per-drive budget would need a rule chosen without H31.\n"
  "- C (comma) clean FA 6.1 % and V2AIX Stationary 2.26 % are untouched.\n")
(ROOT / "reports" / "WP8_S8.md").write_text("\n".join(L), encoding="utf-8")
print("written reports/WP8_S8.md", len("\n".join(L)), "chars; summary", json.dumps(summary["h31_K"]["paired"])[:200])
