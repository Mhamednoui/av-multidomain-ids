# WP7 System: working log (append only, dated)

## 2026-10-22 S1 start: streaming runtime (started early by the supervisor; engineering step, no detection verdict)

### Inputs read
RULES.md, STATUS.md, workpackages/WP7_system.md, ARCHITECTURE.md, ORCHESTRATOR "WP6 decisions" (point 3: S1 needs only the contracts and the
frozen domains: GPS, CAN, V2X now; NET when frozen; LiDAR placeholder = WP3 S1 v2-baseline layer, labelled interim), reports/M1_GPS.md s.8,
M1_CAN.md s.9, M1_V2X.md, notes/WP1/2/5/6 briefs.

### State of the frozen domains found (decides what is wrapped)
- GPS: `gps/domain.py` GPSDomain (frozen object results/WP1/frozen_gps). Whole-run API (prepare(df) + score(df)); every layer (EKF, CUSUMs, dead reckoning) is
  a per-run loop, causal, no step() entry point.
- CAN: `can/domain.py` CanDomain (results/WP2/s7_domain). Whole-capture API score_capture(t, ids, dlc, B); windows are the integer second of the
  running-max clock; causal (WP2 test), no incremental entry point.
- V2X: there is NO domain object. The frozen physics-only stack L1+L2+L3 of M1_V2X exists as layers (v2x/l1, l2, l3) plus tools/WP5_S6_run.py (raw columns via
  v2x.l4.message_scores, per-layer ECDF on genuine validation rows, combiner "max" chosen for the stack without L4 on validation halves, threshold 1% of genuine
  validation). WP7 therefore builds `system/v2x_runner.py V2XPhysicsDomain` by the same recipe (fit on VeReMi validation minus held-out types 6/12/17, like S6)
  and checks that it reproduces the S6 layer thresholds and the S6 validation false-alarm number.
- Cross-domain: crossdomain/consistency.py WhichDomainLies (+ witness.py SigmaModel / to_grid). No fitted object is saved by WP6 (S3 not started). WP7 fits an
  engineering object on the DEV (train+val) clean KITTI rows of the WP6 S2b cache (the S2b choice: instantaneous |z|, domain-level blame). It is a runtime-test
  object, NOT the WP6 verdict model.
- Network: network/domain.py exists but is untracked (WP4 S7 running), reports/M1_NET.md does not exist: NOT frozen -> labelled placeholder runner, same interface.
- LiDAR: WP3 S1 retrained v2-baseline (XGBoost on the 429-dim temporal descriptor, ../data_extra/cache_v3/WP3/retrained_deployed.json) = "interim".

### Design decision (important)
The frozen detectors are whole-run / whole-capture vectorised programs; none exposes a per-sample step. Rules forbid modifying other WPs' folders. So each runner is
STATEFUL in the sense that it keeps the stream so far (per drive / capture / sender context) and, when a sample (or a window) completes, calls the frozen
batch code on the PREFIX and emits the Evidence of the new sample. Because the frozen layers are causal, the Evidence of sample k computed from the prefix up to k
must equal the Evidence computed on the whole run. That equality IS the test (A1) and the truncation test (A2) checks that nothing later is read.
Consequences, stated up front: (1) exactness by construction + testable; (2) latency of GPS / CAN grows with the length of the run/capture so far (the prefix is
re-scored) - it is an UPPER BOUND of what an incremental implementation would cost; per-sample cost of an incremental version is NOT measured here; the runtime
therefore reports latency as a function of prefix length too. (3) An optional follow-up is an incremental entry point in the frozen domains
(reports/REQUEST_WP7_incremental_entry_points.md); not needed for correctness.
V2X (per message) uses a bounded context instead of the whole stream (own track history + other tracks that the layers can see: first and latest message of
tracks heard in the last 1 s [overlap] and births of the last 10 s [track_birth]); exactness is again tested against the whole-table batch.
Known tie caveat: v2x.l3.birth_density counts births with EQUAL timestamp that arrive later in row order; a strictly causal stream cannot. VeReMi validation has
0 equal timestamps, so the test is unaffected; the runner counts such events (`tie_events`) and reports them.

### S1 acceptance rule (written BEFORE any result; judged on VALIDATION data only, no test set is read or scored in S1)
Streaming = the runner fed one sample at a time (GPS fix, CAN frame, V2X message, LiDAR scan, 1 s witness step); batch = the frozen batch code on the same inputs.
- A1 exactness (per domain): the Evidence sequences are identical: same count, same sample_id, same alarm flag on 100% of samples, same reason string on 100% of alarms,
  max |score difference| <= 1e-9 (GPS, CAN, V2X, cross) and <= 1e-6 (LiDAR: float32 model/features). Data: GPS >= 9 validation runs from the 3 validation drives
  (clean + attacked); CAN >= 4 validation captures (>= 2 attack, >= 1 ambient); V2X >= 2 validation time blocks (all messages of the block, or a time slice of >= 3,000
  messages of it, with attacks of >= 8 classes); cross >= all 210 validation-drive runs of the S2b cache at residual level AND >= 6 runs at MotionEstimate level
  (frozen producers -> aligner -> statistic); LiDAR >= 30 validation scans from >= 2 drives. Any single mismatch = A1 NOT MET for that domain (reported with the cause).
- A2 causality by truncation: for each domain, at >= 3 truncation points per stream, the Evidence emitted for the truncated stream equals the first Evidence of the full
  stream, exactly (alarm, reason, score <= tolerance of A1). (CAN windows: all windows completed in the truncated stream.)
- A3 reset: after reset(), feeding stream B gives exactly what a fresh runner gives on B (>= 1 pair per domain).
- A4 latency: per sample and per domain, median / p95 / p99 (ms) over >= 3 repetitions, spread across repetitions reported (the machine is loaded by other workers:
  numbers are an upper envelope of the quiet-machine value). Compared with the v2 references (network ~1 ms, CAN ~0.05 ms/frame, GPS ~0.8 ms, LiDAR ~23 ms/scan,
  fusion ~0.3 ms). No pass/fail against the v2 numbers; the pre-registered real-time check is p99 < sample period of the stream (GPS fix 1 s, CAN window 1 s,
  V2X message 0.1 s, LiDAR scan 0.1 s, witness step 1 s); a miss is reported, not hidden, and gives the reason.
- A5 bus: every Evidence on the common bus has stream time and wall time; merged order is by stream time; per-domain counts equal the runner outputs.
- A6 labels: the LiDAR and network runners carry interim / placeholder labels in every Evidence.details["status"] and on the runner object.
Not part of S1: any detection rate, any test-set scoring, any threshold re-fit (all thresholds are the frozen ones; the only objects WP7 fits are the V2X physics-only
domain and the cross-domain runtime object, both by the documented recipes above, on validation / dev data).

### Log

#### 2026-10-22 build and checks (all numbers from results/WP7/S1_*.json, S1_tables.md)
- Code: system/{bus,runner,gps_runner,can_runner,v2x_runner,cross_runner,placeholder_runners}.py. Runner contract: reset(key), push(sample) -> list[Evidence], flush(), LatencyLog per call, optional EvidenceBus, status label
  ("frozen" / "interim" / "placeholder", written into Evidence.details["status"] for the last two).
- V2X domain object built by tools/WP7_S1_v2x_fit.py (VeReMi validation minus types 6/12/17, 256,586 rows, 161,426 genuine): layer thresholds equal results/WP5/s6_veremi.json to 0.0, combined validation FA 0.009967 equals S6
  (S1_v2x_fit.json). The 32 MB domain.json is NOT committed (regenerate with: python -I -u -W ignore tools/WP7_S1_v2x_fit.py, about 1 min).
- Cross runtime-test object (tools/WP7_S1_cross_fit.py): SigmaModel(linear) per edge + WhichDomainLies(inst, domain-level blame) fitted on the WP6 S2b dev cache clean rows (150 runs, 3,221 rows); in-sample on purpose (runtime object, not the verdict).
- LiDAR interim calibration (tools/WP7_S1_lidar_fit.py): 549 normal validation scans, raw threshold 0.9755272650718689 = WP3 S1 val_fpr_0.01 threshold.
- A1 (stream == batch): GPS 210 val runs 3,990 fixes + 63,840 per-layer Evidence, CAN 6 val captures 672,789 frames 274 windows + wheel-speed MotionEstimates, V2X 4 val blocks 10,906 messages 12 attack classes
  (+130,872 per-check Evidence), cross 360 val runs at residual level (6,840 steps) + 9 runs through the 4 frozen producers (168 steps), LiDAR 34 scans (features identical to the WP3 S1 cache, max diff 0.0):
  0 alarm / reason mismatches everywhere, max score difference 0.0.
- Finding fixed during the run (not a tuning step): the cross runner first pruned its source buffers (keep_s = 4 s). The interval means of crossdomain.witness.to_grid are differences of cumulative sums,
  so z moved by ~1e-13 and one ECDF step flipped (score 3.7e-4, 11 of 168 steps, no alarm change; the calibration set contained the very same values: in-sample). Fix: keep the whole history by default (keep_s=None);
  the bounded variant stays an option and its mismatch count is reported in S1_cross.json. Lesson: ECDF scores are step functions, a 1e-13 difference can show as 1e-4.
- A2: GPS 72, CAN 18, V2X 12, cross 36, LiDAR 3 truncation checks (batch prefix == batch full and stream prefix == stream full): all identical. A3: reset identical in all 5.
- A4 latency (median / p95 / p99 ms, pooled over 3 repetitions, machine shared): GPS fix 31.6 / 71.6 / 89.2 (median spread over reps 31.4-32.0); CAN frame 0.0032 / 0.0057 / 0.0084, amortised 0.044 per frame;
  CAN window 96.0 / 186.0 / 212.3; V2X message 20.7 / 46.9 / 59.8; cross step 6.3 / 13.7 / 15.9 (residual-level step 0.18); LiDAR interim 32.1 / 51.6 / 59.6; network placeholder 0.0019; bus publish 7.2 us.
  Real-time check p99 < period: yes in all domains. Growth with context is real (GPS 18.7 -> 40.7 ms median over run length 0-24 fixes, CAN window 54 -> 137 ms over 5k-98k frames, V2X 9 -> 37 ms over 1-229 context rows).
- A5 / A6: bus counts equal runner outputs, merged order by stream time, labels present (S1_bus.json).
- Wording correction: the rule says "all 210 validation-drive runs of the S2b cache" for the cross level; 210 is the number of GPS-stream val runs. The S2b cache has 360 val-part runs; all 360 were used.
- Tools: tools/WP7_S1_run_all.sh runs gps, can, cross, v2x, lidar one at a time (latency); WP7_S1_bus.py; WP7_S1_report.py writes S1_acceptance.json, S1_tables.md, reports/WP7_S1.md.
- Pitfalls: bash heredocs with long text fail in this harness (use the Write tool for files with docstrings); python -I needs explicit sys.path inserts; the V2X fit needs about 3 GB RAM (VeReMi CSV load 47 s).
- For the next reader: if WP1 / WP2 / WP5 later provide incremental entry points (reports/REQUEST_WP7_incremental_entry_points.md), only the _push of the corresponding runner changes; the stream == batch tests stay as they are.

## 2026-10-24 S3 start: run_all.py, make_report.py, RESULTS_v3.md, README (started early by the supervisor; engineering step, NO test set is scored)

Inputs read: RULES.md, STATUS.md, workpackages/WP7_system.md, notes/WP7_brief.md, ROADMAP.md, ORCHESTRATOR DECISION rows (2026-10-24: corrected thesis claim; V2X sim-to-real headline; M2 closed NOT MET;
novelty layer dropped), reports/M1_GPS, M1_CAN, M1_NET, M1_V2X (+V2AIX addendum), M2. JSON keys located with a small structure-printer; no result was recomputed.

### S3 acceptance rule (written BEFORE the generated report exists)
- R1 run_all.py: (a) `--list` prints every step (id, WP, kind, dependencies, data needed with DATASETS id) and exits 0 without importing heavy packages; (b) `--dry-run` prints the exact commands in
  execution order and runs nothing; (c) execution order is a valid topological order of the declared dependencies and WP order is WP0 -> WP1..WP5 -> WP6 -> WP7 (tested); (d) every script a step names
  exists; no command or path touches ../codes or ../codes_v2 for writing, nothing is downloaded (missing data is printed with its DATASETS id and the step is SKIPPED); (e) default run executes no refit
  and no test-set scoring (those kinds need --refit, and the plan prints that each one adds a labelled test exposure); (f) `--only <WP>`, `--from <step>` select consistently with dependencies;
  (g) `--check` is read-only: frozen objects load, thresholds/aliases in the frozen objects equal the saved verdict values, saved freeze-check files report 0 score difference / 0 alarm mismatch.
- R2 make_report.py: RESULTS_v3.md is generated from results JSON only; running it twice gives byte-identical output; every number in the body is rendered through a tracker and the appendix lists
  (file, key path) next to each of them; a scan of the body finds no untracked standalone number; closed milestones have no missing key; milestones whose result JSON does not exist yet
  (M1-LiDAR, M2 addendum, M3 simulation) render "PENDING" with the file name that will fill them. Verdicts (met / not met) are read from the saved acceptance JSON where one exists, otherwise
  computed from saved numbers against the thresholds of the pre-registered rule (written next to the verdict with its source report).
- R3 tests/system/test_run_all.py and test_make_report.py pass; `python tests/run_tests.py` passes (full suite).
- R4 README.md covers: what v3 is, install, data and licences (V2AIX non-commercial / no redistribution; CICIDS unofficial mirror), how to run, where results are, honest summary.
- Curated inputs that exist in no result JSON (test-exposure counts, v2 reference numbers quoted in the M1 reports) go in ONE file results/WP7/S3_registry.json with a "source" for each entry
  (report + section); they are treated like JSON keys by the tracker and labelled "curated" in the appendix.

### 2026-10-24 S3 built and checked (numbers from the generated files; no test set scored)
- Files: run_all.py (step table, 47 steps incl. a pending marker; kinds regression / tables / tests / runtime / report by default, prep / dev / build / eval only with --refit), make_report.py, RESULTS_v3.md,
  README.md, results/WP7/S3_registry.json, tests/system/test_run_all.py (10 tests), test_make_report.py (8 tests), reports/WP7_S3.md.
- Entry points were discovered from the headers of tools/WP*_S*.py (usage lines), not from memory: WP1 S8 dev/test/control/external/freeze/tables, WP2 S7 select/fit/final/tables/others/summary, WP3 S4 tables (LiDAR
  open: pending step), WP4 S7 prep/dev/test/d23/freeze/tables, WP5 S6 dev/run and S3b cache/geometry/clean/inject/senders/tables, WP6 S5 streams/dev/test/tables, WP7 S1 fits/runtime/S1b. Tools that rewrite reports/*.md
  (WP5_S6_report, WP7_S1_report) are NOT in the default run (they overwrite committed milestone reports).
- `python run_all.py --check` (read-only) all OK: GPS/CAN/network freeze checks (diff 0, mismatches 0), V2X runtime thresholds == WP5 S6, M2 system == config, WP7 S1 acceptance MET, make_report inputs complete.
- make_report: 786 traced values, 0 missing keys in closed milestones, deterministic. Pitfalls met while building it: (1) a Python non-raw string "\b" inside a patch script became a backspace character and silently disabled a regex
  (check with od -c); (2) pathlib.write_text has no newline= in Python 3.9 (use open(..., newline="\n")); (3) many numbers hide in prose ("1% budget", "section 4", "class 17"): the scan allows only identifiers, dates,
  section / class references and "95% interval"; everything else must come through a Ctx method; (4) dict keys of some JSON mix captures and ambient entries (s7_test per_capture): filter by name.
- Verdict policy: GPS (G1..G10), V2X (rules 1..5), M2 (A1..A7, Z1..Z6) read `met` / `verdict` from their acceptance JSON; CAN (C1..C5) and NET (N1..N3) are computed from saved numbers against thresholds in the registry
  (sources in M1_CAN.md / M1_NET.md / ROADMAP.md); there is no acceptance JSON for those two milestones.
- Rule counts shown in RESULTS_v3.md section 1 are rows of the generated tables, not the milestone reports' own rule grouping.
- Full suite: 440 passed, 0 failed (tests/run_tests.py).
- Open for the supervisor: names of the files that fill the PENDING sections (results/WP3/S9/acceptance.json, results/WP6/s5b_acceptance.json, results/WP7/S2_acceptance.json); regenerate RESULTS_v3.md after every milestone close.

## 2026-10-25 S2 start: Simulation v3 on the FROZEN system v2 (plan + acceptance rule, written BEFORE any S2 test-data pass; closes M3)

Inputs read (token-saving list of ORCHESTRATION section 6): RULES, STATUS, workpackages/WP7_system.md, notes/WP7_brief.md, ORCHESTRATOR DECISION rows (2026-10-25 "WP6/WP7" and "WP3/WP6"; 2026-10-24 WP6/WP7), reports/WP7_S1.md (+S1b), reports/M2.md incl. the 2026-10-25 addendum, reports/WP6_S5b.md, make_report.py
(slot "M3 simulation" fills from results/WP7/S2_acceptance.json: every top-level key whose value is a dict with "met" (bool) or "verdict" is a row; "rule" is the text; the first 4 scalar fields are shown),
codes_v2 RESULTS_v2.md (live simulation: 7,800 rows, 13 alternating blocks, accuracy 91.67%, FA 1.90%, recall 84.17%, phantom block 8.3% flagged, first alert after 38 rows).
Binding: system = fusion.system.load_system(2) FROZEN (entries, ECDFs, thresholds K 0.6963 / C 0.7032, correlator m2 w5 gap15, majority_decided blame, SAFE_STOP needs >= 2 domains); the five frozen domains through the WP7 S1 / S1b runners; NO tuning of anything. Motion-critical SAFE_STOP rule = separately labelled design variant, never the headline.

### What S2 is (and is not)
S1 proved stream == batch domain by domain on VALIDATION. S2 drives the frozen system on TEST material end to end through the runners, sample by sample, and measures what a deployed system would show: first-alert delay (incl. the real network 5-minute bin and the real LiDAR cost), alert events and SAFE_STOP per clean hour, detection per attack type and domain, blame, response actions, per-domain end-to-end latency, real-time feasibility. It is NOT a new detector evaluation and NOT a re-tuning: the thresholds/ECDFs of system v2 are used as they are, so this is the FIFTH scoring of the fusion test data (S3, S4, S5, S5b before) and every domain test set is seen again (KITTI test drives: 9th exposure counting WP3 S1-S9 + WP6; ROAD test >= 7; D10 test several; VeReMi test 3rd; comma 3rd).

### Construction (fixed here, before any result)
Seed: SEED = 42. Composite pairing / fill-in: rng [42, 77, 2, ord(family)] (family K / C); V2X ego choice rng [42, 77, 3, block index]; regenerated KITTI GPS runs rng [42, 77, 4, drive, phase, run index] (aux [42, 77, 6, drive, phase, run index]); injected motion-sensor attacks rng [42, 77, 5, drive, phase, attack index]; LiDAR attacked scans keep the WP3 generators and seeds unchanged ([83, drive, scan] per-scan, [89, drive] sensor-fixed episodes, [97, drive] world-fixed episodes), i.e. the attacked scans ARE the WP3 test attacks. A new pairing means: not the S5b seed [42, 66, 5, ord(family)].
Time base: 1 Hz system clock (tick k = [k, k+1) s). Block = one composite drive; vehicle block = one KITTI test drive-run (K family, 8-45 s, synced GPS fixes + cross-domain motion witnesses + LiDAR scans of the SAME drive at the same times + CAN wheel-speed witness from simulated CAN frames decoded by the frozen CanDomain) or one comma2k19 test route window of 120 s (C family: real GNSS + CAN speed + gyro; cross layer only). The other domains' segments are placed on the clock from their own test streams: ROAD CAN (frame by frame), VeReMi ego view (message by message), D10 host 192.168.10.50 (flow by flow), all test material, never train rows.
Persistent attacks start at the block start: the attack onset is tick 3 of the block (3 s of clean pre-roll that every layer needs; the WP1 generator cannot start earlier than fix 3) and the attack stays on to the end of the block. Recorded attacks (ROAD, D10, VeReMi, WP3 episodes) are placed so that their recorded onset falls on tick 3. Regenerated vehicle attacks (GPS drift / accel_drift / doppler_spoof / meaconing, gps_can, lidar_scale / bias / yaw, can_scale / offset / freeze) are generated with onset k0 = 3 by the same code (gps.stream.make_run with the onset draw fixed to 3; crossdomain.attacks) so only the onset differs from WP1 / WP6.
Representative sampling: ALL test episodes, no random subset: GPS/cross-K 70 runs per vehicle family (7 test drives x 10 phases); comma 32 episodes per family (+16 clean windows); ROAD every labelled attack interval of the 11 attack captures (+4 ambient clean captures); D10 every attack interval of every test block (15 attack blocks); VeReMi every (ego view, attack class) onset of the ego views of ALL genuine candidate senders of the test blocks; LiDAR all 6 single-return per-scan kinds on all 7 test drives (every 3rd scan attacked from scan 30, WP3 S4 design, persistent to a window of <= 15 s) and all 168 persistent episodes (4 sensor-fixed ep_ + 4 world-fixed epW_ kinds x 3 per drive x 7 drives). The v2 comparison rows (cmp_boxcloud, cmp_mradd_*, GhostCluster) are NOT run (physically impossible on a single-return sensor); v2's phantom/box-cloud block is therefore not like-for-like and is only quoted.
Multi-domain scenarios: (i) KITTI GPS + LiDAR + simulated CAN on the same car: gps_can (coordinated, GPS + wheel odometry + CAN witness), and every GPS family composite carries the synced clean LiDAR + CAN streams of the same car; (ii) comma GNSS + CAN: gnss_can and can_bus; (iii) two-domain scripted blocks as in v2 block 10 / 12: each ROAD attack interval paired with one GPS attack run of the same composite, and with one LiDAR PointDrop / IntensitySpoof window of the same drive (two domains attacked at once, the attacks start at the same tick).
Network: the frozen network domain finalises a flow only when its 5-minute bin has closed (S1b), so Evidence for flow time tau reaches the system at the close of that bin (plus the one-minute hold of the M2 tick model, kept so the frozen network ECDF stays valid). Short vehicle composites therefore carry NO network Evidence (stated limit); network attacks are run as long blocks (D10 attack interval + 6 min tail) with clean vehicle-domain blocks chained underneath (no attack in them), and the network ticks are placed at FLOW time with their availability time recorded; the alarm of such a tick is known to the system only at that availability time.
Clean hours: long clean timelines = the 16 clean D10 test blocks (28,560 s = 7.93 h) as network backbone with clean vehicle blocks chained underneath (K: random clean KITTI runs; C: random clean comma windows; CAN / V2X clean segments from the clean test streams, with replacement), one timeline per backbone block, separate pairing seeds for K and C. Events / SAFE_STOP per clean hour = events over the clean timelines / hours. Clean ticks of attack composites are not used for FA.
Fusion in the stream: system/fusion_runner.py FusionRunner: tick parts arrive with availability times; at every system second the runner has only the parts available so far; the system score, alarm, correlator events and response are computed on that state (prefix re-score of the frozen SystemV2.run, same device as the S1 runners). The first-alert time of a tick is the first second at which its alarm is visible. Final state must equal SystemV2.run on the complete composite (A1).
Per-domain tick semantics = the M2 / S5b pack semantics (so the frozen ECDFs stay valid): GPS fix = tick; cross step = tick; CAN window second = tick; V2X tick = max over heard messages (+ count for the density transform); LiDAR tick = max over the scans of the second (combined and 4 layers), own alarm = any scan alarm; network tick = max over the flows of the last closed minute, held for one minute.

### What is reported
Per attack type (family): composites n, event detection (an alert event with an alarm tick in the attack window) and tick detection, first-alert delay (median, quartiles; two definitions: M2 tick delay = first alarm tick - onset tick; AVAILABLE delay = first second at which the alarm is visible - onset, which includes network bin and intrinsic Evidence delays), blame (correct / wrong / undecided of detected events), response (share of attacked composites whose worst event reaches WARN / DEGRADE / SAFE_STOP; first time to DEGRADE / SAFE_STOP), per attacked domain; alert events and SAFE_STOP / DEGRADE / WARN per clean hour with 95% cluster-bootstrap CIs (over backbone blocks; over vehicle groups for detection); clean tick FA; end-to-end latency per domain (sample -> Evidence on the bus: compute latency from the runners' LatencyLog + the Evidence delay in stream time) and the real-time ratio (compute seconds per stream second) per domain, LiDAR at its measured cost per scan; where the system does not keep up. v2 simulation side by side with the not-like-for-like caveats. Design variant (labelled): SAFE_STOP only when the corroborating second domain is motion-critical (gps, lidar, can) or cross-domain, V2X / network cannot corroborate; same alarms, response recomputed.

### ACCEPTANCE RULE (S2; judged once, on the single full test run)
A1 stream integrity: FusionRunner final alarms and events (start, end, blamed, response) equal SystemV2.run on the same composite for every composite and every clean timeline (0 mismatches).
A2 coverage: for each attack type the number of composites equals the enumerated number of test episodes (table in the JSON, nothing dropped silently; drops are listed with the reason).
A3 live co-simulation: >= 6 composites (K clean; K gps_can; K LiDAR episode; K ROAD CAN attack + LiDAR; C gnss_can; one network excerpt) are driven fully live (all runners fed in time order, Evidence through the EvidenceBus into the FusionRunner at 1 Hz) and give the same per-tick parts / alarms / events as the replay from the stored domain passes (0 mismatches).
A4 timing: per domain, compute latency (median, p95, p99 per sample, from the passes), Evidence delay in stream time, real-time ratio and the statement "keeps up on this machine: yes / no" (rule: p99 per-sample compute < sample period AND amortised compute per stream second <= 1 s); the LiDAR cost is the measured one. MET if the table is complete and every number comes from a measured pass.
A5 completeness: every item of "What is reported" exists in results/WP7/S2_*.json with n and CI where applicable.
System-level bounds, the SAME numbers as M2 / S5b (reported against them, not tuned; the milestone verdict M3 is the conjunction of A1-A5 and B1-B7):
B1 clean raw tick FA <= 3.0% (K and C). B2 alert events per clean hour <= 10 (K and C). B3 K mean event detection over the single-domain attack types (equal weight per type; episode families, comparison rows and coordinated types excluded as in S5b) >= 70%. B4 K mean event detection over the S4 held-out types >= 60%. B5 K blame of detected single-domain events: correct >= 75% and wrong <= 10%. B6 SAFE_STOP per clean hour <= 1 (K and C). B7 100% of alert events carry an explanation (the system's own explanation string).
Expectation written before the run (so the outcome cannot be rationalised): B1 and B2 will not hold (S5b: FA 3.50 / 7.41%, events 17.5 / 28.7 per hour), B3 will not hold, B6 for C is close to 1; A1-A5 and B7 should hold. If B-rows fail the milestone is closed NOT MET with the numbers; no re-run, no re-seed.

### Known limits stated up front
(1) Comma family: the comma witnesses are aligned upstream (cached residual rows of WP6 S2 / S2b) and the cross layer runs per second on them at residual level (CrossRunner.step_residuals); the KITTI family runs the full MotionEstimate chain. (2) Short vehicle composites carry no network Evidence (5-minute bin); network is evaluated on long blocks. (3) No real receiver positions in VeReMi: the ego view is the M2 construction (genuine sender, messages of others within 300 m of its interpolated track), but the V2X runner scores the whole block stream (all senders) so the frozen scores equal the batch scores. (4) The vehicle-attack onset is tick 3 (earliest the generators allow). (5) GPS-LiDAR coupling (OXTS pose) is not re-run (S5b). (6) The CAN domain Evidence comes from ROAD captures (frame by frame), the CAN wheel-speed witness of the KITTI car from simulated frames: two different CAN streams (as in S5b).

### 2026-10-25 S2 build log (before any S2 headline number; passes run on the shared machine, 4 LiDAR workers + 5 other processes)
- New code: system/lidar_runner.py (LidarRunner over the frozen LiDAR stream; 2 tests), system/fusion_runner.py (FusionRunner: 1 Hz fusion with availability times, timeline of events, replay(); 4 tests incl. late network Evidence),
  tools/WP7_S2_{lib,lidar,veh,can,net,v2x,check_lidar,sim,sim_main,live,report}.py, tests/system/{test_fusion_runner,test_lidar_runner,test_s2_sim}.py.
- Integrity of the streams against the M2 packs on IDENTICAL input (results/WP7/S2_check_*.json): GPS 350 original test runs (clean + 4 GPS attacks) max score diff 0.0 and 0 alarm mismatches (236 of ~123k layer-alarm flags differ: the pack
  stores layer scores as float32 and compares them with the layer threshold; the runner uses the layer's own alarm flag); cross-domain layer 70 original clean runs, 1512 ticks, max diff 0.0, 0 alarm / blame mismatches (the runtime cross object is rebuilt
  by the recipe of the WP6 test pack: sigma models on the DEV clean phase-0 rows, ECDF + tie-safe tau on the leave-one-drive-out dev statistics); ROAD CAN attack captures 11/11 windows max diff 0.0, 0 alarm mismatches, ambient captures with
  gaps in the WP2 window table keep their time gaps (the pack collapses them: 456 s capture, 433 table windows); D10 network 17 of 18 blocks max diff 0.0 (first big block checked below); the simulated KITTI wheel witness is decoded by the frozen
  CanDomain decoder (CanDomain.motion_estimates): the CANRunner scoring needs the full ROAD signal set, which a wheel-speed-only simulation lacks (KeyError l3c_M1@0.9 on the first try).
- Decisions while building (all before the S2 test run, none tuned on results): (1) KITTI GPS attacks regenerated with onset fix 3 through a wrapper that fixes only the onset draw of gps.stream.make_run (FixedOnsetRng); (2) comma windows regenerated with onset +3 s using the
  residual code of tools/WP6_S2_comma.py; (3) the CAN wheel witness of the KITTI car is shared by all families of a drive (WP6 S2 seeds [42, 6, 2 / 4, drive]); (4) the V2X pass scores whole blocks (all senders) and cuts ALL ego views (no random 10);
  (5) network ticks keep the M2 minute-hold semantics and carry the availability time of their bin; (6) LiDAR per-scan windows are <= 15 s (scans 29..179), episodes keep the WP3 draws (including the episode start s0).

### 2026-10-25 S2 RESULT (single full test run; numbers from results/WP7/S2_acceptance.json, S2_results.json, S2_tables.md; report reports/WP7_S2.md, milestone reports/M3.md)
- Run: 213,744 attack composites (K 107,229 / C 106,515, 134 attack types, all test episodes: V2X 212,398 of them from 3,108 ego views, LiDAR 42 + 168, ROAD CAN 11 per family, network 17 long blocks per family, KITTI vehicle 770, comma 288, 22 two-domain blocks) and 32 clean timelines (7.93 h per family). Logs results/WP7/logs/S2_*.log.
- Acceptance: A1 MET (0 mismatches in 213,776 composites), A2 MET (0 differences between enumerated and built counts), A3 MET (6 live composites, 0 mismatches; 2 with events), A4 MET (table complete), A5 MET.
  B1 NOT MET (K 3.31% [2.82, 4.15], C 6.15% [5.16, 7.34]), B2 NOT MET (18.4 [16.3, 20.4] / 27.5 [24.5, 30.6] per clean hour), B3 NOT MET (K 60.8% [58.8, 62.9]), B4 MET (71.1% [65.0, 75.8]), B5 MET (78.5 / 9.7% type-weighted; pooled 99.4 / 0.06% is V2X dominated),
  B6 NOT MET for C (K 0.38 [0.10, 0.72], C 1.64 [0.27, 2.49]; variant 0.63), B7 MET (201,637 of 201,637). M3 verdict NOT MET, 8 of 12 rows. The expectation written before the run held (B1, B2, B3 fail, C SAFE_STOP near 1).
- Choice made after seeing a number: B5 judged type-weighted (stricter than pooled), both reported.
- Real time (A4): LiDAR 1.98 s per scan lightly loaded (19x too slow), 3.98 s under the 13-process load of the passes; V2X whole-block stream 1.9 compute s per stream s; CAN window cost grows with the capture (0.14 s -> 2.3 s); network Evidence delay 66 s median, 242 s max.
- Pitfalls met: (1) CANRunner cannot score the simulated wheel-speed-only frames (needs the ROAD signal set): decode with CanDomain.motion_estimates; (2) VeReMi test has 709,430 messages (not 27k: that was the birth count), V2X streaming took ~2.3 h on 4 processes + 1 serial duplicate that could not be killed; (3) the WP2 window table drops windows and the stream keeps time gaps: compare through `sec`; (4) D10 block 2017-07-03|0 differs from the pack in one minute (ordering at equal timestamps); (5) the report bootstrap over 213k composites took 35 min: tools/WP7_S2_finalize.py patches the JSON; (6) a bash heredoc with python triple quotes fails: write patch files with the editor.
- Tests: full suite 486 passed, 1 skipped (RESULTS_v3 staleness; the orchestrator regenerates it), 0 failed.
