# WP4 S2: L1 allow-list / protocol / TCP-flag rules

Date: 2026-10-22    Worker: sonnet medium (WP4 S2)

## Summary (tables: results/WP4/s2_tables.md, generated from results/WP4/s2_d10.json, s2_d23.json, s2_diag_val.json)
- Five Layer subclasses in network/l1.py, fitted on BENIGN TRAIN, 1% tie-safe budget on BENIGN VALIDATION: net.allow_pair (src,dst,port/proto novelty),
  net.allow_service (dst,port/proto novelty, no source identity), net.proto_port (P(proto|port) + RFC limits), net.tcp_flags (flag-combination rarity + single-packet rule),
  net.flow_rate. Flow level; D10 final (de-duplicated) table; PortScan also on the stage (pre-dedup) cache.
- Acceptance (rule in notes/WP4_network.md, written before the layers were scored):
  A1 FA <= 2% on benign test: MET (layers 0.69-1.17%; combinations 1.07% and 1.20%).
  A2 source-agnostic stack detects >= 50% of flows in >= 3 of 11 families: MET numerically (10 of 11; SSH-Patator 0%), but see the caveat: it is a topology effect.
  A3 honesty items (blind families, ablation, FA): done.
  A4 transfer D10 -> D23 of the flag layers (FA <= 5%): NOT MET (net.tcp_flags FA 30.6%, combination 16.0%).
- D10 test, source-agnostic stack (harness, 4 layers, logistic combiner): FA 1.20%; detection Bot 98, DDoS 100, GoldenEye 100, Hulk 99.8, SlowHTTP 99.3, Slowloris 100,
  FTP 74, PortScan 65, SSH 0, Web-BruteForce 100, Web-XSS 100 (%). Layers alone: allow_service 95.0% overall; tcp_flags 16.9% (Hulk 33, SlowHTTP 76, Slowloris 29, PortScan 10);
  proto_port 0% except the non-evaluable Infiltration; flow_rate 0.1%.
- CAVEAT: nearly all of this is network topology, not attack behaviour. 99.75% of the attack flows go to ONE host (web server 192.168.10.50), which receives only 0.83% of the
  benign flows (141 benign train flows on port 80); the allow-list scores any flow to this rarely used server as rare (s2_diag_val.json, train/validation only). 18.8% of the benign
  validation alarms are flows to that server as well. In another network, or with a busy public server, this would not hold.
- net.allow_pair is lab-specific: every attack comes from the single external address 172.16.0.1, and the pair (172.16.0.1 -> server) never occurs in benign traffic: 100% on 10
  families, Bot 43%. Not counted for A2 (rule fixed in advance). A real attacker address is not "known".
- Families the rules cannot see: SSH-Patator (0% by all source-agnostic layers) and FTP-Patator (allow_service 0%; only the flags / pair layers touch it: login guessing on services
  that benign traffic also uses), Bot except as a rare destination (flags 0%), any application-layer attack to a busy allowed service. PortScan: 65% post-dedup (192 flows), but on the
  154,913 pre-dedup flows of the test window tcp_flags gives 99.1% and allow_service 20.9%: the scan is a flag pattern, not a service novelty. Flow-level rules cannot count fan-out or retries (S3).
- Layers that do not work: net.proto_port (AUC 0.08: attacks use the commonest port/protocol pairs) and net.flow_rate (AUC 0.27: attacks are slower than benign). Kept as reported
  negatives; the ablation shows removing them changes nothing.
- D23 in-dataset (fit on D23 benign): blind. Flag/protocol/rate layers FA 0.9-1.0%, combination detection 1.2% (only DDoS-LOIC-UDP through proto_port, and families with 2-3 flows).
  Allow-list (Tuesday 20-02 only, the only file with IPs): DDoS-LOIC-HTTP 0.0% / 0.1% (AUC 0.79 / 0.90).
- Transfer D10 -> D23 (no refit): allow-list FAILS as expected (FA 96.9% pair, 66.5% service on Tuesday 20-02). proto_port FA 0.3%, flow_rate 0.1% (detect nothing), tcp_flags FA
  30.6%: in D23 the RST / ECE columns are set on 22% of benign flows, in D10 on 0.03%, so the "rare combination" is not rare. Flag rules do NOT transfer.
- Combiner quirk: with all five layers the harness chose "max" and Bot falls to 0% although allow_service alone detects 98%; the 4-layer stack chose logistic. Both tables are in s2_tables.md.
- Test used once (results/WP4/logs/s2_verdict.log). Every choice on validation. 15 network tests pass.
- Question: is a flow-level "rare destination server" score what we want in L1? Valid in this lab, but it ties detection to a topology fact; behaviour counting starts in S3.

## Goal of the step
L1 allow-list / protocol rules learned from normal traffic (which hosts talk to which services), TCP flag / state sanity.

## Acceptance rule (notes/WP4_network.md, "S2 start", 2026-10-22, before any layer was scored)
A1 FA <= 2% on D10 benign test per layer and combination. A2 the stack without source identity detects >= 50% in >= 3 of the 11 evaluable D10 families (allow_pair excluded: one external
attacker address). A3 report blind families, ablation, FA. A4 transfer D10 -> D23: flag/protocol/rate layers FA <= 5% on D23 benign test; allow-list expected to fail (not a criterion).

## What was done
- network/l1.py (5 layers), tests/network/test_l1.py (7 tests), tools/WP4_S2_lib.py (compact tables, cache ../data_extra/cache_v3/WP4/S2/, +1.7 GB), WP4_S2_dev.py (validation grid),
  WP4_S2_run.py (smoke | verdict), WP4_S2_diag.py (train/validation diagnostic), WP4_S2_tables.py.
- Data: D10 final tables (benign train 1,076,772; benign val 359,449; test 470,829 flows, 401,965 benign) and the PortScan stage file; D23 final tables, all 10 files (allow-list: Tuesday 20-02 only).
  Known host = address with >= 10,000 benign train flows (15 hosts); port/proto keys with < 1,000 benign train flows are pooled into their class bucket. Both chosen on validation (grid edge, not searched further).
- Validation finding that shaped the layers: unpooled rare ports tie at the top score for 1.9% of benign val flows, so the tie-safe threshold sat above them (first version detected 0%).
- Harness subsample (fixed, seed 42): benign 150,000 and at most 20,000 flows per family per split. Per-layer rows use all flows. Combiner method chosen on validation halves by group (day).
- Dedup: the final tables are de-duplicated (PortScan 1,851 flows overall, 192 in test); the stage cache (154,913 PortScan flows in the test window) is used for the pre-dedup PortScan row only.

## Results (all tables: results/WP4/s2_tables.md)
D10 test, layer alone, FA on benign (401,965): allow_pair 1.17%, allow_service 0.93%, proto_port 0.69%, tcp_flags 1.14%, flow_rate 0.96%. AUC 0.995 / 0.997 / 0.082 / 0.877 / 0.273.
Acceptance: A1 MET, A2 MET (numerically; topology caveat), A3 MET, A4 NOT MET.

## Ablation rows
results/WP4/s2_d10_all.md and s2_d10_no_identity.md (each layer alone, all, all-but-one). 4-layer stack: removing allow_service 97.2% -> 65.9% detection; removing tcp_flags, proto_port or
flow_rate: -0.1 to -2.2 pts. Without allow_service the remaining signal is tcp_flags: Hulk 95.7%, Slowloris 62.7%, SlowHTTP 77.8%, PortScan 16.7% (all_but_net.allow_service row).

## Problems, surprises, open questions
1. Detection is dominated by "flows to a rarely used server": a dataset artefact (single victim). D10 is a weak test of the allow-list idea; D23 shows the allow-list and flag rules are blind there.
2. CICFlowMeter flag columns are 0/1 presence flags with known artefacts (Fwd PSH Flags equals SYN Flag Cnt in D10; RST equals ECE in D23), so "impossible flag combination" cannot be asserted
   from RFCs; it is learned rarity and does not transfer.
3. Test splits come from the same attack sessions as train (S1 caveat 7), so within-D10 numbers are optimistic; D23 is the honest cross-session figure and shows near-zero.
4. proto_port and flow_rate have AUC < 0.5 on D10 test (attacks look more ordinary): no inversion applied (it would be a choice made on results).
5. tools/WP4_s1_peek.py shows as deleted in the working tree; not mine, left alone.

## Proposed next step
S3 host time-window logic on the stage caches: fan-out, retry counts, rates; these are what flow-level rules cannot see (PortScan, SSH/FTP-Patator, DoS rate).
