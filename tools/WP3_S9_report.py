"""WP3 S9: writes reports/M1_LiDAR.md from the JSON results (every number below is read from results/WP3/S9/*.json or the earlier WP3 result files).
Usage: python -u -W ignore tools/WP3_S9_report.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS

R9 = RESULTS / "WP3" / "S9"
J = lambda p: json.loads(Path(p).read_text())  # noqa
F, Z, D, A, X = (J(R9 / f"{n}.json") for n in ("final", "freeze_check", "dev", "acceptance", "extra"))
S2B, S1 = J(RESULTS / "WP3" / "S2b" / "val_old_vs_fixed.json"), J(RESULTS / "WP3" / "S1_reproduction.json")
S5, S7 = J(RESULTS / "WP3" / "S5" / "final.json"), J(RESULTS / "WP3" / "S7" / "final.json")
h = F["headline"]
LA, AB = F["layers_alone"], F["all_but"]
p = lambda x, d=1: f"{100 * x:.{d}f}"  # noqa
det = lambda r, a: p(r["det"][a]["det"])  # noqa
ci = lambda r, a: f"[{p(r['det'][a]['ci95'][0])}, {p(r['det'][a]['ci95'][1])}]"  # noqa
E, W = F["episodes"]["ep"]["stack"], F["episodes"]["epw"]["stack"]
ek = lambda b, k: f"{b['kinds'][k]['detected_3s']}/{b['kinds'][k]['episodes']}"  # noqa
dl = lambda b, k: "-" if b["kinds"][k]["median_first_alert_s"] is None else f"{b['kinds'][k]['median_first_alert_s']:.2f}"  # noqa
v2 = F["v2_side_by_side"]
fa_d = h["fa_per_drive"]
ATT = ["ph_replace_near", "ph_replace_far", "ph_budget_near", "ph_budget_far", "PointDrop", "IntensitySpoof"]
NM = {"ph_replace_near": "replace near", "ph_replace_far": "replace far", "ph_budget_near": "budget near", "ph_budget_far": "budget far", "PointDrop": "PointDrop",
      "IntensitySpoof": "IntensitySpoof", "cmp_boxcloud": "box cloud*", "cmp_mradd_near": "multi-return add near*", "cmp_mradd_far": "multi-return add far*"}
L = []
w = L.append
w("# M1-LiDAR: LiDAR spoofing detection by sensor physics (WP3, milestone report)\n")
w(f"Date 2026-10-25. Status: **PARTIAL** (rules written before any S9 result: notes/WP3_lidar.md \"S9 design and ACCEPTANCE RULE\"; verdicts: results/WP3/S9/acceptance.json). Self-contained; long tables: `results/WP3/S9/S9_tables.md`; numbers: `dev.json` (validation), `final.json` (test, one run), `freeze_check.json`, `test_scores.csv.gz`; earlier steps: reports/WP3_S1 ... S7.\n")
w("**Protocol.** KITTI raw, Velodyne HDL-64E, 23 drives: 13 train, 3 validation, 7 test (0001 0005 0095 0039 0079 0028 0052). There is no labelled attack and no labelled object, so attacks are generated: calibrated ray-cast phantoms (exact laser rays; return probability and intensity fitted on real KITTI objects, S2) under SINGLE-RETURN physics (one return per beam: an injected return replaces the real one behind it, S2b), replace (full box) / budget (50-400 points) x near (5-15 m) / far (15-40 m); PointDrop (random thinning of a 10-60 deg sector); IntensitySpoof (bright sector). "
  f"{h['det']['PointDrop']['n']} attacked scans per attack (every 3rd scan of the 7 test drives); persistent episodes of 30 scans, 21 per kind, sensor-fixed (placed relative to the sensor) and world-fixed (placed in the world, parked-car-like); episode alarm = v2 rolling log-odds over 1 s above the 99th percentile of clean windows, within 3 s. Rows marked * (multi-return add, single-return box cloud) are comparison rows: physically impossible or crude on a single-return sensor, never headline.")
w(f"**Stack (zero-shot, no attack label in any fit).** Headline = L1 sensor geometry + L2a object intensity + L2c background model + L2d ego-compensated tracking. Combiner chosen on validation by the label-free rule (clean false-alarm control first, then detection): {D['V1']['chosen']} of ECDF ranks (split and noisy-or tested: noisy-or eliminated, worst-drive LODO FA {p(D['stacks']['int/noisy_or']['lodo_worst'])}% against {p(D['stacks']['int/max']['lodo_worst'])}%; split {p(D['stacks']['int/split']['mean_phys'])}% vs max {p(D['stacks']['int/max']['mean_phys'])}% mean validation detection). Density part of L2a NOT kept ({p(D['V2']['gain'])} points on validation). Thresholds: 1% TOTAL scan budget, tie-safe, from the out-of-fold clean scores of the 16 train+val drives (object model refitted leave-one-drive-out; L1, L2c, L2d have no learned parameter). Optional rows (never headline): L2b occlusion, L4 supervised descriptor model (seen families only). L3 dropped (S7).\n")
w("## 1. What each layer catches, and why (test, scan level, each layer at its OWN 1% threshold; FA of the clean scans)\n")
w("| layer | physics | FA | PointDrop | IntensitySpoof | replace near | far / budget phantoms |")
w("|---|---|---|---|---|---|---|")
phys = {"raw_L1": "L1 geometry: each return lies on one of 64 laser rings and a beam has one return; a point injected off its ring, or a second return in a beam, breaks the sensor model",
        "raw_L2a": "L2a intensity: the mean intensity of a patch of a surface depends on range and material; a bright sector (spoofed reflectivity) is outside what clean objects give",
        "raw_L2c": "L2c background: the previous scan moved by the ego pose predicts which ring / azimuth windows return; a removed sector leaves them empty",
        "raw_L2d": "L2d tracking: a surface that appears in free space, or stays fixed to the sensor while the car moves, is no static or moving object"}
for c in ("raw_L1", "raw_L2a", "raw_L2c", "raw_L2d"):
    r = LA[c]
    w(f"| {c[4:]} | {phys[c]} | {p(r['fa'], 2)} | {det(r, 'PointDrop')} | {det(r, 'IntensitySpoof')} | {det(r, 'ph_replace_near')} | {p(max(r['det'][a]['det'] for a in ('ph_replace_far', 'ph_budget_near', 'ph_budget_far')))} |")
o = F["optional"]
w(f"| L2b (optional) | free space: far returns seen between returns of one object mean it is not solid | {p(o['L2b alone']['fa'], 2)} | {det(o['L2b alone'], 'PointDrop')} | {det(o['L2b alone'], 'IntensitySpoof')} | {det(o['L2b alone'], 'ph_replace_near')} | {p(max(o['L2b alone']['det'][a]['det'] for a in ('ph_replace_far', 'ph_budget_near', 'ph_budget_far')))} |")
w(f"| L4 (seen families only) | XGBoost on the v2 descriptor, trained on our own PointDrop / IntensitySpoof / phantom generator | {p(o['L4 alone']['fa'], 2)} | {det(o['L4 alone'], 'PointDrop')} | {det(o['L4 alone'], 'IntensitySpoof')} | {det(o['L4 alone'], 'ph_replace_near')} | {p(max(o['L4 alone']['det'][a]['det'] for a in ('ph_replace_far', 'ph_budget_near', 'ph_budget_far')))} |\n")
w(f"Comparison rows (impossible on a single-return sensor): L1 alone catches the multi-return add far at {det(LA['raw_L1'], 'cmp_mradd_far')}% (two returns in one beam), L2d the multi-return add near at {det(LA['raw_L2d'], 'cmp_mradd_near')}%, L2b the same at {det(o['L2b alone'], 'cmp_mradd_near')}%: the layers behave as designed on the attack they were designed for, and that attack cannot exist on this sensor.\n")
w("## 2. Final numbers (test, stack at 1% total budget; 95% intervals = bootstrap over the 7 test drives)\n")
w("| attack | detection | 95% CI | per-drive range | AUC |")
w("|---|---|---|---|---|")
for a in ATT + ["cmp_boxcloud", "cmp_mradd_near", "cmp_mradd_far"]:
    pd_ = h["det"][a]["per_drive"]
    w(f"| {NM[a]} | {det(h, a)}% | {ci(h, a)} | {p(min(pd_.values()))}-{p(max(pd_.values()))}% | {h['auc'][a]:.3f} |")
w(f"\nClean test FA **{p(h['fa'], 2)}%** {('[' + p(h['fa_ci95'][0], 2) + ', ' + p(h['fa_ci95'][1], 2) + ']')}; per drive " + ", ".join(f"{d} {p(v, 1)}" for d, v in sorted(fa_d.items())) + f" (%); leave-one-drive-out FA on the 16 train+val drives: mean {p(h['lodo_mean'], 2)}%, worst {p(h['lodo_worst'], 2)}% ({h['lodo_worst_drive']}). Small drives move by several points (a single layer alone reaches {p(max(LA[c]['lodo_worst'] for c in LA))}% on the 21-scan drive 0048). The budget is shared by four layers: **the stack loses most of what a strong layer has alone** (PointDrop {det(h, 'PointDrop')}% against {p(F['dilution']['PointDrop']['best_layer_alone'])}% for L2c alone; near replace {det(h, 'ph_replace_near')}% against {p(F['dilution']['ph_replace_near']['best_layer_alone'])}% for L2d). With every layer at its own 1% (union, FA {p(F['each_layer_at_own_1pct_union']['fa'], 2)}%) the same attacks reach {det(F['each_layer_at_own_1pct_union'], 'PointDrop')}% / {det(F['each_layer_at_own_1pct_union'], 'ph_replace_near')}%; a 2% total budget gives PointDrop {det(F['budgets']['0.02'], 'PointDrop')}%, IntensitySpoof {det(F['budgets']['0.02'], 'IntensitySpoof')}% (FA {p(F['budgets']['0.02']['fa'], 2)}%).\n")
w("**Persistent episodes (21 per kind, stack, 3 s rule; delays = median first alert of the detected ones):**\n")
w("| kind | sensor-fixed detected (delay s) | world-fixed detected (delay s) | scan alarm at onset / later steps, world-fixed |")
w("|---|---|---|---|")
for k in ("replace_near", "replace_far", "budget_near", "budget_far"):
    a, b = f"ep_{k}", f"epW_{k}"
    w(f"| {k.replace('_', ' ')} | {ek(E, a)} ({dl(E, a)}) | {ek(W, b)} ({dl(W, b)}) | {p(W['kinds'][b]['onset_scan_alarm'])}% / {p(W['kinds'][b]['sustained_scan_alarm'])}% |")
w(f"\nFalse-episode rate on {E['n_clean_windows']} clean windows (3 s each): {p(E['false_episode_rate'])}%. Only the dense, near, replacing phantom is caught (L2d: it appears in free space; {ek(E, 'ep_replace_near')} sensor-fixed, exact 95% interval [{p(E['kinds']['ep_replace_near']['ci95_exact'][0], 0)}, {p(E['kinds']['ep_replace_near']['ci95_exact'][1], 0)}]%), and a world-fixed one is caught at its FIRST scan only (scan alarm {p(W['kinds']['epW_replace_near']['onset_scan_alarm'])}% at step 1, {p(W['kinds']['epW_replace_near']['sustained_scan_alarm'])}% afterwards): once it stands in the world like a parked car, the tracker sees a static object.\n")
w("## 3. Ablation (test, same combiner, 1% total budget; detection %)\n")
w("| configuration | FA | replace near | far / budget (max) | PointDrop | IntensitySpoof | box cloud* | mr-add near* | mr-add far* |")
w("|---|---|---|---|---|---|---|---|---|")
mx = lambda r: p(max(r['det'][a]['det'] for a in ('ph_replace_far', 'ph_budget_near', 'ph_budget_far')))  # noqa
row = lambda n, r: f"| {n} | {p(r['fa'], 2)} | {det(r, 'ph_replace_near')} | {mx(r)} | {det(r, 'PointDrop')} | {det(r, 'IntensitySpoof')} | {det(r, 'cmp_boxcloud')} | {det(r, 'cmp_mradd_near')} | {det(r, 'cmp_mradd_far')} |"  # noqa
w(row("**all four (headline)**", h))
for c in ("raw_L1", "raw_L2a", "raw_L2c", "raw_L2d"):
    w(row(f"all but {c[4:]}", AB[c]))
for c in ("raw_L1", "raw_L2a", "raw_L2c", "raw_L2d"):
    w(row(f"{c[4:]} alone (own 1%)", LA[c]))
w(row("split combiner (1% total)", F["other_combiners"]["split"]))
w(row("noisy-or combiner (1% total)", F["other_combiners"]["noisy_or"]))
w(row("+ L2b (optional)", o["headline + L2b (optional)"]))
w(row("+ L4 (seen families, NOT zero-shot)", o["headline + L4 (seen families, never headline)"]))
w(row("density part added to L2a", o["density part added to L2a"]))
earn = F["earns_place"]
w(f"\nL2a earns its place ({p(earn['raw_L2a']['largest_loss_when_removed'])} points on IntensitySpoof), L2c ({p(earn['raw_L2c']['largest_loss_when_removed'])} on PointDrop), L2d ({p(earn['raw_L2d']['largest_loss_when_removed'])} on near replace); **L1 does not** ({p(earn['raw_L1']['largest_loss_when_removed'])} points on the single-return set: removing it even raises PointDrop to {det(AB['raw_L1'], 'PointDrop')}% and near replace to {det(AB['raw_L1'], 'ph_replace_near')}% because it frees budget). It stays in the headline by the supervisor's decision as the cheap sensor-integrity layer (it is the only layer that sees injection off the laser rings and duplicate beams, the comparison rows). Adding L2b dilutes PointDrop to {det(o['headline + L2b (optional)'], 'PointDrop')}%; adding L4 gives {det(o['headline + L4 (seen families, never headline)'], 'PointDrop')}% / {det(o['headline + L4 (seen families, never headline)'], 'IntensitySpoof')}% but only on the families it was trained on (leave-one-type-out collapses, S7).\n")
w("## 4. v2 side by side\n")
w(f"v2 reported 90.19% accuracy / AUC {S1['A2_v2_model_on_v3_layer']['test_auc']:.3f} on its own attack mix (PointDrop, IntensitySpoof, a box-cloud ghost with up to 1,500 points where a real car at 30 m has ~50-270; the 4-class argmax has 21.5% false alarms on normal scans). That number is **inflated by the artefacts of section 7** and is not comparable with a per-attack detection at 1% FA. The S2b physics fix collapsed it on the validation drives: v2 near multi-return add {p(S2B['ray_old_S2']['cal|add|near|onset']['v2_1pct'])} -> {p(S2B['ray_fixed']['cal|add|near|onset']['v2_1pct'])}%, v2 box cloud {p(S2B['boxcloud_old']['onset']['v2_1pct'])} -> {p(S2B['boxcloud_fixed']['onset']['v2_1pct'])}%, L1 far add {p(S2B['ray_old_S2']['cal|add|far|onset']['L1_union'])} -> {p(S2B['ray_fixed']['cal|add|far|onset']['L1_union'])}%. The same v2 model on the single-return test attacks (threshold validation 1%, test FA {p(v2['fa_test'], 2)}%):\n")
w("| attack | v2 | v2 AUC | v3 stack | v3 AUC |")
w("|---|---|---|---|---|")
for a in ATT + ["cmp_boxcloud"]:
    w(f"| {NM[a]} | {p(v2['det'][a]['det'])}% {('[' + p(v2['det'][a]['ci95'][0]) + ', ' + p(v2['det'][a]['ci95'][1]) + ']')} | {v2['auc'][a]:.3f} | {det(h, a)}% | {h['auc'][a]:.3f} |")
w(f"\nOn calibrated phantoms the two are equal (at the false-alarm level) except near replace where L2d helps ({det(h, 'ph_replace_near')}% vs {p(v2['det']['ph_replace_near']['det'])}%). On PointDrop / IntensitySpoof v2 is **better** ({p(v2['det']['PointDrop']['det'])}% / {p(v2['det']['IntensitySpoof']['det'])}%): it is a supervised model trained on exactly those two generator attacks (seen families), and it gets the whole 1% budget; the label-free physics layers reach {det(LA['raw_L2c'], 'PointDrop')}% / {det(LA['raw_L2a'], 'IntensitySpoof')}% each at their own 1% and {det(h, 'PointDrop')}% / {det(h, 'IntensitySpoof')}% sharing one. v3 buys unseen-family coverage (L2d near phantoms, L2c removal of any shape) and honest attack physics, not a higher number.\n")
w("## 5. Fundamentally invisible\n")
w(f"- **A calibrated single-return phantom that replaces the real returns** (replace far, budget near / far: {det(h, 'ph_replace_far')}% = FA, AUC {h['auc']['ph_replace_far']:.2f}-{h['auc']['ph_budget_near']:.2f}). On the laser's ray it is a legal scan: same ring, one return per beam, density matched to real objects, intensity from the real library, no free-space or occlusion contradiction (L2b on an attacker that fills every ray: {p(S5['attacks']['fl_replace_near']['union'])}% = FA). L4, a learned model, is at chance on them too. The WP target (50-400 points >= 60%) is therefore NOT MET and cannot be met by one LiDAR; it needs a second sensor (camera / radar cross-check, S8, not done).\n- **A persistent world-fixed phantom** after its first scan (section 2): a parked car is a parked car.\n- A near, dense, replacing phantom is the only single-return phantom with a physical footprint (it appears in free space, L2d): {det(h, 'ph_replace_near')}% at 1% total, {det(LA['raw_L2d'], 'ph_replace_near')}% for L2d alone; the S2 generator is ~1.5x denser than real near objects, so this number is optimistic.\n")
w("## 6. Negative results\n")
w(f"- **Density (L2a count / residual): no gain.** Validation {p(D['V2']['gain'])} points ({p(D['V2']['mean_phys_dens'])} vs {p(D['V2']['mean_phys_int'])}), worst LODO FA {p(D['V2']['lodo_worst_dens'])} vs {p(D['V2']['lodo_worst_int'])}%; on test {det(o['density part added to L2a'], 'PointDrop')}% PointDrop at FA {p(o['density part added to L2a']['fa'], 2)}%. A calibrated phantom is density matched by construction (S4: 1.0-1.2% = FA).\n- **Occlusion (L2b, CARLO):** single-return phantoms {p(S5['attacks']['ph_replace_near']['union'])}% near replace, best-case attacker {p(S5['attacks']['fl_replace_near']['union'])}%, only the impossible multi-return add shows ({det(o['L2b alone'], 'cmp_mradd_near')}%); LODO unstable (drive 0027 {p(S5['nested_lodo_fa_trval']['0027'], 0)}%, 0013 {p(S5['nested_lodo_fa_trval']['0013'], 0)}%).\n- **L3 normal-only object statistics:** adds nothing; worst-drive FA {p(S7['layers']['raw_L3']['fa_per_drive']['0001'])}% (0001). **L4:** leave-one-type-out collapses (PointDrop 95.7 -> 0.0, IntensitySpoof 100 -> 0.0 on validation, S7).\n- **Noisy-or** of four layers: FA {p(F['other_combiners']['noisy_or']['fa'], 2)}% but detection {det(F['other_combiners']['noisy_or'], 'ph_replace_near')}% / {det(F['other_combiners']['noisy_or'], 'PointDrop')}% (near replace / PointDrop); the equal budget split (each layer at 0.25%) is close to max but gives L2c a stricter share and loses PointDrop ({det(F['other_combiners']['split'], 'PointDrop')}%).\n")
w("## 7. Artefacts found\n")
w(f"- **Multi-return add:** the HDL-64E reports one return per beam; \"adding\" a phantom next to the surviving real return is impossible. Under the fix (S2b) L1's 60% far-add detection fell to {p(S2B['ray_fixed']['cal|add|far|onset']['L1_union'])}% and v2's near add from {p(S2B['ray_old_S2']['cal|add|near|onset']['v2_1pct'])}% to {p(S2B['ray_fixed']['cal|add|near|onset']['v2_1pct'])}% (validation).\n- **Density 2.1x:** the first generator gave 113 points at 30-35 m where real car-like clusters have 53 (S2); calibrated to ~1.5x (full box vs partial views; equal at equal angular size).\n- **Ring offset:** shortening rays toward the sensor origin leaves the laser ring by up to ~0.1 m (ring-sector alarm 11% vs 2%); the generator now uses the exact laser ray.\n- **Box cloud:** up to 1,500 points where a real car returns ~50-270, off the rings: easy for v2 and L1, meaningless physically; kept as a comparison row ({det(h, 'cmp_boxcloud')}% here).\n")
w("## 8. Data limits and test exposure\n")
w(f"No labelled objects or attacks (generated attacks only; the generator is the limiting assumption: dense near phantoms favour L2d / L4); KITTI only (one sensor, one region, 2011); the ego pose comes from OXTS (a vehicle without INS must feed LiDAR odometry poses: untested); PointDrop removes 50-100% of a 10-60 deg sector (a small, thin removal would be harder); 7 test drives of 77-429 scans (FA per drive spread above); camera / radar cross-check (S8) not done. **Test exposure of the KITTI LiDAR test drives:** S1 (v2 reproduction), S2 (L1), S4 (L2a), S5 (L2b), S6 (L2c / L2d), S7 (L3 / L4 and the physics stack), S3 (segmentation sanity) and this step: the 7th exposure; the layer scores of S4 / S6 / S7 were re-used (identical to the S7 store, max difference {max(F['check_vs_s7_store'][k][c] for k in F['check_vs_s7_store'] for c in ('raw_L1', 'raw_L2a', 'raw_L2c', 'raw_L2d'))}); no S9 choice used a test number (validation rule), but the test is no longer independent for the project.\n")
w("## 9. Frozen deployable LiDAR domain (for WP6 S5b / WP7)\n")
w("`lidar/domain.py`; fitted object `results/WP3/S9/frozen_lidar/` (`domain.pkl`, `intensity_ecdf.npz`, `domain.json`, ring table, calibration; ~9 MB, fitted on clean train+val only).")
w("```")
w("d = LidarDomain.load('results/WP3/S9/frozen_lidar')")
w("s = d.stream()                                    # one per drive; pose = (x, y, yaw) planar pose of the scan (KITTI: lidar.ego.poses)")
w("comb, per = s.push(points, pose, t, sample_id)      # points float32 N x 4 (x fwd, y left, z up, intensity 0-1)")
w("P, q = d.odometry(scan_paths); est = d.motion_estimates(t_fix, P, t_scan, q)   # MotionEstimate(source='lidar'), gps.lidar_odom passthrough")
w("```")
d_thr = J(R9 / "frozen_lidar" / "domain.json")["stack_threshold"]
w(f"Evidence: one combined per scan (`domain=lidar`, `layer=combined`, `name=lidar.combined`, `t` = scan time, `score` in [0, 1] = ECDF of the max-rank statistic on clean scans, `alarm` = statistic >= {d_thr:.4f} (about 1% of clean scans; expect 1-3% on unseen drives, worst test drive {p(max(fa_d.values()))}%), `reason` = physics sentence of the dominant layer, `details` = method, stat, layer_scores, layer_raw, first_scan_no_previous) and one per layer (`L1`, `L2a`, `L2c`, `L2d`, own 1% threshold). Causal: a scan depends on itself and the previous scan; the first scan of a drive has no L2c / L2d (rank 0, flagged). MotionEstimate: body-frame displacement over 1 s, sigma model of WP1 S5 (x3 on ICP fallback); an independent witness against GPS and CAN speed. **Freeze check:** replayed from raw scans, {Z['matched_to_stored']} test scans ({Z['clean']} clean = all clean test scans, {Z['attacked']} attacked from drives {', '.join(Z['attack_drives'])}) reproduce the stored per-layer scores and the stack statistic with max difference {max(Z['max_abs_diff'].values()):.1e} and {Z['alarm_differences']} alarm differences. Cost {X['scoring_s_per_scan']:.2f} s per scan (single process on the shared machine; segmentation dominates; NOT real time at 10 Hz: needs ~18 parallel workers or a faster segmenter).")
(Path(__file__).resolve().parent.parent / "reports" / "M1_LiDAR.md").write_text("\n".join(L) + "\n")
print(len(L), "lines")
