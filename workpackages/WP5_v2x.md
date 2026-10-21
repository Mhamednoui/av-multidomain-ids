# WP5 V2X (new domain)

Goal: detect misbehaving V2X senders (falsified position / speed / heading, ghost vehicles,
replay, beacon flooding) from received BSM / CAM messages, with plausibility physics first.

Owns: `v2x/`, `tests/v2x/`, `results/WP5/`, `notes/WP5_v2x.md`, `reports/WP5_*`, `tools/WP5_*`.
Data: D12 VeReMi Extension (benchmark), D13 V2AIX JSON subset and / or D14 Tampa BSM sample
(real messages), D15 OSM (road plausibility).

## Baseline
None in v1 / v2 (new domain). Literature on VeReMi Extension (F2MD plausibility checks + ML)
is the reference; report results in a comparable form (per attack type).
Target (fixed): VeReMi Extension results reported per attack type, comparable with the
literature; misbehaviour injected on real messages reported per attack type at 1% FA.

## Steps
- S0 Data: D12 and D14 (small) first; D13 subset size decided with the user.
- S1 Data layer: unified message format (sender id / pseudonym, t, position, speed, heading,
  acceleration, yaw rate, receiver id and position). Adapters VeReMi (JSON logs / CSV),
  Tampa (J2735 BSM fields), V2AIX (CAM). Injection on real messages following the VeReMi
  taxonomy (constant / random position offset, constant / random speed, eventual stop,
  data replay, delayed messages, DoS rate, Sybil / ghost vehicles, sudden appearance), each
  physically described. Split by sender / scenario / recording, never by message.
- S2 L1 message checks: beacon rate per sender, timestamp freshness, field ranges, sudden
  appearance (first message too close to the receiver).
- S3 L2 plausibility (F2MD, Kamel et al.): acceptance range threshold (received from farther
  than radio range), position / speed / heading consistency between consecutive beacons,
  kinematic consistency, overlapping vehicles, map / road plausibility (OSM).
- S4 L3 per-sender Kalman tracker trained on normal motion; innovation tests.
- S5 L4 supervised model on plausibility features (VeReMi train / test).
- S6 Combiner + ablation + VeReMi benchmark + real-message injected test -> milestone M1-V2X.
- (WP6 later) cross-check: a V2X-announced vehicle within LiDAR range should be seen by LiDAR.

## Notes
- No public real-world V2X dataset with labelled real attacks was found (20 Oct 2026). Use
  real messages for normal behaviour and inject physically consistent misbehaviour; VeReMi for
  comparability. Check VeReMi NextGen (2026), MisbehaviorX, V2X-PAD as newer options.

## Progress
(worker updates this section)
- S0 PARTIAL, S1 APPROVED, S2 APPROVED, S3 REVIEW (2026-10-20): v2x/l2.py, reports/WP5_S3.md (PARTIAL: Tampa map false alarms do not transfer). S3b waits for receiver positions.
- S1b REVIEW (2026-10-20): Tampa dedup (19,527 messages), 38 physical vehicles, new time-block split splits_tampa_v2.json, S2+S3 Tampa rerun, reports/WP5_S1b.md (PARTIAL: heading_rate FA 2.7%).
- S4 REVIEW (2026-10-21): v2x/l3.py (Kalman tracker, NIS + CUSUM, track_birth), reports/WP5_S4.md (PARTIAL: Tampa FA of cusum_lo 13.5%). VeReMi L1+L2 68.0% -> L1+L2+L3 78.4% mean detection.
- S5 REVIEW (2026-10-21): v2x/l4.py (xgboost on L1-L3 plausibility features), reports/WP5_S5.md (PARTIAL: headline 78.1% -> 91.5% mean detection, unseen 17 46% -> 92%, but a zero-residual shortcut inflates it; on scored rows L4 ~ baseline except class 17).
- S6 REVIEW (2026-10-21): scored-row L4 (v2x/l4.py L4Scored, rate-free S2_resid features), v2x/stackeval.py, domain combiner + ablation + block-bootstrap CIs on VeReMi (second test exposure), Tampa illustration, reports/M1_V2X.md + reports/WP5_S6.md (PARTIAL: FA and no-loss met; sender FA at k=3, class-17 gain and shuffled control NOT met). Closes M1-V2X pending approval.
