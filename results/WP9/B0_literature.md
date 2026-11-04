# WP9 B0: literature bar (best published detection results, protocols, sources)

Collected 2026-11-03/04 by web search and by opening the pages named in `status`. Every number below was read on a page we opened,
except rows marked `snippet` (search-result text only: UNVERIFIED) and `secondary` (taken from another paper that cites it).
bar: LFC leak-free-comparable, LEAKY random/unstated split, CRIT criticism of a protocol or dataset, DATA dataset paper without a readable number.

## What is a fair bar for a leak-free, seen-attack evaluation

1. **Almost every published headline is leaky or unstated.** Car-Hacking: F1 0.998-1.0 per attack under random 7:3 splits of overlapping
   frames (Hoang & Kim 2022) or an 80/20 split of unstated kind (Guerra et al. 2024). CICIDS2017: RF F1 0.94-0.998 per day (Pekar & Jozsa).
   VeReMi Extension: F1 0.93-0.998 on DoS-family types with a 70/30 split inside each dataset (Baharlouei et al. 2024; Asensio-Garriga as cited).
   GPS (AV-GPS): MLP mean F1 0.944 with stratified 5-fold (Abrar et al.). None of these is a bar we should claim to beat; they are the
   numbers a reader will have in mind, and our leak-free numbers will be lower. Say so in B5.
2. **The only protocols at least as strict as ours that we could read:**
   - can-train-and-test: capture-disjoint train / test, with unknown-vehicle and unknown-attack subsets (set_01 F1 0.95-0.998 for the best of 18 models,
     but the mean over models is 0.42-0.46 and many strong-looking learners collapse to F1 near 0).
   - CICIDS2017 temporal / group splits (Moczkodan & Ragab 2026, preprint): macro-F1 0.89 at best on 20-flow windows; random-split numbers are higher.
   - ROAD (Guerra et al.): not capture-level as far as stated, yet multiclass mean F1 0.32 and DCNN 0.65-0.75: ROAD is not solved even under a possibly leaky split.
3. **Fair bar by dataset (seen attacks, leak-free, fixed false-alarm budget):**
   - Car-Hacking: no leak-free published number found. Bar = "near 1.0 detection at 1% window FA" is plausible for DoS / Fuzzy / RPM / Gear because L1 rules already reach ~100% (WP2); the bar to state is our block-split number, compared with the leaky 0.998-1.0.
   - ROAD: no leak-free number found. Bar = per-capture-family recall at 1% FA; published F1 0.32-0.75 (multiclass / DCNN) are the only honest-looking comparators.
   - can-train-and-test: F1 about 0.95-0.998 (best learners, known and unknown subsets, set_01 only); mean over learners about 0.45. A fair claim: >= 0.98 F1 on test_01 and test_03 with a 1% FA budget and report test_02 / test_04 separately.
   - CICIDS2017 / CSE-CIC-IDS2018: published 0.99 numbers are not leak-free (duplicates 21.1% / 33.3% in our WP4 counts; label and flow errors per Engelen, Lanvin, Liu). Fair bar: macro-F1 about 0.85-0.90 on time / group splits (Moczkodan & Ragab, windows) after dedup; report per-family recall at 1% benign FA, not accuracy.
   - VeReMi Extension: published numbers are within-family DoS only. Our WP5 result (scored-row mean 83.0% over 13 seen classes at 1.1% FA, sender split) is stricter; no published number is comparable. State "no comparable published number".
   - GPS: AV-GPS F1 0.944 (stratified folds, single attack) is the only readable comparator; the cross-dataset cases (F1 0.90-0.965) are the closest to leak-free. No published GPS result exists on KITTI or comma2k19.
   - LiDAR: object-level accuracy > 94% (Shadow-Catcher, KITTI) and TPR > 85% at FPR < 10% (ADoPT, nuScenes) are not scan-level FA-budget numbers; at a 1% budget they are not comparable. Claim nothing beyond "comparable metric not available".
4. **Rule for B5 (WP9 file rule: no claim "best" without same metric and a protocol at least as strict):** a row may use the word "better" only
   against a published number whose protocol was read and is group / capture / time based. Everything else is labelled "reported under a random split".
5. **Open gaps in this survey (not found or not readable in B0):** Song 2020 original numbers; Verma 2024 baseline numbers; Engelen 2021 and Lanvin 2022
   per-class numbers; any peer-reviewed leak-free CSE-CIC-IDS2018 number; VeReMi Extension original benchmark (Kamel 2020); CARLO original paper; any GPS-spoofing
   result on KITTI or comma2k19. Rows from search snippets are marked UNVERIFIED in the tables and must not be quoted until opened.


## Tables

### Car-Hacking (HCRL)

| bar | reference | venue, year, id | metric / result | split protocol | dedup | attacks | status |
|---|---|---|---|---|---|---|---|
| LEAKY | Hoang & Kim, Supervised Contrastive ResNet and Transfer Learning for the In-vehicle IDS | arXiv preprint 2022; arXiv:2207.10814 | SupCon ResNet per attack F1 0.9997-0.9999, FNR 0.02-0.06%, precision 1.0 (DoS, Fuzzy, Gear, RPM) NOTE: overlapping frames may straddle the split; paper does not address it | random 7:3 split of overlapping CAN-ID frames (stride 15), 5 runs averaged | not mentioned | seen (per-attack classes) | opened |
| LEAKY | Guerra et al., AI-Driven IDS on the ROAD Dataset: Comparative Analysis (Table 4, Car-Hacking part) | arXiv 2024 (ACM DOI listed on arXiv page: 10.1145/3689936.3694696; venue not named there); arXiv:2408.17235 | F1 DoS/Fuzzy/Gear/RPM: RF, LightGBM, LCCDE 1.0000 all; DCNN 0.9980-0.9996; TAN 0.9957-0.9999; LSTM 0.9179-1.0000 NOTE: precision / recall / F1 only, no accuracy or FPR | 80/20 split, random-or-not NOT stated; SMOTE on train only; windows step 1 for TAN/DCNNv2 | not mentioned | seen | opened |
| LEAKY | Song, Woo, Kim, In-vehicle network intrusion detection using deep convolutional neural network | Vehicular Communications 21:100198, 2020; DOI 10.1016/j.vehcom.2019.100198 | abstract: 'significantly low FNR and error rate'; numbers NOT read (paywalled). Reproduced by Guerra et al.: DCNN F1 0.9980-0.9996 NOTE: original numbers unverified; reproduction value is secondary | not read | not read | seen | abstract |
| LEAKY | Hoang & Kim, Semi-supervised Convolutional Adversarial Autoencoders | arXiv preprint 2022; arXiv:2204.01193 | F1 up to 0.99, error 0.1% with limited labels; abstract claims unknown-attack detection (no number read) NOTE: dataset identity and unseen-attack number unverified | not read; abstract page does not name Car-Hacking | not read | seen + claimed unknown | abstract |
| CRIT | Lampe & Meng, can-train-and-test (section on prior datasets) | arXiv preprint 2023; arXiv:2308.04972 | CRITIQUE: Car-Hacking recorded with the vehicle parked, engine running; attack-free vs attack captures differ outside the injections (timestamps normalised in can-train-and-test for this reason) NOTE: supports using block / capture splits and not trusting random-row numbers | - | - | - | opened |
| CRIT | MTH-IDS (Yang, Moubayed, Shami), unseen-attack evaluation: DoS / gear / RPM 100% detection, fuzzy F1 about 0.84 | IEEE IoT Journal 2022 (venue per our memory: UNVERIFIED); arXiv:2105.13289 | numbers from search snippet only NOTE: UNVERIFIED: open the paper before citing; only unseen-attack number found for Car-Hacking | unseen-attack setting (per snippet) | unknown | unseen (per snippet) | snippet |

### ROAD (ORNL)

| bar | reference | venue, year, id | metric / result | split protocol | dedup | attacks | status |
|---|---|---|---|---|---|---|---|
| DATA | Verma et al., A Comprehensive Guide to CAN IDS Data & Introduction of the ROAD Dataset | PLoS ONE 19(1), 2024 (venue from arXiv page); arXiv:2012.14600 | dataset paper; baseline numbers NOT read (PDF > 10 MB for the fetch tool) NOTE: masquerade captures are edited copies (as in our DATASETS.md D05) | - | - | fabrication, masquerade (simulated in post-processing, timing opaque), fuzzing, real attacks | abstract |
| LEAKY | Guerra et al., AI-Driven IDS on ROAD (Tables 6, 7) | arXiv 2024; arXiv:2408.17235 | binary per attack F1: LSTM 1.0000 on all 11 classes; TAN 0.0194-0.9976; DCNN mean F1 0.6514, DCNNv2 0.7468. Multiclass: LCCDE mean F1 0.3212 (SD 0.1723); RF masquerade F1 0.0 NOTE: even with a possibly leaky split, multiclass and several binary results are far from 1.0; LSTM = 1.0 everywhere is a leakage red flag | 80/20, random-or-not NOT stated; SMOTE on train; windows step 1; Accelerator attacks excluded (labels withheld) | not mentioned | seen (all 11 classes in train) | opened |
| DATA | Hoang & Kim and others on ROAD | -; - | no ROAD result from other peer-reviewed papers found/opened in B0 NOTE: gap: no leak-free (capture-level) ROAD baseline located | - | - | - | not found |

### can-train-and-test (DTU)

| bar | reference | venue, year, id | metric / result | split protocol | dedup | attacks | status |
|---|---|---|---|---|---|---|---|
| LFC | Lampe & Meng, can-train-and-test (set_01 baselines) | arXiv preprint 2023 (DOI 10.11583/DTU.24805533.v1 = data); arXiv:2308.04972 | set_01, accuracy/F1: test1 known veh+known atk: LogReg 0.9890/0.9878, BIRCH 0.9889/0.9834, IsoForest 0.9846/0.9812, MLP 0.9788/0.9811 (RF F1 0.0015, ExtraTrees 0.4442); test2 unknown veh: BIRCH 0.9745/0.9620, MLP 0.9666/0.9594, LogReg 0.9565/0.9539 NOTE: metric is probably the attack-class or overall F1 (not stated in the text read); only set_01 reported; many baselines collapse (F1 near 0) | dataset-defined: train capture set vs 4 test subsets (known/unknown vehicle x known/unknown attack); captures disjoint | no explicit dedup (authors: unique samples about half of lines in the .log/.csv pairs) | known and unknown attacks | opened |
| LFC | Lampe & Meng (same paper), test3 / test4 | arXiv 2023; arXiv:2308.04972 | test3 known veh+unknown atk: GradBoost 0.9977/0.9966, LogReg 0.9976/0.9964, BIRCH 0.9976/0.9965, MLP 0.9974/0.9964; test4 unknown veh+unknown atk: BIRCH 0.9990/0.9984, GradBoost 0.9984/0.9982, MLP 0.9973/0.9976. Mean F1 over 18 models: test2 0.4214, test3 0.4581, test4 0.4472 NOTE: test3/4 table header was cut in the fetched text; rows matched to the appendix by the fetch summary: treat as likely, not certain | as above | as above | unknown attacks | opened |
| CRIT | Kidmose & Meng, can-sleuth: Investigating and Evaluating Automotive IDS Datasets | EICC 2024 (ACM); DOI 10.1145/3655693.3655696 | 16 ML IDSs on hcrl-ch, hcrl-sa, can-train-and-test; 8 of 16 reach mean F1 > 0.9 on can-train-and-test NOTE: authors of can-train-and-test; claims it separates models better than hcrl-ch | per dataset splits | not read | known/unknown | abstract |

### CICIDS2017

| bar | reference | venue, year, id | metric / result | split protocol | dedup | attacks | status |
|---|---|---|---|---|---|---|---|
| CRIT | Engelen, Rimmer, Joosen, Troubleshooting an Intrusion Detection Dataset: the CICIDS2017 Case Study | IEEE S&P Workshops (SPW) 2021, pp 7-12; DOI 10.1109/SPW53761.2021.00009 | CRITIQUE: traffic generation, flow construction, feature extraction and labelling errors; more than 20% of traffic relabelled/reconstructed; modified CICFlowMeter released NOTE: per-class numbers not read (PDF unreadable by fetch tool) | - | - | - | abstract |
| CRIT | Lanvin et al., Errors in the CICIDS2017 dataset and the significant differences in detection performances it makes | CRiSIS 2022, LNCS 13857 pp 18-33; DOI 10.1007/978-3-031-31108-6_2 (Springer link seen in search) | CRITIQUE: packet misordering, packet duplication, attacks performed but unlabelled (PortScan); corrected dataset changes measured performance NOTE: numbers not read | - | duplicated packets found | - | abstract (via search listing) |
| LEAKY | Pekar & Jozsa, Evaluating ML-Based Anomaly Detection Across Datasets of Varied Integrity | Computers & Networks (accepted 2024); arXiv:2401.16843 | RF F1 on original CICIDS2017 per day, binary / multiclass: Tue 0.8709 / 0.9925, Wed 0.9874 / 0.9906, Thu 0.9404 / 0.9979, Fri 0.9977 / 0.9977. Corrected sets (WTMC-2021, CRiSIS-2022) similar: authors do not confirm large gains NOTE: RF stays at 0.94-0.998 on every version: single-flow RF is easy on this set | split ratio not stated in text read; per-day | 288,602 NaN flows removed; duplicates not described | seen (all classes) | opened |
| LFC | Moczkodan & Ragab, Do Transformers Actually Help Intrusion Detection? Temporal Sequence Evaluation on CIC-IDS2017 | arXiv preprint 2026; arXiv:2606.11098 | 9 models, random vs time (first 80% / last 20%) vs group-by-5-tuple splits; best macro-F1 0.89 (Transformer, non-padded windows); class-balanced RF the most robust; snippet-level claim: Transformer FPR 0.04% -> 2.7% under leakage-free evaluation (NOT verified in the PDF pages read) NOTE: preprint; windows of T=20 flows, so not a per-flow number; same paper lists other works: 99.20% (CNN-LSTM-Transformer) and 91.06% accuracy (Yao et al.) as reported random-split results (secondary) | random 80/20 stratified, time 80/20, group 80/20 by 5-tuple; windows built after the split | no flow dedup described (inf rows dropped) | seen | opened (pp 1-4) |
| DATA | Sharafaldin, Lashkari, Ghorbani, Toward Generating a New IDS Dataset and Intrusion Traffic Characterization | ICISSP 2018, pp 108-116; DOI 10.5220/0006639801080116 | dataset paper; classifier numbers NOT read NOTE: original CICFlowMeter labelling, known to contain the errors above | not read | - | - | abstract |
| CRIT | Sinkron journal 2025 (random vs single temporal vs rolling temporal split on CIC-IDS2017) | Sinkron 2025 (per search snippet); https://jurnal.polgan.ac.id/index.php/sinkron/article/download/16227/4139/31487 | snippet: random split gives F1 near 1.0 for several models; temporal lower NOTE: UNVERIFIED, not opened | random vs temporal | unknown | seen | snippet |

### CSE-CIC-IDS2018

| bar | reference | venue, year, id | metric / result | split protocol | dedup | attacks | status |
|---|---|---|---|---|---|---|---|
| CRIT | Liu, Engelen, Lynar, Essam, Joosen, Error Prevalence in NIDS datasets: CIC-IDS-2017 and CSE-CIC-IDS-2018 | IEEE CNS 2022, pp 254-262; DOI 10.1109/CNS56114.2022.9947235 | CRITIQUE: many undocumented errors in creation and labelling of both datasets; corrected re-creation published NOTE: numbers not read | - | - | - | abstract (via search listing) |
| CRIT | Leevy & Khoshgoftaar, A survey and analysis of intrusion detection models based on CSE-CIC-IDS2018 Big Data | Journal of Big Data 2020 (DOI not verified); - | survey: best per-study scores very high, possibly overfitting; data-cleaning information inadequate NOTE: UNVERIFIED snippet; no peer-reviewed leak-free CSE-CIC-IDS2018 number found in B0 | varies | inadequately documented | seen | snippet |
| CRIT | preprint (June 2026) on CSE-CIC-IDS2018 / CIC-DDoS2019: random vs class-stratified vs class-blind temporal split | preprints.org 202606.0903 (per snippet); - | snippet: random and class-stratified temporal give similar results, class-blind temporal differs; near-neighbour traffic across a random split = memorisation NOTE: UNVERIFIED, not opened | random vs temporal | unknown | seen | snippet |

### VeReMi / VeReMi Extension

| bar | reference | venue, year, id | metric / result | split protocol | dedup | attacks | status |
|---|---|---|---|---|---|---|---|
| DATA | Kamel, Sonnleitner, Kargl et al., VeReMi Extension: A Dataset for Comparable Evaluation of Misbehavior Detection in VANETs | IEEE ICC 2020; DOI 10.1109/ICC40277.2020.9149132 (HAL hal-02492739) | dataset paper with local-detector benchmark; numbers NOT read (HAL blocked) | - | - | 19 attack types (class 0-19 in the combined CSV) | abstract (via search listing) |
| LEAKY | Baharlouei, Makanju, Zincir-Heywood, Evaluating the Robustness of ADVENT on the VeReMi-Extension Dataset | IFIP/IEEE CNSM 2024; dl.ifip.org/db/conf/cnsm/cnsm2024/1571071980.pdf | attack-onset detection: detection rate about 95% (figure), FNR 4.26-4.97%, FPR 1.41-3.48% (centralised); prior ADVENT work F1 99.66% (onset) and 97.85% (malicious node); node-level (time-sliced) F1 up to about 97 (figure) NOTE: numbers read from bar charts are approximate; only DoS/DDoS types | 70% train / 30% test of each dataset, per vehicle; DoS family only (5 types) | not mentioned | seen DoS family only | opened |
| LEAKY | Asensio-Garriga et al. (cited inside Baharlouei et al.) | venue not read; - | F1 99.06 (DoS), 97.97 (DoS Disruptive), 92.56 (Disruptive Sybil), 99.77 (DoS Random), 94.46 (Random Sybil) NOTE: original paper not opened | not read | not read | seen DoS family | secondary |
| LEAKY | VeMisNet (MDPI J. Sens. Actuator Netw. 14(5):100, 2025) | MDPI 2025; https://www.mdpi.com/2224-2708/14/5/100 | snippet: BiLSTM, 99.81% accuracy and F1 on 500 K samples NOTE: UNVERIFIED | not read (HTTP 403) | unknown | seen | snippet |
| CRIT | Sultana et al. 2022 (comparison of ML/DL on VeReMi Extension) and PAMPOS preprint (benign-only transformer, VeReMi++, AUC up to 0.98, F1 up to 0.95) | 2022 / arXiv 2605.06833 (2026); - | snippets only: deep models miss offset-type attacks; benign-trained transformer handles unseen attacks on VeReMi++ (a different dataset) NOTE: UNVERIFIED, not opened | unknown | unknown | seen / unseen | snippet |

### GPS spoofing (AV-GPS, UAV, KITTI/comma2k19)

| bar | reference | venue, year, id | metric / result | split protocol | dedup | attacks | status |
|---|---|---|---|---|---|---|---|
| LEAKY | Abrar et al., GPS-IDS: Anomaly-based GPS Spoofing Detection Framework for Autonomous Vehicles (introduces AV-GPS-Dataset) | arXiv preprint v2, Dec 2024; arXiv:2405.08359 | real data, MLP mean F1 0.944 (Case I 0.965, II 0.964, III 0.905), RF 0.919, XGB 0.915; MLP at tuned threshold FPR 0.0021, FNR 0.0012 (thresholds tuned on Dataset 3); detection delay 10 s NOTE: the cross-dataset cases (train on one set, test the others) are closer to leak-free; sets are 636-62,042 rows, one RC rover testbed; our DATASETS.md D03 notes sessions glued and a file copy | stratified 5-fold (80/20) on each real dataset + cross-dataset test of the other datasets; fold split NOT by session | not mentioned | one spoof type (Gaussian-noise-stealth); no unseen type | opened |
| DATA | Whelan et al., UAV Attack Dataset (live HackRF spoofing + jamming) | IEEE DataPort; DOI 10.21227/00dg-0d12 | dataset only; no detection result on the page NOTE: authors recommend the live part over the simulated part | - | - | spoofing, jamming, MAVLink DoS | abstract |
| DATA | Nayfeh et al., Real-time ML-based GPS Spoofing Solution for Location-dependent UAV Applications | IEEE eIT 2023; DOI 10.1109/eIT57321.2023.10187344 | abstract only: 'acceptable performance', no numbers; dataset from earlier work NOTE: no usable bar | not stated | - | static / dynamic spoofing | abstract |
| DATA | KITTI-based and comma2k19-based GPS spoofing detection | -; - | no peer-reviewed detection result found: attacks on KITTI/comma2k19 are injected by each author NOTE: our KITTI/comma attacks have no published comparator; say so in B5 | - | - | - | not found |

### LiDAR spoofing (KITTI)

| bar | reference | venue, year, id | metric / result | split protocol | dedup | attacks | status |
|---|---|---|---|---|---|---|---|
| LEAKY | Hau, Demetriou, Munoz-Gonzalez, Lupu, Shadow-Catcher: Looking Into Shadows to Detect Ghost Objects in AV 3D Sensing | ESORICS 2021; arXiv:2008.12008 | >94% accuracy identifying anomalous shadows (vehicles, pedestrians, cyclists); 0.003-0.021 s per object NOTE: object-level accuracy, not per-scan FPR at a fixed budget: not comparable to our scan-level numbers | object-level validation of injected ghost objects; split protocol NOT read | not read | ghost objects (injection), single attack family | abstract |
| LEAKY | Cho, Cao, Zhou, Mao, ADoPT: LiDAR Spoofing Attack Detection Based on Point-Level Temporal Consistency | BMVC 2023 (per arXiv comment); arXiv:2310.14504 | nuScenes (NOT KITTI): FPR < 10%, TPR > 85%; outperforms CARLO and 3D-TC2 NOTE: different dataset; FPR 10% is far above our 1% budget | not read | - | dense and sparse point injection | abstract |
| CRIT | Cross-Modal Phantom (arXiv 2604.21841) and measurement study (arXiv 2303.10555) | arXiv 2026 / 2023; - | snippets: 85.5% attack success on 400 KITTI scenes against PointPillars (attack side); earlier work often assumed unvalidated attacker capabilities NOTE: UNVERIFIED; relevant to RULES 5.7 (attack realism): published detection rates mostly use idealised injections | - | - | - | snippet |
