# WP4 Network

Goal: a network intrusion detector that counts what attacks must do (scan many ports, retry
logins, flood, beacon) instead of only recognising flow shapes, evaluated on later traffic and
on another dataset.

Owns: `network/`, `tests/network/`, `results/WP4/`, `notes/WP4_network.md`, `reports/WP4_*`, `tools/WP4_*`.
Data: D01 (v2 sample, no IPs / time), D10 full CICIDS2017 flows (S0), D23 CSE-CIC-IDS2018
(cross-dataset), optional D24 TOW-IDS (in-vehicle Ethernet).

## Baseline (v2, `../codes_v2/results/network.json`, `zeroday_unseen.json`)
99.73% acc, macro F1 99.60% on held-out flows (random split after de-duplication); unseen Bot
5.8% (supervised 0%), unseen WebAttack 96.3% (zero-day layer).
Target (fixed): time-based split; unseen Bot > 70% at the same false-alarm level; cross-dataset
2017 -> 2018 reported.

## Steps
- S0 Data: D10 (and D23 after a size check with `aws s3 ls --summarize`) after approval.
- S1 Data layer: flows with timestamps, IPs, ports; remove exact duplicates and conflicting
  labels (v2); split by time (days / time blocks), never randomly; attack labels per flow and
  per host.
- S2 L1 allow-list / protocol rules learned from normal traffic (which hosts talk to which
  services), TCP flag / state sanity.
- S3 L2a host time-window logic: port scan (distinct destination ports / hosts per source,
  threshold random walk, Jung et al. 2004), brute force (repeated short sessions to 21 / 22),
  DoS (rate per destination vs baseline).
- S4 L2b beaconing: periodic connections source -> destination (botnet command and control).
- S5 L3 normal-only per-port profiles and an autoencoder / isolation forest on benign flows.
- S6 L4 retrain XGBoost on the time split inside the harness.
- S7 Combiner + ablation + leave-one-attack-out + cross-dataset -> milestone M1-NET report.

## Pitfalls from v2
- CICIDS2017 sample: 22% exact duplicate flows, 24 conflicting labels.
- Known CICIDS2017 / 2018 labelling problems: check corrected versions (e.g. BCCC) and say which
  labels are used.

## Progress
- S1 APPROVED (data layer). S2 done 2026-10-22 (L1 rules, reports/WP4_S2.md), waits for review.
