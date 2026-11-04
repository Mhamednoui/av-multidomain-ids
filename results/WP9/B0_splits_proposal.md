# WP9 B0: proposed leak-free splits and metrics per dataset (benchmark track)

Rules applied (WP9 file + RULES.md 5): dedup exact rows first, split by group (capture / vehicle / time block / drive / recording), lock the split in
`locks/WP9_<dataset>.json` before training, validation for every choice, test scored once (B5). Existing v3 splits are reused when they already satisfy this.
Facts about existing splits come from `notes/WP2_brief.md`, `notes/WP4_brief.md`, `notes/WP5_brief.md`, `notes/WP1_brief.md`, `notes/WP3_brief.md`, and the split files named below (not re-opened beyond their headers).

## Metrics reported for every dataset (so the numbers are comparable to the literature and to RULES 5.5)
- Primary: detection rate (recall) of attack units at a fixed false-alarm budget set on validation benign data (1% of normal units), plus ROC-AUC. Unit = frame / window / flow / message as stated.
- For literature comparability: precision, recall, F1 (attack = positive, and macro-F1 over families) and accuracy, all at that validation threshold, plus FPR at the test.
  Literature uses F1 and accuracy; accuracy alone is misleading (can-train-and-test shows accuracy 0.99 with F1 0.00 for several learners).
- Per attack family: recall at the budget; leave-one-family-out as extra row where the dataset has enough families (the zero-shot angle of v3).
- Uncertainty: block bootstrap over test captures / drives / time blocks (not over rows).
- Controls: shuffled-label control for each learned unit; feature-importance red flag (WP9 rule, v3 rule).
- Every row labelled "seen attack types, standard dataset"; random-split literature numbers are quoted only as "reported under a random / unstated split".

## Car-Hacking (HCRL, D02, D02n)
- Problem: one drive per attack file, attacks only in the first ~73-80% of each file (`results/WP2/s1_carhacking.json`: last attack row fraction 0.73-0.80); consecutive frames are near-identical; random splits are the source of the 0.998-1.0 numbers.
- Dedup: do not drop identical (id, payload) frames (periodic traffic repeats legitimately and the dataset has no per-frame uniqueness); dedup = remove byte-identical files and rows identical in (timestamp, id, payload). Count and report.
- Split: reuse the v2/WP2 S1 time-block split (train / val / test blocks inside each file, block_class_counts in `results/WP2/s1_carhacking.json`; matches v2 so v2 comparisons stay valid) with a gap of 1 s between blocks and windows built after the split. Add normal_run (D02n) as pure-benign validation/test false-alarm data (fresh).
- Unit: frame and 1 s window (window label = at least one injected frame), as WP2.
- Caveat to print next to the result: single vehicle, attack and attack-free segments of the same file differ in context (parked vehicle; Lampe & Meng).

## ROAD (D05)
- Reuse the WP2 S1 capture-level split (`results/WP2/s1_road.json`: each capture has `part` train / val / test; ambient captures and attack families spread across the three parts).
- Masquerade captures are edited copies of the attack logs: checked in `s1_road.json`, every masquerade capture is in the same part as its source attack capture (good). Note max_engine_coolant_temp has one attack capture, in test only: its family is UNSEEN in train, so it cannot be a seen-attack row (report as unseen, or move it only with a documented, pre-training decision).
- Accelerator captures have no labels: exclude from supervised scoring (as Guerra et al.), keep only as whole-capture alarm-rate check.
- Metrics: window recall at 1% clean-window FA per family (fuzzing, fabrication, masquerade, each signal), AUC, window F1 for comparability. Note that the WP2 rule-based stack already reports 5/5 masquerade; B1 must beat that with a supervised model or report that it does not.

## can-train-and-test (D11)
- Reuse `results/WP2/splits_d11.json` (4 sets; train minus a val hold-out of the highest-numbered capture of each attack family; test_01..04 = known / unknown vehicle x known / unknown attack as published; byte-identical files kept once by sha256 with precedence train > val > test).
- Report test_01 and test_03 as "seen attack" rows and test_02 / test_04 separately (unknown vehicle); run sets 01-04 and report the mean and spread, so the number can be set beside Lampe & Meng set_01 (they report set_01 only).
- Dedup: sha256 file-level already done; add exact-row dedup of (id, payload, timestamp) inside captures; their statement that unique samples are about half of the lines (.log and .csv copies) means do not double-count.
- Metrics: attack-class F1 and accuracy (their metric, to be confirmed in the CSV labels) plus recall at 1% FA.

## CICIDS2017 (D10)
- Reuse the WP4 S1 split: per day, periods = attack windows + benign stretches, each cut 60/20/20 by flow count in time order with 1-minute gaps (`notes/WP4_brief.md`); exact-duplicate removal (596,376 of 2,830,743 labelled rows = 21.1%) and conflicting-label removal (542) already applied.
- Changes needed for B2: (a) report the known label/flow errors (Engelen 2021, Lanvin 2022): mention that WP4 uses the original CICFlowMeter labels, so PortScan is unlabelled in parts and rare families lose flows after dedup (PortScan collapses with v2-style dedup, so use the stage files for host logic); (b) exclude non-evaluable families (Heartbleed 11, Infiltration 36, Web-SQLi 21 test flows) from per-family claims; (c) also report a 5-tuple / host-pair group split as a second view (Moczkodan & Ragab protocol) because time cuts keep conversations whole only within a period.
- Metrics: macro-F1 over the 11 evaluable families, per-family recall at 1% benign FA, AUC; no accuracy headline.

## CSE-CIC-IDS2018 (D23)
- Reuse the WP4 time-period split; D23 dedup removed 5,410,812 duplicates (33.3%) and 43,572 conflicting rows (`notes/WP4_brief.md`).
- Known problems: 7 of 10 files stop at 1,048,575 rows as published (Fri-16-02 ends at 13:xx, Hulk val 0); only Tue-20-02 has IPs and ports; D23 DoS-Hulk, SlowHTTPTest and FTP-Patator nearly empty after cleaning. Report per-family only where val and test have enough flows (the WP4 rule); do not force the others.
- Use also as external test (train 2017, test 2018) as WP4 did; feature semantics differ (RST = ECE column), so retrain on the 76-column D23 names.
- Metrics as CICIDS2017.

## VeReMi / VeReMi Extension (D12)
- Reuse `results/WP5/splits_veremi.json` (train 15,578 / val 2,121 / test 5,533 senders; split by sender id; the combined CSV has no simulation or receiver id). Test uses 10 time blocks for bootstrap CIs.
- Weakness to state: senders of one simulation can sit on both sides (no simulation id), so receiver-side neighbour context may leak. Mitigation: use only per-sender features and per-message residual features (the WP5 deployable set) and report that cross-sender features are excluded; if D25 (VeReMi NextGen / raw VeReMi logs) is obtained, redo by simulation.
- Seen-attack row: all attack classes except the held-out WP5 types 6, 12, 17 are "seen"; B3 may add 6 and 17 back to training for the seen-attack row but must say that the test split is then not the WP5 zero-shot test (type 12 stays excluded, zero-placeholder artefact).
- Dedup: exact repeated messages are labelled separately (WP5: exact repeats, replay) and are reported, not dropped (they are the replay attack).
- Metrics: per-class recall at 1% genuine-message FA (scored rows and all rows), message-level F1/accuracy for comparability, sender-level detection at k chosen on validation (WP5).

## GPS (AV-GPS D03, UAV D06, KITTI OXTS D04/D04b, comma2k19 D22)
- KITTI: reuse the WP1 drive split (TEST 0001 0005 0095 0039 0079 0028 0052; VAL 0011 0035 0027; rest train; LODO thresholds over the 16 train+val drives). Attacks are injected by us (no public KITTI GPS-spoof benchmark exists): label rows "seen injected attack, our generator" and keep one family unseen in training.
- comma2k19: split by route and by chunk (Chunk_1 as dev; Chunk_2 / Chunk_4 are the fresh WP8 H31 chunks, so use them as test only if B4 states they were scored by WP8; Chunk_3 and 4 share one dongle); never split inside a route.
- AV-GPS-Dataset: the only set with a published number (Abrar et al.). Split by session (cut files at the glued-session boundaries; D03 note: file 0 is a copy of part of file 1, drop it; spoofed sessions with 0-1 satellites are an artefact: report with and without the satellite-count feature). Use the paper's three cross-dataset cases (train on one set, test on the others) as the comparable row, not stratified folds.
- UAV Attack Dataset: 3 live flights, case study only (flight-level, no statistics).
- Metrics: run-level detection at 1% clean-run FA with drive-cluster intervals (WP1 style), AUC; F1 per window for comparability with Abrar et al.

## LiDAR spoofing on KITTI (D04, D04b)
- Reuse the WP3 drive split (same TEST / VAL / train drives); attacked scans use the clean previous scan; scan file names repeat across drives, so group id = `<drive>/<file>` (WP3).
- No public detection benchmark on KITTI scans at a fixed FA budget. Published numbers are object-level accuracy (Shadow-Catcher) or nuScenes TPR/FPR (ADoPT); report scan-level recall at 1% clean-scan FA and also object-level accuracy of the shadow-type check if cheap, labelled "not comparable".
- Attack realism (RULES 5.7): keep the WP3 findings (single-return calibrated phantoms are not detected beyond FA; multi-return add near 69% is the impossible-attacker comparison); do not report detection of an attack a real attacker could not mount as a benchmark win.

## Order of work and what B1-B4 should lock
1. B1 CAN: Car-Hacking (WP2 block split), ROAD (WP2 capture split), D11 (splits_d11.json).
2. B2 network: WP4 splits for D10 and D23, plus 5-tuple group view.
3. B3 V2X: splits_veremi.json.
4. B4 GPS + LiDAR: WP1 / WP3 drive split; AV-GPS session split.
5. Each: write `locks/WP9_<dataset>.json` (split ids, hashes, dedup counts) before training.
