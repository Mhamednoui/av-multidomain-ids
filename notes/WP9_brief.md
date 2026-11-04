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
