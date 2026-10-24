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
