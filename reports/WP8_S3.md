# WP8 S3: LiDAR in the stack (PointDrop) and speed

Date: 2026-11-03    Worker: sonnet (high, T3)

## Summary (<= 40 lines)
- Goal: keep PointDrop alive inside the LiDAR stack (v3: 87 % alone, 27.6 % in the stack) and cut the 1.2-1.8 s per scan to <= 0.1 s, stream == batch.
- Rules: notes/WP8_v31.md "S3 pre-registration" (grid + selection rule) and rounds 2 and 3 (each logged and committed BEFORE its numbers). Everything judged on V31_val
  (10 KITTI drives, 2,085 scans, 6,255 attacked scans in 9 kinds, 30 PointDrop episodes); no H31 file opened (assert_not_h31 in every build).
- Protocol is stricter than v3's S9: the layer references (not only the stack) are leave-one-drive-out over 23 drives. Under it the v3 rule (max of ranks, 1 %)
  gives clean FA 2.70 % (drive 0027: 16.6 %) and PointDrop 4.3 %. The v3 S9 "FA 1.18 % / PointDrop 27.6 %" used in-sample layer ranks; the frozen v3 domain on a
  25-scan PointDrop sample alarms 12 % in the stack: the dilution is real, and larger than v3 reported.
- Finding 1 (FA): the L2a COUNT statistics (cnt_int_*) are drive dependent (0027: 20 % of scans over the 99.75 % quantile of the other drives). Fix: L2a uses
  (int_hi, int_lo, cnt_int_hi) (`tail2h`); clean FA 0.96 % (worst drive 3.2 %).
- Finding 2 (power per budget): the L2c Poisson-shortfall statistic (miss_z20) is far stronger at small budgets than the v3 ratio statistic (57 % vs 2 % at 0.25 %
  budget); a multi-window version (z at 10/20/30/45/60 degrees, `zmulti`) is better still.
- Selected by the registered rule (round 3, budget B = 1 %): `tail2h|zmulti|E7` = union of layer alarms with per-layer budgets L1 0.05 / L2a 0.20 / L2c 0.45 / L2d 0.30 % of B.
- Result at B = 1 % (LODO, V31_val): FA 0.96 %; PointDrop 67.5 % [64.0, 70.0]; IntensitySpoof 61.2 (v3 rule 61.3); near replace 23.6 (24.5); far / budget phantoms 1.0
  (= FA); every kind within 2 points of the v3 rule (largest drop 1.2, box cloud). PointDrop 3 s episodes 23/30 (76.7 %), false-episode rate 7.7 % (v3 rule 17/30, 10.8 %).
- Exploratory B = 1.25 % (labelled; not the registered operating point): FA 1.30 %, PointDrop 74.4 % [71.2, 76.4], other kinds within 2 points; episodes 22/30.
- Speed: fast statistics are IDENTICAL to v3 (frozen v3 vs fast path, 150 scans: max |diff| 0.0 on all four layers, 0 alarm differences). The exact v3 clustering is the
  main cost (2.4 s on dense scans); v3.1 clusters voxel (0.1 m) centroids (L2a max |diff| 0.018, stack statistic 0.006, 0 alarm differences). Median 141-178 ms per
  scan (machine shared), p99 240-265 ms: 8-12x faster than v3, but L1 (median <= 100 ms) NOT MET.
- Stream == batch: exact (0 alarm mismatches, max |diff| 0.0, 1,113 scans).

| rule | verdict |
|---|---|
| L1 speed (median <= 0.10 s, p99 <= 0.25 s) | NOT MET (median 0.141-0.178 s, p99 0.24-0.265 s) |
| L2 stream == batch | MET (0 mismatches, diff 0.0) |
| L3 PointDrop >= 70 % per scan at 1 % and episodes >= 80 % | NOT MET at B = 1 % (67.5 %, 76.7 %); per scan MET at B = 1.25 % (74.4 %), episodes not (73.3 %) |
| L4 non-inferiority (every kind >= v3 rule - 2 points, FA in [0.5, 1.5] %) | MET (FA 0.96 %; min margin: box cloud -1.2) |
| L5 phantoms (G10) | MET (far / budget at FA; near replace 23.6 % explained by L2d: a surface appearing in free space) |

## Acceptance rules (as registered, before the results)
notes/WP8_v31.md, section "2026-11-03 S3 (LiDAR) pre-registration ..." (grid: alpha family x L2c statistic + W0; selection: feasible = FA in [0.5, 1.5] % and every kind
>= M0 - 2 points, then maximise PointDrop, G8 order); "S3 round 2" (L2a statistic set, budget shares E1-E6); "S3 round 3" (multi-window z statistics, E7-E8, B = 1.25 %
as exploratory). Round 1 and 2 outcomes are kept (candidates_r1/r2.json).

## What was done
- lidar/fast.py: statistics with one ring assignment per scan (windowed ring search, common mode on the far points only, bit-identical to v3), cluster labels without the
  object table, voxel clustering (flag `vox`), radix-sort range images, ground height, IntensityScorer, extra L2c statistics z10/z30/z45/z60/zg20.
  lidar/combine31.py: Union combiner with per-layer budgets (alpha / E shares / water-filling). lidar/domain31.py: Domain31 (stream, save / load, Evidence contract as v3).
  v3 files (lidar/domain.py, segment.py, geometry.py, background.py, combine.py) untouched.
- tools/WP8_S3_{lib,build,an,eval,freeze,speed,equiv,extra,profile}.py; tests/v31/test_fast.py (9), test_domain31.py (2). Suite 514 pass / 0 fail / 2 skip;
  `run_all.py --check` passes (v3 frozen objects unchanged).
- Records: results/WP8/S3/parts (23 clean drives, 10 attack / PointDrop-episode drives; not committed, rebuilt in 16 min with tools/WP8_S3_build.py).
- Attacks: the S4 set (seeds [83, drive, i], stride 3, attacked scan vs clean previous scan); PointDrop episodes (new): 3 per drive, fixed sector / fraction, fresh
  thinning each scan, seeds [101, drive]; step 1 vs the clean previous scan, later steps vs the attacked previous scan.

## Results (results/WP8/S3/*.json)
Selected (candidates_r3.json, key `tail2h|zmulti|E7`; v3 rule = `M0|all4`, same OOF protocol; detection %, 95 % CI = bootstrap over the 10 drives):

| attack | v3 rule | v3.1 B = 1 % | v3.1 B = 1.25 % (exploratory) |
|---|---|---|---|
| clean FA (worst drive) | 2.70 (16.6) | 0.96 (3.2) | 1.30 (3.2) |
| PointDrop | 4.3 [0.4, 9.2] | 67.5 [64.0, 70.0] | 74.4 [71.2, 76.4] |
| IntensitySpoof | 61.3 [49.6, 71.1] | 61.2 [49.7, 71.2] | 61.3 [49.8, 71.3] |
| near replace | 24.5 [19.6, 32.6] | 23.6 [19.2, 30.4] | 23.7 [19.4, 30.4] |
| far replace / budget near / budget far | 2.6 / 2.4 / 2.4 | 1.0 / 1.0 / 1.0 | 1.2 / 1.2 / 1.2 |
| box cloud* / multi-return add near* / far* | 8.5 / 25.8 / 62.3 | 7.3 / 25.3 / 61.7 | 7.5 / 25.6 / 61.9 |
| PointDrop episodes (3 s) | 17/30 (FER 10.8 %) | 23/30 (FER 7.7 %) | 22/30 |
| AUC of the stack statistic, PointDrop / IntensitySpoof / near replace | 0.948 / 0.904 / 0.828 | 0.966 / 0.920 / 0.834 | - |

Per drive PointDrop (B = 1 %): 0.54 (0052) ... 0.73 (0027). Layer alone at its budget share (extra.json): L1 cmp_mradd_far 61.2 only; L2a IntensitySpoof 60.7; L2c PointDrop 67.3;
L2d near replace 23.0; union without L2c: PointDrop 0.3; without L2a: IntensitySpoof 0.6; without L2d: near replace 0.9; without L1: only the impossible multi-return add far
falls (1.2). Round 1 (alpha family, v3 statistics, all four L2a statistics): no candidate with FA <= 1.5 % (drive 0027); round 2 (L2a sets): only the degenerate W0 candidate feasible,
PointDrop 4.7; round 3: 6 feasible (E7 / E8 shares).
Speed (results/WP8/S3/speed_light.json, speed_load_first.json): 1,113 V31_val scans, one process, push() only: median 178 / 171 ms and p99 265 / 262 ms in the two clean runs
(other workers present), 141 ms median in a profiling run on drive 0011; file read 0.8 ms. Under load: 178 ms. v3: 1.16 s (median, sample) to 1.84 s (S9).
Regression (equiv.json): fast exact path vs frozen v3 on 75 clean + 75 attacked scans: 0.0 difference on L1, L2a, L2c, L2d; voxel: L2a max 0.018.

## Problems, surprises, open questions
- The v3 S9 in-stack numbers (FA 1.18 %, PointDrop 27.6 %) are not reproducible under leave-one-drive-out layer references: FA 2.70 %, PointDrop 4.3 % for the same rule. S7 must
  compare v3 and v3.1 on H31 with frozen v3 as is (G2), and say that the v3 S9 values were optimistic.
- Operating point: PointDrop >= 70 % costs ~1.1-1.25 % of the budget with the current statistics. Supervisor decision needed: accept B = 1.25 % for LiDAR (frozen_lidar31_B125, FA 1.30 %)
  or keep 1 % and L3 NOT MET (67.5 %). Episodes stay below 80 % in both: a sensor-fixed removal is invisible to L2c after the onset scan (the previous scan is thinned in the same sector).
- Speed: 0.14-0.18 s. Remaining cost (profile, ms): ring assignment ~35, voxel clustering ~35, two range images ~19, L1 statistics 5, tiles 5, motion 3. Reaching 0.1 s needs compiled kernels
  (numba 0.60 is installed in the tf env but is not in requirements.txt: needs the user's approval) or approximations that change the statistics (float32 images, sub-sampled common mode)
  and a rebuild (25 min). Not done.
- Frozen domain size 58 MB (intensity cells of 1.2 M tiles); not committed (sha256 in the journal). domain31.json files committed.
- Selection used V31_val for 3 rounds (27 + 244 + 173 candidates in the three rounds): the PointDrop figure is optimistic by selection; S7 (H31, once) is the unbiased number. Candidates' CIs are over 10 drives.
- Units: PointDrop episodes are a new generator (persistent, sensor-fixed); it is not the same material as the v3 episode set.

## Files
results/WP8/S3/{candidates_r1,r2,r3,selection_r1,r2,r3,extra,equiv,speed_light,speed_load_first}.json, equiv_rows.jsonl, frozen_lidar31/ (domain31.pkl sha256
0a897b32615e62ea8dd9562c80771adc6010eecaf9d9bdbcbfba21b98124665c), frozen_lidar31_B125/ (700d9483bffe04aa5922f5f2f40c2b76603e550405ab0c3c3069761a925a6639),
results/WP8/scores/S3/lidar_val.npz (per-scan layer scores, statistic, alarm, labels, groups for the selected config and the v3 rule, 9,230 scans), logs results/WP8/logs/S3_*.log.

## Proposed next step
S2 / S7 consume `Domain31.load('results/WP8/S3/frozen_lidar31')` (stream().push(points, pose, t, id) -> combined Evidence + 4 layer Evidence). Decide B = 1 % vs 1.25 % first.
