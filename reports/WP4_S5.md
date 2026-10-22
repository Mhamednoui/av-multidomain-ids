# WP4 S5: L3 normal-only flow models (per-service profile, isolation forest, autoencoder)

Date: 2026-10-22    Worker: sonnet high (WP4 S5)

## Summary (tables: results/WP4/s5_tables.md; numbers: results/WP4/s5_d10.json, s5_d23.json, s5_dev_val.json, s5_acceptance.json, s5_bot_shapes.json)
- Three layers in network/l3.py, fitted on BENIGN TRAIN flows only (no attack label in fit), 1% tie-safe budget on benign validation, ONE verdict run on test (D10 stage stream of S3 / S4, same split and audit exclusion; D23 fixed-seed sample, all days):
  net.l3_service (per (protocol, destination port) Mahalanobis profile, shrunk covariance, per-service score normalisation), net.l3_iforest (200 trees, max_samples 2048, max_features 0.5), net.l3_ae (Keras dense 32-12-32, MSE, per-service normalisation).
- Feature hygiene: not features: IPs, Flow ID, timestamp, source port, destination port / protocol (grouping only). The "clean" set also drops TCP-stack fingerprints (Init Win bytes, Seg Size Min), flag columns that differ between CICFlowMeter versions
  (RST / URG / CWE / ECE) and duplicate columns. 76-column ablation: no gain from the dropped columns (macro 35.1 vs 35.3 service, 9.1 vs 13.5 iforest, 35.3 vs 39.0 AE for all-76 vs clean).
- Acceptance (notes/WP4_network.md, written before any score): D1 MET (FA 0.92 / 1.12 / 1.02%; published labels 1.01 / 1.06 / 5.90%: the audited Infiltration file hits the AE).
  D2 NOT MET (only the AE reaches >= 50% on one rule-blind family, Slowloris 78%; Bot 0, Web-XSS 0, Web-BruteForce 0 for all three).
  D3 MET (harness tcp_flags + L2a macro 54.2 -> 61.0 with the three L3 layers, +6.8 points, combined FA 0.33 -> 0.74%; AE alone adds +5.0, service +3.3, iforest 0).
  D4 statement: no L3 layer alarms on Bot at all (0 of 308), so there is no Bot hit that could be a signature. D5 zero-shot NOT transferable (D23 benign FA 36.1 / 6.5 / 14.2% at the D10 threshold); refit on D23: FA 0.96 / 1.00 / 1.03% (met). D6, D7 done.
- Do normal-only models catch what the rules miss? Mostly NO at the 1% budget (service / iforest / AE, D10 test): Bot 0 / 0 / 0, Web-XSS 0 / 0 / 0, Web-BruteForce 0 / 0 / 0, Slowloris 50 / 15 / 78%; Infiltration (6 test flows, not evaluable) 100 / 67 / 33%.
  The families are not invisible but sit in the benign tail: median benign-rank of Bot 0.98 / 0.96 / 0.92, per-family AUC of Bot 0.97 / 0.95 / 0.90; at a 5% budget (diagnostic only) Bot is caught 98 / 96 / 1%, Web-BruteForce 14 / 5 / 0%, Web-XSS 2 / 2 / 0%.
  What L3 adds to the stack is on families the rules half-see (harness): Slowloris 8.5 -> 71.9%, SlowHTTPTest 93.5 -> 99.2, PortScan 97.4 -> 99.0.
- Bot signature (D4): train Bot flows to 8080 are 4 fwd / 3 bwd packets, 62-123 ms (73% of 840), but the validation / test Bot flows are the later beacon phase: 3 fwd / 3 bwd packets, about 1.0 s (96% of 308 test flows; 302 to port 8080); only 3 test Bot flows match the train signature.
  Benign flows have that same beacon-phase shape on 8080 (441 train, 115 val, 182 test benign flows with 3/3 packets and 0.99-1.05 s), so a model fitted on benign has seen the shape and calls it normal. Honest reading: Bot is not catchable by flow shape alone at 1% FA on this data; do not claim it.
- Per family, D10 test, AE (best layer): PortScan 98, SlowHTTPTest 97, Slowloris 78, DDoS-LOIC 62, Hulk 60, GoldenEye 32; service profile: FTP-Patator 100, SSH-Patator 51, Hulk 63, SlowHTTPTest 84; iforest is the weakest layer (SlowHTTPTest 80) and adds nothing in the harness.
  On the de-duplicated flows only the service profile gives SSH 96 / Hulk 88 / PortScan 43 (vs 51 / 63 / 2 pre-dedup): multiplicity matters as in S3.
- Attributions (top alarms): service profile: Hulk = FIN flag (92%), Slowloris = SYN flag (74%), FTP = SYN flag (92%), SSH = Fwd / Bwd IAT Min; AE: PortScan = PSH + ACK flag counts (59%), GoldenEye = Idle times; iforest: Idle Mean / Max / Std.
  Benign false alarms are mostly ports 53 (37 / 39%) and 443 (25 / 24%) for service / AE (DNS and TLS flows with unusual idle / active times); full tables s5_tables.md section 6. Many top features are flag counts and idle times, so the models partly re-learn what L1 / L2a already see.
- D23 (sample, test side): zero-shot is unusable at the D10 threshold (service FA 36%, one day 100%: D23 benign scores are 4.7x the D10 median); with the threshold re-calibrated on D23 benign validation (no refit) the macro AUC stays low (service 0.52, iforest 0.68, AE 0.60).
  Refit on D23 benign, detection at 1% FA (service / iforest / AE): Slowloris 79 / 37 / 77, Web-XSS 45 / 8 / 45, Web-BruteForce 25 / 24 / 25, LOIC-HTTP 3 / 0 / 42, Infiltration 3 / 4 / 3 (18,880 flows), Bot 0.9 / 0.5 / 0.9 (35,623 flows, AUC 0.90-0.97), SSH 0.
  Normal-only L3 is an ON-NETWORK layer, like dos_rate.
- Compute: the first AE (sklearn MLPRegressor) needed 27 min per fit on the busy machine; replaced by Keras on CPU (seconds per epoch); no GPU used, no lock.

## Acceptance rule (notes/WP4_network.md, 2026-10-22 "S5 plan", before any score) and result
| rule | result |
|---|---|
| D1 FA <= 2% each layer (headline without audit file; published labels also) | MET: 0.92 / 1.12 / 1.02% (published 1.01 / 1.06 / 5.90%) |
| D2 some layer >= 50% on >= 2 of the 4 rule-blind families | NOT MET (AE: Slowloris only) |
| D3 harness macro +5 points on tcp_flags + L2a at FA <= 2% | MET: 54.2 -> 61.0 (+6.8), FA 0.74% |
| D4 Bot signature statement | no alarms on Bot; the shape also occurs in benign traffic; see above |
| D5 zero-shot FA <= 5% on D23 benign; refit FA <= 2% | zero-shot NOT MET (36.1 / 6.5 / 14.2%); refit met (0.96 / 1.00 / 1.03%) |
| D6 hygiene and attributions | done (s5_tables.md sections 3, 6) |
| D7 per-family with n, Infiltration | done; D10 Infiltration has 6 test flows (not evaluable), D23 18,880 |

## What was done
- network/l3.py, tests/network/test_l3.py (10 tests; full suite 283/283), tools/WP4_S5_prep.py (D10 features aligned to the S3 stage rows), _prep_d23.py (sample drawn once), _explore.py, _dev.py, _lib.py, _run.py, _tables.py, _botshape.py.
- Cache: ../data_extra/cache_v3/WP4/S5 (D10_X.npy 0.86 GB, D23_eval.pkl 0.5 GB; WP4 cache 6.0 GB, limit 7 GB); smoke outputs deleted.
- Selection on validation (attack validation used for selection only, recorded): rule "highest mean detection of the four rule-blind families, ties -> macro". blind4 is tied across models (only Slowloris is ever caught), so macro decided: service maha floor 0.1 + per-service normalisation, iforest (2048, 0.5), AE (32,12,32) + per-service normalisation.
  Pass 1 grid (rz_mean, rz_top3, maha, hbos, iforest, AE) showed AUC 0.84-0.99 but 0-1% detection of Bot / Web at 1% FA (rz and hbos negative: AUC 0.48-0.67); pass 2 added per-service normalisation (helps FTP / SSH, not Bot / Web). Both passes recorded (s5_dev_val.json, logs/s5_dev_val_pass1.json).

## Caveats
1. Validation basis for the rule-blind families is small (Bot 109 flows from 5 bot sources, Web-XSS 97); the selection was driven by Slowloris and macro, not by Bot.
2. Per-service normalisation uses 300k benign train flows other than those the model was fitted on (service profile: a sample of the same flows). Thresholds are calibrated on benign validation as usual.
3. The AE is the layer most hurt by the Thursday Infiltration label problem (published-label FA 5.9%): the benign-labelled scanning host is an anomaly to it; the headline FA excludes that file as decided in S3.
4. D23 is a sample (benign 8 / 20 / 30% of train / val / test, attack flows capped at 60k per family and split, seed 42, drawn before scoring); D23 has no audit analogue examined.
5. The harness combiner is the S3 / S4 logistic combiner: with L3 added it still dilutes SSH (2.7% vs 99.3% in the OR view). The OR of base + L3 reaches Slowloris 99.6% but its FA is 5.45% (budgets add up). Per-layer and OR views are in s5_tables.md.
6. The beacon layer is not part of the S5 harness (optional in the brief).

## Questions / proposed next step
- Accept D2 / D5 NOT MET and keep the L3 layers as optional ON-NETWORK extras (AE and service profile; iforest dropped as it adds nothing)? Proposal for S7: headline stack = tcp_flags + L2a (+ AE / service as an on-network option); Bot, Web-XSS, Web-BruteForce reported as not detected by normal-only flow models.
- S6 (supervised XGBoost on the time split) can use attack labels; the finding that the beacon-phase Bot shape also occurs in benign traffic (about 0.05% of benign flows on 8080) limits any flow-shape model for Bot: S6 should report Bot with leave-one-attack-out.
