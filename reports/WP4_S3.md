# WP4 S3: L2a host time-window logic (scan, TRW, brute force, DoS rate, slow)

Date: 2026-10-22    Worker: sonnet medium (WP4 S3)

## Summary (tables: results/WP4/s3_tables.md; numbers: results/WP4/s3_d10.json, s3_d23.json, s3_acceptance.json, s3_dev_val.json)
- Five stream Layers in network/l2a.py (net.scan, net.trw, net.bruteforce, net.dos_rate, net.slow). IPs only GROUP flows (per source, pair, destination); no address identity.
  Counts use the PRE-DEDUP stage flows (flow multiplicity matters; D10 stage 2,830,743 flows, D23 Tue 7,948,748). D10 time resolution is ONE minute, windows are whole minutes.
- Fit on benign-only train stream, 1% tie-safe budget on benign-only val stream (flow unit and window unit), ONE verdict run on test (mixed stream). W chosen on val: scan 1, trw 5, bruteforce 1, dos_rate 1, slow 5.
- Acceptance (notes/WP4_network.md, written before any score):
  B1 MET (layer FA 0.00-1.77%, window FA 0.07-0.90%, harness stack FA 0.33%).
  B2 MET (PortScan 97.4%, SSH 98.6%, FTP 99.95%).
  B3 MET (4 of 5 DoS families >= 50%: Hulk 100, GoldenEye 100, LOIC 100, SlowHTTP 85; Slowloris 0).
  B4 MET (macro over 11 families: tcp_flags alone 21.1% -> tcp_flags + L2a 54.2%; L2a alone 61.9%).
  B5 NOT MET as written (transfer D10 -> D23 Tue-20-02 without refit: DDoS-LOIC-HTTP detected 99.7%, but OR-FA 46.6%: net.dos_rate FA 39.7% because destination baselines do not exist on the other network;
  scan 2.5%, trw 3.1%, bruteforce 2.2% FA are within 5%; bruteforce alone detects LOIC 99.3% at FA 2.2%). Refit on D23: LOIC 100%, per-layer FA 1.0-1.4%, OR 5.5%.
- Per family (D10 test, flow unit, %): PortScan 97.4 (scan, trw, dos_rate), SSH 98.6 and FTP 100 (bruteforce), Hulk/GoldenEye/LOIC 100, SlowHTTP 85. Not seen: Bot 1, Web-BruteForce 0, Web-XSS 0, Slowloris 0.
- Delay (minutes from the first attack flow of the test segment, resolution 1 min): 0 for LOIC, GoldenEye, Hulk, SSH; 1 for FTP and PortScan (first segment); 4 for SlowHTTP (table 3 of s3_tables.md).
- Pre-dedup vs dedup: on the flows that survive de-duplication PortScan falls to 40.6% (from 97.4%): window counts come from the full stream, the survivors are the atypical scan flows. Other families change < 10 points (table 5).
- Harness (tcp_flags + 5 L2a, logistic combiner, subsample drawn AFTER the window features): combined FA 0.33%, detection 93.1% of attack flows, but the combiner drops SSH to 0.1% and Slowloris is 8.5%
  (correlated layers; removing net.slow or net.trw restores SSH 98.6%): per-layer / OR numbers are clearer than the learned combiner here. OR of the 5 layers has FA 2.77% (five 1% budgets add up); it is not the stack.

## Honest caveats
1. LABEL PROBLEM (D10): in Thursday afternoon (Infiltration file) the compromised host scans (2,033 flows, 1,008 ports in one minute) and it is labelled BENIGN. With the published labels every scan / half-open budget is eaten
   by it (FA with published labels: scan 4.8%, dos_rate 5.4%, trw 3.7%). Decision taken on validation before the verdict: that file's benign flows are excluded from fit, calibration and the headline FA but stay in the stream.
   Both FA figures are in every table. This is an audit decision on the labels, not tuning on test.
2. Reversed flows: CICFlowMeter often reports the server as source with an ephemeral destination port, so scan and TRW count only dst ports < 32768 (TCP for TRW). Rule fixed on train / val.
3. TRW alone is weak (AUC 0.51; benign hosts fail first contacts often: the classic ln(99) threshold gives 10% FA on val); with a budget threshold it equals scan on PortScan and adds nothing in the ablation.
4. net.dos_rate is NOT topology-free in one respect: it looks up a per-destination baseline learned on the protected network (unseen destinations use a pooled 90th percentile). On another network it needs a refit (B5).
5. Per-minute window detection of PortScan is only 20-25% (many scan cells are partial minutes at the edges) while the flow unit is 97%.
6. Families time windows cannot see (single-flow application attacks or low-volume behaviour): Web-XSS, Web-SQLi, Heartbleed, Infiltration (0-33%), Web-BruteForce (about 1,000 flows over 1-2 minutes, below the busy web server's own rate),
   Bot (1%), Slowloris (few connections, hidden by the benign long-lived flows of the same server; tcp_flags catches 34.7%). These need the L3/L4 flow models.
7. Window-unit detections of rare families rest on few cells (e.g. Web-XSS 1 cell); see the n in results/WP4/s3_d10.json.

## Ablation (harness, D10 test; full table s3_tables.md section 6, each layer alone and all-but-one)
| configuration | FA % | macro 11 families % |
|---|---|---|
| net.tcp_flags (topology-free L1) alone | 0.88 | 21.1 |
| L2a layers only, combined | 0.49 | 61.9 |
| tcp_flags + L2a, combined | 0.33 | 54.2 |
| all but net.bruteforce | 0.33 | 41.8 |
| all but net.tcp_flags | 0.49 | 61.9 |

## Files
network/l2a.py, tests/network/test_l2a.py (13 tests; full suite 239/239), tools/WP4_S3_prep.py, _dev.py, _lib.py, _run.py, _tables.py, results/WP4/s3_*.json|md, logs results/WP4/logs/s3_*.log.
Cache: ../data_extra/cache_v3/WP4/S3 (compact stage tables); S2/D23.pkl deleted (rebuildable); WP4 cache 4.7 GB.

## Questions
- Accept the audit of the Infiltration file (caveat 1)? Alternative: published labels only (all FA figures for both are in the tables).
- B5 is NOT MET for net.dos_rate without refit. Options for S7: online per-destination baseline (no table), or treat only bruteforce / scan / trw as transferable.

## Proposed next step
S4 L2b beaconing (needs IPs: D10 and D23 Tue only).
