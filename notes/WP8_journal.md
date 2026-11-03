# WP8 journal (append-only; format: ISO time | step | what | state/next)

2026-11-03T00:00 | ORCH | v3.1 started: tag v3.0, branch v3.1, plan workpackages/WP8_v31.md | S0 + P1 launched
2026-11-03T16:38:20+01:00 | S0 | worker start: reading context (START_HERE, RULES, WP8, STATUS, registry, M3) | inventory next
2026-11-03T16:41 | P1 | start: inventory done (GPS s8_raw.pkl+frozen calibrators, LiDAR S9/test_scores.csv.gz, CAN S3 windows partial; NET/V2X/fusion per-sample scores gone) | writing tools/WP8_P1_curves.py
2026-11-03T16:42 | P1 | running tools/WP8_P1_curves.py (gps first), log results/WP8/logs/P1.log | next: check outputs
2026-11-03T16:44:05+01:00 | S0 | launch remote zip directory listing (kitti, comma) tools/WP8_S0_remote_list.py, logs results/WP8/logs/S0_remote_{kitti,comma}.log | resumable, outputs results/WP8/S0/remote/
2026-11-03T16:44 | P1 | done: outputs + reports/WP8_P1.md written, STATUS row P1 -> REVIEW | committing, stop
2026-11-03T00:30 | ORCH | P1 approved; rule 6 (keep scores in results/WP8/scores) added to WP8 plan | S0 running
