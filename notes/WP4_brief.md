# WP4 brief (network) - read this first
Status after S1 (2026-10-21). Details: notes/WP4_network.md, reports/WP4_S1.md, results/WP4/s1_tables.md.

## Data (all derived tables: ../data_extra/cache_v3/WP4/, pickle gzip, outside git, ~3.2 GB)
- D10 CICIDS2017 GeneratedLabelledFlows (unofficial HF mirror, agrees with the MachineLearningCVE copy on every flow and label: gate G2+G3 passed;
  G1 vs D01 failed, D01 is not a verbatim subset of either file set, so v2 network numbers on D01 are NOT directly comparable with v3).
  2,830,743 labelled rows -> 596,376 exact duplicates (21.1%), 542 conflicting -> 2,233,825 clean.
- D23 CSE-CIC-IDS2018 processed CSVs: 16,232,943 rows -> 5,410,812 duplicates (33.3%), 43,572 conflicting -> 10,778,559 clean.
  7 of 10 files stop at 1,048,575 rows as published (not our truncation); Fri-16-02 therefore ends at 13:xx (Hulk cut: val 0).
- Only D10 and D23 Tue-20-02 have IPs and ports; the other nine D23 files have no IPs (host logic S3/S4 cannot run on them).
- Layout: cache_v3/WP4/<D10|D23>/final/*.pkl (D23 in 1M-row chunks) with columns file,row,ts,src_ip,dst_ip,src_port,dst_port,protocol,
  label,family,group,hash,<76 features float32, D23 names>,split,period,day. D10/roles.pkl = per-flow attacker/victim role. D10/stage + D23/stage = all
  rows BEFORE dup/conflict removal (use them for S3 scan/brute-force counts; the cleaned tables lose 99% of PortScan and most D23 FTP/SlowHTTPTest flows).
- Loader helpers and column map (D10 77 columns -> 76 D23 names; 'Fwd Header Length.1' is a duplicate and dropped): network/flows.py.

## Cleaning (as v2, on feature hashes; inf -> NaN; earliest copy kept; conflicts dropped entirely)
- Empty separator rows (288,602 in D10 Thu-morning) and repeated header rows (59 in D23) removed and counted per file (results/WP4/s1_clean_*.json).
- Timestamps carry no AM/PM in both datasets: hours 1-7 are +12 h (checked against the published attack schedule). 14 D23 rows with 1970 dates -> split "gap".

## Split (by time, never random)
- Per day: periods = attack windows (family timestamp clusters, gap > 30 min separates them) + benign stretches between; each period cut at
  flow-count quantiles 60/20/20 in time order, 1-minute gaps dropped (split="gap", rows kept), periods < 5 min -> train.
- Design was changed once before any model result (clock-time cuts left PortScan val with 2 flows); see notes.
- D10 evaluable families (test >= 100 and val >= 30): Bot, DDoS-LOIC-HTTP, DoS-GoldenEye, DoS-Hulk, DoS-SlowHTTPTest, DoS-Slowloris, FTP-Patator,
  SSH-Patator, PortScan, Web-BruteForce, Web-XSS. Not evaluable: Heartbleed (11), Infiltration (36), Web-SQLi (21).

## Held out for leave-one-attack-out in S7 (fixed now)
- D10: the 11 evaluable families above, one at a time; plus the groups DoS (4 types), WebAttack (BruteForce+XSS) and BruteForce (FTP+SSH).
  Priority: Bot (target: unseen Bot > 70% at the same false-alarm level), WebAttack, PortScan.
- D23 (external test 2017 -> 2018, whole dataset): evaluable Bot, DDoS-HOIC, DDoS-LOIC-HTTP, DDoS-LOIC-UDP, DoS-GoldenEye, DoS-Slowloris, Infiltration,
  SSH-Patator, Web-BruteForce. After cleaning, D23 DoS-Hulk, SlowHTTPTest and FTP-Patator are nearly empty or lack a val part: report, do not force.

## Host labels
- D10: attacker = 205.174.165.73 (seen as 172.16.0.1 behind NAT), victims 192.168.10.x from the data (web server .50 for most; Bot victims
  .15/.8/.9/.14/.5; Heartbleed .51; Infiltration .8). 336,230 of 336,234 attack flows have a documented attacker end (results/WP4/s1_hosts_d10.json).
- D23: only Tue-20-02 (DDoS-LOIC-HTTP: many external IPs -> 172.31.69.25); results/WP4/s1_hosts_d23.json.

## Pitfalls for later steps
- Rare-flow duplicates: the v2-style dedup collapses PortScan to 1,851 flows (from 158,930); window/host logic must use the stage files.
- Features IAT/Header/Init_Win/min_seg/URG differ between D10 and D01 (s1_gate_diag.json); never mix D01-trained models with D10 features.
- Test splits untouched so far (no model trained in S1).

## After S2 (2026-10-22): L1 rules (network/l1.py; report reports/WP4_S2.md, tables results/WP4/s2_tables.md)
- 5 layers (allow_pair, allow_service, proto_port, tcp_flags, flow_rate); fit benign train, 1% budget on benign val; frozen: known host = >= 10,000 benign train flows, port/proto pooled if < 1,000.
- D10 test FA ~1% per layer. Detection comes mostly from "flow to the rarely used web server 192.168.10.50" (99.75% of attack flows; 0.83% of benign): topology artefact, say so in M1-NET.
  allow_pair uses the single attacker address 172.16.0.1 (lab-specific). tcp_flags is the only behaviour-like L1 signal (Hulk 33%, SlowHTTP 76%, Slowloris 29%; PortScan 99% pre-dedup / 10% post-dedup).
- Blind: SSH-Patator (0%), FTP-Patator (allow_service 0%), Bot (flags 0%); D23 in-dataset ~0 detection; transfer D10 -> D23: allow-list FA 66-97%, tcp_flags FA 30.6% (flag semantics differ, RST = ECE column in D23).
- proto_port and flow_rate have AUC < 0.5 (attacks look ordinary / slower than benign): negative results.
- Compact tables for later steps: tools/WP4_S2_lib.py load_d10() / load_d23() (cache .../cache_v3/WP4/S2/; ids, 17 features, t in seconds).

## After S3 (2026-10-22): L2a host time-window layers (network/l2a.py; report reports/WP4_S3.md, tables results/WP4/s3_tables.md)
- Compact PRE-DEDUP streams: ../data_extra/cache_v3/WP4/S3/D10_stage.pkl, D23tue_stage.pkl (tools/WP4_S3_prep.py; ids factorised, minute index, split from final intervals). D10 time resolution = 1 minute.
- Layers: net.scan (W1), net.trw (W5), net.bruteforce (W1), net.dos_rate (W1), net.slow (W5); fit benign train, 1% on benign val. Test D10: PortScan 97, SSH 99, FTP 100, Hulk/GoldenEye/LOIC 100, SlowHTTP 85; blind: Bot, Web-*, Slowloris.
- AUDIT: D10 Thursday-Infiltration file has a benign-labelled scan by the compromised host; its benign flows are excluded from fit / calibration / headline FA (published-label FA also reported). Reversed flows: scan/TRW count only dst port < 32768.
- Macro over 11 families: tcp_flags alone 21%, + L2a 54%, L2a alone 62%. Learned logistic combiner is hurt by correlated layers (SSH 0.1%): use per-layer/OR views or rethink the combiner in S7.
- Transfer to D23 Tue: bruteforce/scan/trw FA 2-3% (bruteforce LOIC 99%); dos_rate needs refit (FA 40%).
- Helpers: tools/WP4_S3_lib.py (load, stream, fit_calibrate, flow_eval, window_eval).

## After S4 (2026-10-22): L2b beaconing (network/l2b.py net.beacon; report reports/WP4_S4.md, tables results/WP4/s4_tables.md, limit test s4_limit.json)
- Per (src,dst,port,proto) group, active minutes in a trailing 64-min window; cv / mad / tol / acf statistics learned as benign tails (N_MIN 6 active minutes); "rate" (sub-minute metronome) is a separate diagnostic, not in the layer score.
- Bot in D10 stage flows: train 1539 / val 109 / test 308; 5 real groups per split (5 bots -> one C2 :8080): burst of 5-8 flows/min then a beacon with 1-2 minute gaps (~100 s period, fixed shape 4 fwd / 3 bwd packets, ~80 ms).
- Test: Bot 36% of flows (3 of 5 groups; 2 groups with 85 flows never testable), FA 1.75% flow / 1.10% window; among testable flows benign FA 26.8% (benign groups are very regular on the 1-min grid): low precision. Harness Bot 0 -> 17.5% (combiner dilutes; OR view 36%).
- Resolvable period on the 1-min grid: 100 s .. 720 s (phase); below ~1.6 min and above ~12 min invisible. D23 Bot (Fri-02-03) has NO addresses (not evaluable). D23 Tue transfer FA 2.71%.
- Next: S5 flow-shape models (Bot has a very fixed flow shape). Helper: tools/WP4_S4_run.py (beacon_layers, add_beacon, bot_pairs).

## After S5 (2026-10-22): L3 normal-only flow models (network/l3.py; report reports/WP4_S5.md, tables results/WP4/s5_tables.md, acceptance s5_acceptance.json)
- net.l3_service (per protocol+port Mahalanobis + per-service score normalisation), net.l3_iforest, net.l3_ae (Keras 32-12-32 + per-service normalisation); fit benign train only; 60 "clean" columns (no IP/ports/Init-Win/RST-URG-ECE/duplicates); 76 columns gave no gain.
- D10 test FA 0.9-1.1% (AE published-label FA 5.9%: audited Infiltration file). Macro 11: service 35, iforest 13, AE 39. Rule-blind: Bot / Web-XSS / Web-BruteForce 0 for all (Bot AUC 0.90-0.97: in the benign tail, not above the 1% line; at 5% FA service 98%), Slowloris 78% (AE).
- Harness: tcp_flags + L2a 54.2 -> 61.0 with the three L3 layers (FA 0.74%); AE +5.0, service +3.3, iforest 0. Zero-shot D23 NOT transferable (FA 36 / 6.5 / 14%); refit on D23 FA ~1%: Slowloris 77-79, Web-XSS 45, LOIC 42 (AE), Bot 1%, Infiltration 3%: ON-NETWORK layers.
- Bot: test Bot flows are the beacon phase 3/3 packets ~1 s on 8080 (not the 4/3 ~80 ms burst of train); the same shape exists in benign (182 test flows): no flow-shape model should claim Bot. results/WP4/s5_bot_shapes.json.
- Helpers: tools/WP4_S5_lib.py (load_d10 with the aligned 76-feature matrix, frame, det_at_budget), cache ../data_extra/cache_v3/WP4/S5 (D10_X.npy, D23_eval.pkl; WP4 cache 6.0 GB).
- Next: S6 supervised XGBoost on the time split inside the harness.

## After S6 (2026-10-22): L4 supervised XGBoost (network/l4.py net.l4_xgb; report reports/WP4_S6.md, tables results/WP4/s6_tables.md, acceptance s6_acceptance.json)
- v2 model retrained on the v3 time split: binary XGBoost, 60 clean features (no IPs / ports / time / Flow ID), train = de-duplicated train flows (1.18 M, 183k attack), depth 3, lr 0.2, 616 trees (6 trials on validation), threshold 1% of benign validation. v2's 99.73% was D01 (different CICFlowMeter run): NOT comparable.
- D10 test (dedup rows = no exact copy across the split; stream rows next to it): FA 1.00% (stream 1.23, published labels 1.30), macro11 98.0% (stream 92.9). IN-DISTRIBUTION ceiling (time cut inside the attack windows): do not quote as generalisation.
- Null control (flow level, 5 seeds) mean AUC 0.477 (<= 0.55 met); top feature Bwd Pkt Len Std 24.7% (no dominant / capture-encoding feature).
- Bot: detected 98% only through the Ares C2 beacon signature (3 fwd / 3 bwd packets, ~1 s, port 8080, identical byte lengths). The BENIGN-labelled flows with that shape (train 403 / val 101 / test 165) are the five Bot hosts beaconing to 205.174.165.73:8080 inside the Friday PortScan / DDoS files = label noise
  (results/WP4/s6_bot_benign_shape.json). LOAO (validation): unseen Bot 0% (AUC 0.81); FTP 1, SSH 1, DoS group 2, SlowHTTP 29, PortScan 45, LOIC 63, GoldenEye 93, Web 80-99 (HTTP-like families stay in training), macro 55.9% vs base 61.5%; base OR L4-unseen 89.6% (FA 5.0 -> 5.9%).
- Harness (dedup rows): tcp_flags + L2a 65.1% (FA 0.80) -> + L4 98.0% (0.56); stream rows 54.2 -> 93.8. L4 alone 98.0% (FA 1.02). Beacon and on-network L3 add nothing once L4 is in.
- D23 zero-shot: FA 5.17% (> 5%, days 12-14% on 02-22 / 02-23), AUC 0.741 (LOIC-UDP 0.38, Infiltration 0.42), macro9 28.8%; re-calibrated 10.1%; on-network supervised refit (information) FA 1.0%, macro9 79.4%, AUC 0.968.
- Scope proposal: L4 = optional supervised layer, seen families, refit per network, outside the zero-shot headline stack.
- Helpers: tools/WP4_S6_lib.py (load_s6, sel, feat), cache ../data_extra/cache_v3/WP4/S6 (base_val.pkl / base_test.pkl = scores of tcp_flags, 5 L2a, beacon, L3 service + AE on the D10 stream rows with their calibrators in base_cal.pkl; l4_model.json; D10_in_final.npy). WP4 cache 6.1 GB.
- Next: S7 combiner + ablation + leave-one-attack-out (test side) + cross-dataset -> M1-NET.
