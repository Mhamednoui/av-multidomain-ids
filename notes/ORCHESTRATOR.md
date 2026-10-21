# Orchestrator log (supervisor decisions, assignments, approvals)

## 2026-10-20: v3 set up (by the session that built v2)

Context for the next orchestrator session:
- User: Mhamed Nouira (EPT, thesis defended 17 Oct 2026). Works in VS Code on Windows.
- User preferences (keep): honest, non-overfitted numbers ("a credible 85% beats an inflated
  99%"); write everything down in files, never rely on chat memory; one step at a time with a
  stop for review; save the orchestrator's context (workers do the work, orchestrator monitors,
  assigns, evaluates); no GitHub push without explicit approval; ask before downloads (sizes).
- User's request for v3 (20 Oct): make each domain detector smarter with logic, physics and
  parallel models, because any model is only as good as its dataset; add a real V2X dataset;
  full system re-programming / retraining if needed; detailed roadmap so any model knows where
  it is and what to do; multi-agent work supervised by the orchestrator.
- History: v1 = thesis code (../codes). v2 = leak-free re-evaluation (../codes_v2;
  NOTES_v2.md = full log; RESULTS_v2.md = numbers). v2 is committed on a LOCAL branch `v2` in
  C:\Users\nouir\PFE_github\av-multidomain-ids (commits 24c7d75, a381336, abf7579, 2525467;
  tag thesis-v1), NOT pushed.
- Written today: START_HERE, RULES, ROADMAP, ARCHITECTURE, DATASETS, STATUS, ORCHESTRATION,
  workpackages/WP0-WP7, reports/README. Folders created (empty): common, gps, can, lidar,
  network, v2x, crossdomain, fusion, system, tools, tests, results, locks, notes, reports.
  NOT done yet (WP0 S1): git init, requirements.txt, any code.
- Dataset research done (20 Oct, web): see DATASETS.md. No download made for v3 yet.
  Disk free 51.9 GB.

Open questions for the user at the start of the next session:
1. Approval mode: user approves every step, or orchestrator approves routine steps?
2. Go for WP0 S1.

## Assignments and approvals
(orchestrator appends: date, WP, step, worker, decision, comment)

2026-10-19, user decisions (orchestrator session):
- Approval mode: orchestrator approves routine steps (after the ORCHESTRATION.md section 3
  checklist); the user is consulted for milestones, downloads, failures and contract changes.
- WP0 S1: on hold. Do not assign until the user says go.
- Workers: model Sonnet 5.5 (`model: "sonnet"` in the Agent call). Run several workers in
  parallel whenever the dependency order allows (max 3, one GPU-heavy at a time).
  ORCHESTRATION.md section 2 updated accordingly.
- 2026-10-19 user: "start, let the workers do all the work: downloads, programming, everything;
  I want results." => Downloads are pre-approved (orchestrator checks size/licence and keeps
  >= 15 GB disk free; logs each one here). Orchestrator approves steps and chains them without
  waiting for the user; user is told about milestones and real failures only.
  No GitHub push (still needs explicit approval).

| Date | WP | Step | Model | Decision | Comment |
|---|---|---|---|---|---|
| 2026-10-19 | WP0 | S1 | sonnet | ASSIGNED | first step |
| 2026-10-19 | WP0 | S1 | sonnet | APPROVED | env pins OK, commit 35966a3 clean. Doc fixes by orchestrator: S3 split + exact v2 B2 targets (threshold, FA, row-level AND run-level detection) pinned in WP0 file; download policy aligned (RULES 3.4, DATASETS, ORCHESTRATION: pre-approved, >= 15 GB free). Old "20 Oct" dates left as-is (system clock says 19 Oct). |
| 2026-10-19 | WP0 | S2 | sonnet | ASSIGNED | common contracts + tests |
| 2026-10-19 | WP0 | S2 | sonnet | APPROVED + S2b | 14/14 tests, commit 9ad97f7, toy AUC combined 0.955 vs best layer 0.746. Follow-up S2b sent to same worker: ECDF tail above max validation normal made strictly increasing and < 1 (saturation kills rank info in combiners). Then S3. |
| 2026-10-19 | WP0 | S2b | sonnet | APPROVED | 16/16 tests, commit 095a2c4, toy unchanged (51.5% @1%). |
| 2026-10-19 | WP0 | S3 | sonnet | ASSIGNED | v2 B2 regression, closes M0 |
| 2026-10-19 | WP1 | S0 | sonnet | ASSIGNED | download D15 OSM; S0 is data-only, does not need common/, so started in parallel with WP0 S3 to save time. S1 still waits for M0. |
| 2026-10-19 | WP2 | S0 | sonnet | ASSIGNED | download D11 (7.5 GB); same reasoning. |
| 2026-10-19 | WP1 | S0 | sonnet | APPROVED | commit 6cb0207, D15 OSM 35 MB, 23/23 drives inside bbox. Note for S6: extract has footways/paths, filter to drivable highway classes. |
| 2026-10-19 | WP5 | S0 | sonnet | ASSIGNED | D12 VeReMi Ext + D14 Tampa; D13 V2AIX subset decided by orchestrator: JSON only, <= 5 GB, whole recordings (split by recording later), no ROS bags. |
| 2026-10-19 | WP0 | S3 | sonnet | APPROVED, M0 CLOSED | commit fb5b6b1, 19/19 tests. All B2 alarm numbers identical to v2; threshold 6.658872 vs 6.657975 m (order statistic vs np.quantile interpolation, no test row in between). B2 FA 1.58% > 1% budget = inherited drive shift, baseline for WP1. |
| 2026-10-19 | WP1 | S1 | sonnet | ASSIGNED | GPS data layer |
| 2026-10-19 | WP1 | S1 | sonnet | APPROVED | commit 8ecdf70, 29/29 tests, B2 bit-identical on new stream; Doppler spoof / meaconing velocity-consistency 1.03x clean (physically consistent). B2 baseline run-level: Doppler 0.414, meaconing 0.471. Caveat: attack generator KITTI only; UAV onset 117 s is v2 estimate. |
| 2026-10-19 | WP1 | S2 | sonnet | ASSIGNED | L1 receiver sanity rules |
| 2026-10-19 | WP5 | S0 | sonnet | APPROVED (partial) | commit e3d6d5e. D12 VeReMi Ext 1.21 GB CC BY 4.0, 3.19 M msgs, 24,663 senders, class 0..19. D14 Tampa sample 1 day, 226 vehicles. D13 V2AIX: manual request form (user action needed: v2aix.ika.rwth-aachen.de -> Download -> form). S1 proceeds on D12+D14; V2AIX adapter added when access arrives. |
| 2026-10-19 | WP5 | S1 | sonnet | ASSIGNED | V2X data layer on D12+D14 |
| 2026-10-19 | WP1 | S2 | sonnet | APPROVED with documented miss | commit ef8deb4, 41/41 tests. 14 L1 rules. KITTI kinematic rules 0% FA but add ~nothing over B2 (AUC 0.847 -> 0.855); Doppler-vs-position is the useful one (B2+L1 AUC 0.860). UAV: alarm at first spoofed fix 118 s; A6 FA 3/118 = 2.54% vs 2% limit: NOT met, kept honest, no retune (3 vs ~2.4 expected = small-sample). Decision on the worker's question: UAV benign flight is the UAV calibration flight from now on (documented role, splits.json unchanged), spoofing flight stays the only UAV test. Jerk 50 m/s^3 is an engineering estimate: keep flagged. Clock rule: no data, report as not evaluated. |
| 2026-10-19 | WP1 | S3 | sonnet | ASSIGNED | L2a error-state EKF + NIS |
- 2026-10-19 23:25 user: workers at medium effort (`effort: "medium"` in every Agent call from now on). The 2 workers already running (WP5 S1, WP1 S3, resumed after a rate limit) keep their original setting until they finish.
| 2026-10-19 | WP5 | S1 | sonnet | APPROVED | commit b167bd3, 66/66 tests. VeReMi class map 0-19 (F2MD order) partially verified: primary source unreachable (web search 23:30 also inconclusive), but data checks agree (class 1 const pos, 5 const speed, 13-15 rate x2/x4/x4, 16 six pseudonyms). Accepted; class 12 and offsets 2/4/6/8 flagged weak. VeReMi split: 48 time blocks x 1800 s, 60/20/20, 0 sender overlap, no co-alive senders across parts; residual leakage (same city/day/generator) documented. Tampa: split by vehicle 136/45/45, only ~10 attackers per type in test -> wide CIs. Held-out attack types 6, 12, 17. No receiver id/pos in VeReMi combined CSV: acceptance-range / sudden-appearance checks cannot be evaluated on it (need per-receiver logs or D25 NextGen). |
| 2026-10-19 | WP5 | S2 | sonnet medium | ASSIGNED | L1 message checks |
| 2026-10-19 | WP1 | S3 | sonnet | APPROVED with documented misses | commit fa6f487, 83/83 tests. EKF consistent on val (NIS/dim 0.85, 5.4% > chi2-95). Strong on the new attacks at equal FA (oracle diagnostic): Doppler spoof 87% vs B2 40% of runs, meaconing 71% vs 46%; ties drift/accel/jump, loses freeze 79 vs 89. MISSES: clean test FA 2.59% (val threshold from 3 drives does not transfer), slow drift < 0.5 m/s 14% vs 60% target, AV-GPS meaningless (AUC 0.30), ablation FA clause. UAV met (118.0 s). Ungated EKF absorbs ~99% of a Doppler-consistent spoof -> gating/CUSUM needed. |
| 2026-10-19 | WP1 | policy | - | DECISION | Root cause of FA misses in S2/S3: thresholds calibrated on only 3 val drives. From S4 on (all GPS layers, and re-run for B2/L1/L2a in S8): calibrate thresholds with leave-one-drive-out over the 16 train+val drives (pooled out-of-fold clean scores -> tie-safe budget threshold); parameters that were tuned on train are re-tuned inside each fold or frozen beforehand. Test drives never touched. Report val-only and LODO side by side. |
| 2026-10-19 | WP1 | S4 | sonnet medium | ASSIGNED | CUSUM/SPRT + online odometry scale |
| 2026-10-19 | WP5 | S2 | sonnet medium | APPROVED | commit e14bdea. L1: DoS classes 13-15 99.7% of msgs, attackers caught < 0.5 s; position/speed falsification ~0% (expected). FA <= 1.0% VeReMi, 1.3% Tampa. E1b miss: Tampa DoS x2 5.7% (genuine Tampa has 20 Hz bursts) - kept, not retuned. Field-range quantile layer flags 49% of genuine senders: ablation device only, never deployable. Decision on question: do NOT approximate receiver positions with an RSU centroid (invented geometry); acceptance-range and sudden-appearance go to S3b once receiver positions exist (D25 VeReMi NextGen to be investigated; D13 V2AIX needs user form). S3 now = consecutive-beacon consistency, kinematic consistency, overlapping vehicles, OSM road plausibility (Tampa only if map available; VeReMi Luxembourg map not downloaded -> skip map check on VeReMi or report). |
| 2026-10-19 | WP5 | S3 | sonnet medium | ASSIGNED | L2 plausibility (no receiver-position checks) |
| 2026-10-19 | WP2 | S0 | sonnet | APPROVED | commit 980c3ad. D11 can-train-and-test: zip 1.5 GB MD5 ok, extracted 7.47 GB, 236 CSV (174 distinct: 62 byte-identical copies across sets), 193 M frames, CC BY 4.0, no DLC column, vehicles known per set only. Disk free 44 GB. |
| 2026-10-19 | WP2 | S1 | sonnet medium | ASSIGNED | CAN data layer; dedupe copies before splits; no cantools (use signal_extractions). |
| 2026-10-20 | WP1 | S4 | sonnet medium | APPROVED with documented misses | commit 2200ed6, 116/116 tests. cusum_dr (dead-reckoning branch, frozen when suspicious, learned odo scale) is the best GPS layer so far: vs B2 at ~equal FA, drift +31 pts, accel +19, Doppler spoof +29, meaconing +13; median delay 2 vs 5 fixes; absorbs only 9%/21% of spoof/meaconing vs 99%/97% for the EKF. LODO calibration: fixes EKF NIS FA (2.59 -> 0.44%) but not cusum_ekf (2.53%); cusum_dr 1.64% (goal 1.5%). Full stack with LODO: AUC 0.900 -> 0.922, FA 1.14% (B7 met). Misses: B4 (FA transfer), slow drift. Decision on question: slow-drift-within-30 s target is UNTESTABLE on KITTI (no test run has 30 s post-onset); do NOT concatenate runs (artificial seams). Re-test later on long real drives (D22 comma2k19, optional) or report as untested. Note for S8: hyperparameters were chosen on the pooled 16 drives, not nested per fold -> S8 must nest. |
| 2026-10-20 | WP1 | S5 | sonnet medium | ASSIGNED | LiDAR odometry ICP vs GPS, MotionEstimate (21/23 drives have velodyne) |
| 2026-10-20 | WP5 | S3 | sonnet medium | APPROVED (partial) | commit ec091d2. L2 F2MD checks: random pos/speed (+offset), disruptive, DoS random/disruptive caught 90-100% of msgs on both datasets; ConstSpeed 96/54, ConstPos 86/15. Missed: ConstPosOffset, EventualStop, DelayedMessages, per-message-pseudonym Sybil 18/19. Ablation @1%: VeReMi 45.1 -> 72.4%, Tampa 18.4 -> 53.3%. FA: VeReMi met; Tampa missed only via map_road (5.5%, 2 vehicles ~27 m off mapped roads), non-map union 0.98%. |
| 2026-10-20 | WP5 | decisions | - | DECISION | (1) Tampa coreData_id is per RSU, not per vehicle: the S1 by-id split LEAKS. Fix now (S1b): deduplicate the same over-the-air message heard by several RSUs, link ids into physical tracks where possible, and re-split Tampa by time block with buffer gaps (same policy as VeReMi), so no vehicle-moment is on two sides; re-inject attacks and re-run S2 + S3 Tampa evaluations; report old vs new. (2) map_road stays out of the deployable Tampa union (unmapped/private roads give real FA); keep it as a separate soft-evidence layer for the combiner in later steps; do NOT widen road classes after seeing test. |
| 2026-10-20 | WP5 | S1b | sonnet medium | ASSIGNED | Tampa dedupe + re-split + rerun S2/S3 Tampa |
| 2026-10-20 | WP5 | S1b | sonnet medium | APPROVED (partial) | commit a623ff5, 131/131 tests. Tampa: 43% of rows were RSU copies; 226 ids = ~38 physical vehicles; old test leaked (68% of rows had a copy in another part). New time-episode split (splits_tampa_v2.json; seeds 42-47 failed pre-fixed size criteria, 48 used: disclosed). Mean detection L1+L2 over 19 types: old 54.4% @7.6% FA -> new 44.7% @1.8% FA. heading_rate FA 2.7% vs 2% rule: miss kept. New test set = 3 vehicles, 2 attackers/type: too small for statistics. D14 row in DATASETS.md corrected by orchestrator. |
| 2026-10-20 | WP5 | S0b | sonnet medium | ASSIGNED | get more Tampa BSM days from public data.transportation.gov (no login), cap ~3 GB; if sandbox registration needed -> stop, user action. WP5 S4 (per-sender Kalman) next, VeReMi first. |
| 2026-10-20 | WP5 | S0b | sonnet medium | CLOSED, NOT MET | commit 3eb625f. No public no-login source of more Tampa BSMs (Socrata sample fixed at 34,464 rows; S3 buckets 403). User action: ITS DataHub data request (text in reports/WP5_S0b.md). Until then Tampa = illustration (3 test vehicles); VeReMi = benchmark with statistical power. |
| 2026-10-20 | WP5 | S4 | sonnet medium | ASSIGNED | per-sender Kalman tracker, VeReMi primary |
| 2026-10-20 | WP2 | S1 | sonnet medium | APPROVED | commit 5d7d568, 133/133 tests. ROAD 41/41 captures match v2 (27.4 M frames, 62,547 injected); Car-Hacking matches v2 split; D11 236 files, byte round-trip exact, no duplicate hash across sides. Corrections (DATASETS.md section 5 updated by orchestrator): D11 inversions up to -7.9 ms next to injected frames (dt sign must never be a feature), set_01/test_04 is Traverse not Silverado. |
| 2026-10-20 | WP2 | decision | - | DECISION | D11 calibration regimes, report both from S2 on: (a) ZERO-SHOT: thresholds from the training vehicle's normal traffic only, applied to the unknown-vehicle tests; (b) ON-VEHICLE: a short clean calibration period of the target vehicle (e.g. first N minutes of its attack-free frames, from files / time ranges disjoint from the scored test frames, N fixed before results). Spec rules are per-vehicle by design, so (b) is the realistic deployment; (a) shows transfer. Val hold-out for model selection stays on the training vehicle. |
| 2026-10-20 | WP2 | S2 | sonnet medium | ASSIGNED | L1 spec rules per vehicle |
| 2026-10-20 | WP1 | S5 | sonnet medium | APPROVED with documented misses | commit f42e77d, 144/144 tests. LiDAR ICP odometry 23/23 drives (0001, 0015 from ../codes/data/Depth, read-only): test 1.58% transl, 0.0069 deg/m. Misses: C2c 1 s disp err 0.129 vs 0.10 m; C3 2-sigma coverage 89.4 vs 90%; C4 FA 1.64 vs 1.5%; C5 Doppler spoof 60% / meaconing 61% vs 75% (limited by simulated receiver noise, not LiDAR). Primary L2d layer adds ~0 over S4 stack; all 7 L2d layers add AUC 0.922 -> 0.927 under LODO. cusum_lidar 10.1% FA: rejected. MotionEstimate published (C8 met). Decisions: (1) MotionEstimate displacement = body frame (ARCHITECTURE.md clarified, not a contract change). (2) 75% target for Doppler/meaconing is KEPT for S8; S8 reports it honestly plus delay; targets are not lowered after seeing results. |
| 2026-10-20 | - | usage | - | PAUSE | User at ~85% of usage limit. No new worker assignments until the user says go. Running: WP2 S2, WP5 S4 (let them finish). Cost: each worker starts at ~30K tokens (system prompt + tools + doc reading list) and ends at 60-280K. Next time: 1 worker at a time, trimmed reading list (only WP file, own notes tail, previous report). |
- 2026-10-20 user: do not reduce quality; choose model/effort per task instead. ORCHESTRATION.md section 6 written (tiers T1-T4, per-WP brief files, 2 workers max). First worker of each WP after this date also writes notes/WP<n>_brief.md.

## HANDOFF 2026-10-20 night (user shut down; usage limit hit, resets 04:20 Africa/Tunis)

State:
- Approved: WP0 S1-S3 (M0 closed); WP1 S0-S5; WP2 S0-S1; WP5 S0, S1, S1b, S2, S3 (S0b closed not met).
- Interrupted mid-step (work on disk, NOT committed; do not delete):
  - WP5 S4 (per-sender Kalman, v2x/l3.py, tests/v2x/test_l3.py, tools/WP5_S4_*, results/WP5/s4_*,
    reports/WP5_S4.md draft): was writing the report.
  - WP2 S2 (CAN spec rules, can/l1.py, can/l1_exp.py, tools/WP2_S2_*, results/WP2/s2_*): mid-run.
  Resume: if this same session is alive, SendMessage the two workers. If a new session: launch a
  fresh worker per step (WP5 S4: T2 sonnet/medium; WP2 S2: T2 sonnet/medium) telling it to
  continue from the files on disk (read its notes file tail + draft), not restart.
- Next after those: WP1 S6 (T2), WP1 S7 (T3), WP1 S8 (T3, M1-GPS); WP5 S5 (T3), S6 (T3, M1-V2X);
  WP2 S3+; wave 2 downloads WP3 / WP4 S0 (T1). Max 2 workers. New workers write notes/WP<n>_brief.md.
- User actions pending: (1) V2AIX access form v2aix.ika.rwth-aachen.de; (2) optional ITS DataHub
  request for full Tampa BSM (text in reports/WP5_S0b.md).
- Approval mode: orchestrator approves routine steps; downloads pre-approved (>= 15 GB free);
  no GitHub push. Model/effort per task: ORCHESTRATION.md section 6.
| 2026-10-21 | WP5 | S4 | sonnet medium | APPROVED (partial) | commit f79b65c, 144/144 tests. L3 per-sender CV Kalman + NIS + CUSUMs + track_birth. VeReMi: mean detection 19 classes 68.0 -> 78.4% at ~1% FA, AUC 0.845 -> 0.907; DataReplay 98%, GridSybil 73%, EventualStop only 11%, ConstPosOffset ~1%. Class 12 (48%) is an ARTEFACT of the zero placeholder jump, not delay detection: must be reported as such in S6/M1. Per-message Sybil 18/19: sender-level 98/100% at 2.9% genuine senders flagged (birth check). Tampa: kf_cusum_lo FA 13.5% (real standing vehicles repeat exact positions = simulation artefact in VeReMi). Decisions: (1) kf_cusum_lo DROPPED from the deployable L3 union, kept as diagnostic (reason: real-data FA, disclosed). (2) road-occupancy prior: not now; WP5 S5 supervised model may use plausibility features instead. |
| 2026-10-21 | WP1 | S6 | sonnet medium (T2) | ASSIGNED | OSM map matching |
| 2026-10-21 | WP2 | S2 | sonnet medium | APPROVED with documented miss | commit 52752aa, 154/154 tests. ROAD (frozen run 1 = verdict): all 5 v2-detected captures caught 0.17-0.93 s, reverse driving 0 alerts, masquerade missed (expected), FA 3.4% windows (122/h) vs 1%: NOT MET (v2 timing model had 0 FA -> spec rules alone are worse on FA; combiner must handle). Run 2 (IQR periodic test) chosen after test exposure: diagnostic only. Car-Hacking met (DoS/Fuzzy 100%, RPM/Gear 99.5% @1.0%). D11: zero-shot ID/DLC rules alarm ~100% on unknown vehicle (rules do not transfer); on-vehicle 1-min calibration FA 1.2-5.9% (one cell 20%), recall 0.78-1.0. Incident: a 39 GB cache briefly filled C:, deleted; cache now 3.4 GB in ../data_extra/WP2_S2_cache. |
| 2026-10-21 | disk | - | - | ALERT | C: free 14 GB (< 15 GB floor) on 2026-10-21; ../data_extra = 25 GB total, so ~30 GB went elsewhere since 2026-10-19 (44 GB free). Investigating (recycle bin, large recent files). No downloads until resolved; workers must keep caches <= 1 GB. |
| 2026-10-21 | WP5 | S5 | sonnet high (T3) | ASSIGNED | L4 supervised model on plausibility features |
