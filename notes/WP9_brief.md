# WP9 brief (benchmark track; <= 60 lines; workers update their own lines)

## Bar (B0, results/WP9/B0_literature.md)
- can-train-and-test: Lampe & Meng arXiv 2308.04972 capture-disjoint, best F1 0.95-0.998 (mean of 18 learners 0.42-0.46).
- CICIDS2017: Moczkodan & Ragab arXiv 2606.11098 time + 5-tuple group splits, macro-F1 0.89 (20-flow windows). Leaky per-day RF 0.94-0.998.
- Car-Hacking: only leaky (random 7:3), F1 0.998-1.0; recorded parked (Lampe & Meng).
- ROAD: Guerra et al. mean F1 0.32 / DCNN 0.65-0.75; LSTM 1.0 = red flag.
- VeReMi ext: DoS only, 70/30, F1 0.93-0.998. GPS: Abrar et al. AV-GPS cross-dataset F1 0.90-0.965.
- No leak-free bar: CSE-CIC-IDS2018, capture-level ROAD, leak-free Car-Hacking, KITTI/comma GPS, unseen VeReMi -> our numbers are first such numbers (say so).

## Orchestrator decisions (2026-11-04, before any WP9 result)
1. Splits per results/WP9/B0_splits_proposal.md, locked in locks/WP9_<dataset>.json before training.
2. CICIDS2017: use the corrected labels of Engelen et al. 2021 (WTMC) if downloadable without login (RULES 3.4); else original labels, labelled "original CICFlowMeter labels (known errors)". Report both if both exist (test scored once per label set, exposure labelled).
3. ROAD: max_engine_coolant_temp has attack only in test -> reported as an unseen-family row, never in the seen-attack table.
4. VeReMi: split by simulation run / file (not by sender) to avoid neighbour-context leaks.
5. Report per dataset: macro-F1, per-class recall, FPR, AUC (where scores exist), with group-bootstrap 95% CI; plus the literature metric if different.
6. Reuse v3 supervised layers where they exist; otherwise standard strong baselines (gradient boosting, RF, 1D-CNN/LSTM where justified). Shuffled-label control mandatory.

## Steps state
- B0 approved 2026-11-04. B1 (CAN), B2 (network) launched 2026-11-04. B3 (V2X), B4 (GPS+LiDAR) next.
- B1 CAN (2026-11-04, REVIEW; reports/WP9_B1.md): 1 s window unit, locks in locks/WP9_{carhacking,road,d11}.json, test scored once. Car-Hacking block split: macro-F1 0.999 [0.998,1.000], FPR 0.000 (normal_run 0.012): MET, equal to the leaky bar (not better).
  ROAD capture split: 10-class macro-F1 0.829 [0.724,0.996], FPR 3.2%, 9/9 attack captures alarmed, masquerade reverse_light_on/off recall 0.00/0.48, coolant (unseen) 0/2: NOT MET.
  D11 (4 sets): test_01 window F1 mean 0.80 at the 1% budget (post-hoc F1-optimal thr 0.96/0.57/0.99/0.98), unknown vehicle (test_02/04) FPR 100%; test_03/04 are UNSEEN-attack rows (B0 proposal corrected).
  Controls: global shuffled-label fails for ROAD and most D11 units; within-capture permutation AUC 0.7-0.9 (regime shortcut learnable); same-segment AUC still 0.93-1.00. Unit differs from the literature (frame): no "better" claim.

- ORCH on B1 (2026-11-04): approved. Headline per pre-registered rule (1% val budget). D11 F1 at the val-F1-optimal threshold (0.964/0.571/0.985/0.979) may be reported as a SECONDARY operating point, labelled "threshold chosen on validation for max F1 (literature convention); reported after the 1% test result; same single test scoring". Shuffled-label failure (capture regime predicts attack-bearing) must be stated in every table that uses ROAD / D11 seen rows. Unknown-vehicle FPR 100% = v3 finding (on-vehicle calibration needed).
- B3 V2X (2026-11-05, REVIEW; reports/WP9_B3.md): message unit, D12 = one simulation, run-level split = 1800 s time block (23/7/8 blocks), locks/WP9_veremi.json; H31's 10 WP5 test blocks excluded (overlap 0). Test scored once (exposure 1).
  Chosen xgb_D_noT_d6 (plausibility + raw fields). Test H (1% val budget): macro-F1 0.917 [0.911,0.923], FPR 0.0104, AUC 0.983, mean alarm recall 0.957; S (val-F1-opt): macro-F1 0.918, FPR 0.0017.
  DoS family prevalence-matched 70/30 F1 0.992-0.996 (pooled 0.995) vs bar 0.93-0.998: R1 MET (equal, stricter split, no "better"); natural prevalence H 0.89-0.94. R2 MET. Weak: ConstPosOffset 0.63, EventualStop 0.83, GridSybil 0.81; class 12 = artefact.
  Controls: row shuffle 0.496 PASS; within-block sender permutation 0.377 and proxy-only (time, sender, pseudonym) 0.638 FAIL as written (time/sender alone 0.508, pseudonym id carries churn 0.629; group-permutation nulls 0.34-0.52). v3 L4 reused as-is: recall 0.60 (weak). Raw x,y = map-specific.
