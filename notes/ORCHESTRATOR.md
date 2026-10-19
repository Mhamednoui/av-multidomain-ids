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
