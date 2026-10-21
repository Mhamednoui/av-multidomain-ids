# WP5 S4: L3 per-sender Kalman tracker with innovation tests

Date: 2026-10-20/21    Worker: sonnet (medium)    Status: PARTIAL (VeReMi met; Tampa FA of one check not met)
Full report (equations, class-by-class, limitations, all tables): `results/WP5/s4_report_details.md`. Rule: `notes/WP5_v2x.md` ("S4 ... acceptance rule", written before results).

## Summary
- Built `v2x/l3.py`: constant-velocity Kalman (state x,y,vx,vy; measurement position+velocity; white-noise-acceleration Q). Noise (sp, sv, sa) by max-likelihood on 800 genuine TRAIN tracks only (VeReMi: sp 0.05 m and sv 0.02 m/s on their floors, sa 1.94). 4 layers: kf_nis (chi2 per message), kf_cusum_hi (CUSUM on NIS), kf_cusum_lo ("too exact" track), track_birth (new identities within 300 m / 10 s, no receiver position). Thresholds: genuine val, 1% budget, tie-safe; types 6/12/17 never used. Tests: 144 pass.
- Consistency (genuine val): VeReMi NIS mean 4.15, 7.0% above chi2 95% (inside the pre-registered bounds) but shape poor (median 0.19 vs 3.36, heavy tail). Tampa NIS mean 2.10 (outside [3,5]).
- FA on genuine test: VeReMi all L3 checks and union <= 0.9% (MET). Tampa: cusum_lo 13.5%, L3 union 14.8% (NOT MET; others <= 1.8%).
- Value (VeReMi test, harness, 1% budget): L1+L2 68.0% -> L1+L2+L3 78.4% mean detection over 19 classes (+10.4), FA 0.98% -> 1.08%. AUC 0.845 -> 0.907.
- What L3 catches (VeReMi, message level, L3 union vs L1+L2): 2 ConstPosOffset nothing (1%); 9 EventualStop little (11% vs 1%; cusum_lo 18.7%, missed K2 >= 30%); 11 DataReplay 98% vs 68%; 12 DelayedMessages* 48% vs 1% (CSV class 12 is zero placeholders; alarm comes only at the jump to real positions and persists via CUSUM memory, not "delay"); 16 GridSybil 73% vs 61%; 17 DataReplaySybil* 53% vs 17% (mostly track_birth); 18/19 tracker blind (0-0.3%, one/two-message tracks), track_birth 38%/43% per message, 16%/39% in the union; sender level (>= 3 alarms) 97.8%/100% vs 0%/37%, genuine senders flagged 2.9%.
- Caveats: CUSUM keeps alarming after one jump (inflates message-level numbers for 12, 11); VeReMi's own 11/13/16 are kinematically inconsistent; cusum_lo is VeReMi-only (real standing vehicles repeat positions exactly); track_birth FA per genuine birth 62-81% (lenient per-message budget); Tampa = 3 vehicles, illustration only (L1+L2 48.7% -> 72.2% but at 15.8% FA; without cusum_lo 69.2% at 2.8% FA).
- Pre-registered K1-K7: K1, K4, K5, K7 as expected; K2 not met; K3 met for the wrong reason; K6 birth better than expected.
- Delay (sender level, median of detected attackers, L3 union): 11: 1 s, 16: 0.3 s, 17: 1 s, 18: 2.5 s, 19: 1 s, 9: 7 s, 12: 61 s.

## Questions for the supervisor
1. Drop cusum_lo from the deployable L3 (recommended) or keep as VeReMi-only?
2. Build a learned road-occupancy prior (train genuine positions) for 2, 12, 18, 19? Not done (outside S4).

## Files
`v2x/l3.py`, `tests/v2x/test_l3.py`, `tools/WP5_S4_l3.py`, `WP5_S4_diag.py`, `WP5_S4_report.py`; `results/WP5/s4_summary.json`, `s4_veremi.json/.md`, `s4_tampa.json/.md`, `s4_tables.md`, `s4_report_tables.md`, `s4_report_details.md`, `s4_diag.json`, `s4_params_*.json`; logs `results/WP5/logs/s4_*.log`.
