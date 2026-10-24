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
