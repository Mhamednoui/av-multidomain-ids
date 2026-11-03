# WP9: benchmark track (seen-attack, standard datasets, leak-free), deadline 2026-11-30

User goal (2026-11-03): "by the end of the month ... a solid IDS, good detection rate, one of the best".
Orchestrator reading: be comparable to the published state of the art on the standard datasets
under the standard "known attack types" setting, but leak-free; keep the zero-shot / fresh-hold-out
results of v3 / v3.1 as the distinguishing contribution. Results go to results/WP9/ and RESULTS_v31.md
(separate "benchmark track" section, every row labelled "seen attack types, standard dataset").

## Rules (in addition to RULES.md and WP8 crash safety rules 1-6, which apply here)
- Splits: deduplicate exact rows first; split by time / capture / recording / drive (never random rows);
  the split is written and locked (locks/WP9_<dataset>.json) BEFORE training.
- Validation for every choice; test scored ONCE per dataset in B-final; exposure registered.
- Literature table (B0) is written BEFORE any WP9 result: per dataset, best published numbers,
  their split protocol, whether dedup was done, metric, source (DOI / arXiv). This is the bar.
- No claim "best" unless the comparison is on the same metric and a protocol at least as strict.
- Shuffled-label control at every learned unit; feature-importance red flag as in v3.

## Steps
| Step | Tier | What |
|---|---|---|
| B0 | T2 | Literature survey (web): SOTA per dataset (Car-Hacking, ROAD, can-train-and-test, CICIDS2017, CSE-CIC-IDS2018, VeReMi / VeReMi extension, KITTI-based LiDAR spoofing, GPS spoofing sets), protocols, numbers, sources -> results/WP9/B0_literature.md + .json; propose per-dataset leak-free splits and metrics |
| B1 | T3 | CAN supervised track (Car-Hacking, ROAD, D11) |
| B2 | T3 | Network supervised track (CICIDS2017, CSE-CIC-IDS2018) |
| B3 | T3 | V2X supervised track (VeReMi / extension) |
| B4 | T3 | GPS + LiDAR supervised track (where public benchmarks exist) |
| B5 | T3 | Final: one test scoring per dataset, comparison table vs B0, report reports/WP9_final.md |
