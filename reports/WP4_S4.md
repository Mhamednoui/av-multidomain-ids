# WP4 S4: L2b beaconing (periodicity of connection start times)

Date: 2026-10-22    Worker: sonnet medium (WP4 S4)

## Summary (tables: results/WP4/s4_tables.md; numbers: results/WP4/s4_d10.json, s4_d23.json, s4_limit.json, s4_dev_val.json, s4_acceptance.json)
- Layer net.beacon (network/l2b.py): per (source, destination, port, protocol) group of service-directed flows, the series of ACTIVE MINUTES in a trailing 64-minute window is tested for periodicity:
  gap CV, gap MAD/median, jitter-tolerant fraction of gaps near the median (tol), autocorrelation peak (+-1 min), plus a separate sub-minute "rate" diagnostic. IPs only group flows; no IP or port whitelist.
  The benign distribution of every statistic is learned on benign TRAIN groups (tail probability), so NTP / DNS-like periodic services are just "usual"; 1% tie-safe budget on benign validation (flow unit and group x 64-min window unit). N_MIN = 6 active minutes before scoring. WIN 64 and N_MIN 6 chosen on validation.
- Bot in the data (pre-dedup stage flows): train 1539 / val 109 / test 308 / gap 10 flows; 5 real groups (5 bots -> one C2 server :8080) per split + 1-6 stray groups. Each group: a burst of 5-8 flows per minute for ~30 min, then a beacon of one flow per 1-2 active minutes
  (about 100 s period). TEST: 5 groups with 42, 85, 42, 85, 48 flows.
- Acceptance (notes/WP4_network.md, fixed on validation before the verdict):
  C1 MET (FA flow 1.75%, 1.51% with published labels, window 1.10%).
  C2 NOT MET (Bot 36.0% of flows vs 50%; 3 of 5 groups alarmed vs 4; the two 85-flow groups never become testable).
  C3 NOT MET (harness Bot 0% -> 17.5%, +17.5 points vs 20 required; macro over 11 families 54.2 -> 55.8%, +1.6 met; stack FA 0.33 -> 0.57%).
  C4 measured (below). C5 MET (D23 Tue-20-02 transfer FA 2.71%, refit 1.21%).
- Honest reading: Bot beaconing is visible only as far as the 1-minute grid allows, and only in 36% of the Bot flows (those after the 6th active minute in groups with median gap >= 2 min).
  Among flows that are testable the layer alarms 100% of Bot flows, but also 26.8% of testable benign flows: only 6.5% of benign flows belong to a testable group, so the 1% flow budget is spent inside that 6.5%
  (benign groups are very regular at minute resolution: 30% of testable benign cells have tol = 1). Periodicity alone is a weak separator here: a real but low-precision addition for Bot
  (OR with L2a: Bot 1% -> 36%, FA 2.77 -> 4.50%).
- Resolvable period (synthetic groups, thresholds from validation, s4_tables.md section 8): phase statistics detect 100% of groups from period 100 s (jitter 0, 10%, 30%) to 720 s; 90 s only 60% of groups (flows 2%),
  45-60 s 0% (about one flow per minute looks like continuous activity), 900 s and above 0% (fewer than 6 active minutes in 64 min).
  Below 1 minute only the flows-per-minute "rate" statistic fires (periods 5-30 s, 100% of groups) but it fires equally on high-rate Poisson control traffic: a steady-rate detector, not proof of periodicity.
  Ares (~100 s) sits at the lower edge of the resolvable range. Data limit: D10 timestamps cannot show periods below ~1.6 min as phase.
- D23 Bot (Fri-02-03): NOT EVALUABLE: src_ip, dst_ip and src_port are 100% NaN in that file, so no (source, destination) groups exist. Only D23 Tue-20-02 has addresses (no Bot there): used for the FA transfer.
- Delay (minutes from the first Bot flow of the group): first alarm after 8 min (two groups) and 109 min (one group, long burst before its beacon). Segment-level: 1 of 2 test segments detected, median 9 min.
- Harness (tcp_flags + 5 L2a + beacon, logistic combiner): Bot 17.5% (beacon alone 36%), combined FA 0.57%. As in S3 the learned combiner dilutes a single-purpose layer; the OR view gives 36% Bot.

## Files
network/l2b.py, tests/network/test_l2b.py (8 tests; full suite 265/265), tools/WP4_S4_dev.py, _limit.py, _run.py, _tables.py, results/WP4/s4_*.json|md, logs results/WP4/logs/s4_*.log.
No new cache (WP4 cache 4.7 GB); temporary files deleted.

## Caveats
1. Validation basis is weak: 109 Bot flows, 5 groups. WIN / N_MIN were chosen on it (N_MIN 6: 27.5% on val); the test result (36%) is of the same size order, not a tuned number.
2. The 1-minute grid: gaps of 1 and 2 minutes carry the 100-s period only as quantisation noise; the layer works because the benign tails are heavier than the Bot values, not because the period is recovered.
3. Group level: synthetic Poisson groups are also flagged at group level (10-85%) because a long group has many chances to exceed a 1% flow threshold; flow-level FA on Poisson is <= 2%.
4. The synthetic limit test describes the grid, not Ares; a real attacker can choose any period or jitter, and a bot with period < 1.6 min or > 12 min is invisible to this layer at this resolution.
5. The audited Infiltration file (S3 decision) is excluded from fit, calibration and headline FA; FA with published labels is given too (1.51 vs 1.75%).

## Questions
- Accept NOT MET for C2 / C3 and keep net.beacon as a low-precision optional layer for Bot (its weight in S7 decided with leave-one-attack-out)? Bot flows have a very fixed shape (4 fwd / 3 bwd packets, ~80 ms, port 8080): flow-level L3/L4 (S5/S6) can use what a periodicity statistic cannot.
- D23 Bot needs addresses, which the processed CSVs lack; the CSE-CIC-IDS2018 PCAP-derived CSVs have them but are a separate download (not approved).

## Proposed next step
S5 L3 normal-only per-port profiles and an autoencoder / isolation forest on benign flows.
