# WP2 CAN

Goal: a CAN intrusion detector that works on a car it was calibrated on with normal traffic
only, catches masquerade attacks, and does not confuse rare legitimate states with attacks.

Owns: `can/`, `tests/can/`, `results/WP2/`, `notes/WP2_can.md`, `reports/WP2_*`, `tools/WP2_*`.
Data: D02 Car-Hacking, D05 ROAD (raw logs + decoded signals + anonymized.dbc), D11
can-train-and-test (S0).

## Baseline (v2, `../codes_v2/results/road_external.json`, `road_windows.json`, `can.json`)
ROAD test captures: timing model at 1 s windows, 0.1% target: 0 false alerts, rate-changing
injections and fuzzing detected < 1 s, all masquerade captures and the coolant capture missed.
Payload model: 90.6% frame recall at 1.05% FA, but false alarms on real reverse driving (ID
0x0D0 in ambient_dyno_reverse). Car-Hacking model on ROAD: 0.5% recall. Car-Hacking
leave-one-attack-out: Fuzzy 0.11%.
Target (fixed): ROAD masquerade captures detected with <= 1 false alert per hour; no
reverse-driving false alarm; can-train-and-test unknown-vehicle results reported.

## Steps
- S0 Data: download D11 (7.5 GB) after the user approves; check licence; record.
- S1 Data layer: unified frame format (t, id, dlc, bytes, label, attack, capture, vehicle).
  Adapters: ROAD (copy `parse_log`, `label_attack`, `attack_split` from v2; keep the label
  check vs signal_extractions), Car-Hacking, can-train-and-test. DBC decoding of ROAD signals
  (use `signal_extractions/*.csv` directly, or `cantools` if the user approves a new package).
  Splits: ROAD by capture as in v2 (masquerade copies with their originals); c-t-t its own
  known / unknown vehicle test sets.
- S2 L1 specification rules calibrated per vehicle on normal traffic: ID allow-list, DLC per
  ID, period per ID with tolerance, bus load, top-priority-ID flooding.
- S3 L2a ECU clock-skew fingerprinting (Cho & Shin, CIDS, USENIX Security 2016): per periodic
  ID, accumulated clock offset and skew; masquerade changes the skew.
- S4 L2b signal physics on decoded signals: ranges, rate-of-change limits, cross-signal
  relations (wheel speeds vs vehicle speed, RPM x gear vs speed, gear vs reverse light), learned
  from ambient data and named by meaning where the DBC allows.
- S5 L3 per-signal predictors trained on ambient data only (residual alarms).
- S6 L4 retrain timing + payload models in the harness; window-level alerts (copy v2 logic).
- S7 Combiner + ablation + cross-vehicle tests (c-t-t unknown vehicles, ROAD masquerade, the
  held-out coolant capture) -> milestone M1-CAN report.

## Pitfalls from v2
- Masquerade captures are edited copies of their originals: same split always.
- Fuzzing in ROAD = all-FF payload; accelerator captures have no injected frames (not labelled).
- Car-Hacking attacks sit in the first ~75-80% of each file: split by interleaved time blocks.
- Frame-level 1% FA = ~24 false frames per second at 2,400 frames/s: report window-level alerts.
- A payload model learns the attacked signal's values: test it on rare legitimate states.

## Progress
(worker updates this section)
- S0, S1 APPROVED. S2 done (NOT MET: FA 3.4%). S3 done (negative: skew out of default stack). S4 done 2026-10-22, REVIEW: L2b NOT MET (masq 4/5, FA 38%), see reports/WP2_S4.md.
- S5 done 2026-10-22, REVIEW: L3 NOT MET (detects 5/5 ROAD test masquerade incl. reverse_light_off; clean FA 7.6%, highway 20.4%), see reports/WP2_S5.md.
