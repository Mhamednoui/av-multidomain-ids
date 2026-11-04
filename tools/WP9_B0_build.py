"""WP9 B0: build results/WP9/B0_literature.{json,md} from the hand-collected rows below.

Purpose: one source of truth for the literature bar (md tables are generated from the same rows as the json).
Inputs: none (rows typed from pages opened during B0, 2026-11-03/04; `status` says how each row was checked).
Outputs: results/WP9/B0_literature.json, results/WP9/B0_literature.md (tables part; the prose part is in
results/WP9/B0_prose_part.md and appended).
status: opened = page/PDF text read in B0; abstract = only abstract/landing page read; secondary = number taken from
another paper that cites it (that paper was opened); snippet = web-search snippet only (UNVERIFIED).
protocol: random = random rows/windows; random? = split method not stated; group = by capture/vehicle/time; none-stated.
bar: LFC = leak-free-comparable; LEAKY = random/unstated split (inflated); CRIT = criticism of a protocol/dataset;
DATA = dataset paper without a detection number we could read.
"""
import json
import os

R = []


def row(ds, ref, venue, ident, metric, protocol, dedup, attacks, status, bar, note=""):
    R.append(dict(dataset=ds, ref=ref, venue_year=venue, id=ident, metric=metric, protocol=protocol,
                  dedup=dedup, attacks=attacks, status=status, bar=bar, note=note))


CH = "Car-Hacking (HCRL)"
row(CH, "Hoang & Kim, Supervised Contrastive ResNet and Transfer Learning for the In-vehicle IDS", "arXiv preprint 2022",
    "arXiv:2207.10814", "SupCon ResNet per attack F1 0.9997-0.9999, FNR 0.02-0.06%, precision 1.0 (DoS, Fuzzy, Gear, RPM)",
    "random 7:3 split of overlapping CAN-ID frames (stride 15), 5 runs averaged", "not mentioned",
    "seen (per-attack classes)", "opened", "LEAKY", "overlapping frames may straddle the split; paper does not address it")
row(CH, "Guerra et al., AI-Driven IDS on the ROAD Dataset: Comparative Analysis (Table 4, Car-Hacking part)",
    "arXiv 2024 (ACM DOI listed on arXiv page: 10.1145/3689936.3694696; venue not named there)", "arXiv:2408.17235",
    "F1 DoS/Fuzzy/Gear/RPM: RF, LightGBM, LCCDE 1.0000 all; DCNN 0.9980-0.9996; TAN 0.9957-0.9999; LSTM 0.9179-1.0000",
    "80/20 split, random-or-not NOT stated; SMOTE on train only; windows step 1 for TAN/DCNNv2", "not mentioned",
    "seen", "opened", "LEAKY", "precision / recall / F1 only, no accuracy or FPR")
row(CH, "Song, Woo, Kim, In-vehicle network intrusion detection using deep convolutional neural network",
    "Vehicular Communications 21:100198, 2020", "DOI 10.1016/j.vehcom.2019.100198",
    "abstract: 'significantly low FNR and error rate'; numbers NOT read (paywalled). Reproduced by Guerra et al.: DCNN F1 0.9980-0.9996",
    "not read", "not read", "seen", "abstract", "LEAKY", "original numbers unverified; reproduction value is secondary")
row(CH, "Hoang & Kim, Semi-supervised Convolutional Adversarial Autoencoders", "arXiv preprint 2022", "arXiv:2204.01193",
    "F1 up to 0.99, error 0.1% with limited labels; abstract claims unknown-attack detection (no number read)",
    "not read; abstract page does not name Car-Hacking", "not read", "seen + claimed unknown", "abstract", "LEAKY",
    "dataset identity and unseen-attack number unverified")
row(CH, "Lampe & Meng, can-train-and-test (section on prior datasets)", "arXiv preprint 2023", "arXiv:2308.04972",
    "CRITIQUE: Car-Hacking recorded with the vehicle parked, engine running; attack-free vs attack captures differ outside the injections (timestamps normalised in can-train-and-test for this reason)",
    "-", "-", "-", "opened", "CRIT", "supports using block / capture splits and not trusting random-row numbers")
row(CH, "MTH-IDS (Yang, Moubayed, Shami), unseen-attack evaluation: DoS / gear / RPM 100% detection, fuzzy F1 about 0.84",
    "IEEE IoT Journal 2022 (venue per our memory: UNVERIFIED)", "arXiv:2105.13289",
    "numbers from search snippet only", "unseen-attack setting (per snippet)", "unknown", "unseen (per snippet)", "snippet",
    "CRIT", "UNVERIFIED: open the paper before citing; only unseen-attack number found for Car-Hacking")

RD = "ROAD (ORNL)"
row(RD, "Verma et al., A Comprehensive Guide to CAN IDS Data & Introduction of the ROAD Dataset",
    "PLoS ONE 19(1), 2024 (venue from arXiv page)", "arXiv:2012.14600",
    "dataset paper; baseline numbers NOT read (PDF > 10 MB for the fetch tool)", "-", "-",
    "fabrication, masquerade (simulated in post-processing, timing opaque), fuzzing, real attacks", "abstract", "DATA",
    "masquerade captures are edited copies (as in our DATASETS.md D05)")
row(RD, "Guerra et al., AI-Driven IDS on ROAD (Tables 6, 7)", "arXiv 2024", "arXiv:2408.17235",
    "binary per attack F1: LSTM 1.0000 on all 11 classes; TAN 0.0194-0.9976; DCNN mean F1 0.6514, DCNNv2 0.7468. Multiclass: LCCDE mean F1 0.3212 (SD 0.1723); RF masquerade F1 0.0",
    "80/20, random-or-not NOT stated; SMOTE on train; windows step 1; Accelerator attacks excluded (labels withheld)",
    "not mentioned", "seen (all 11 classes in train)", "opened", "LEAKY",
    "even with a possibly leaky split, multiclass and several binary results are far from 1.0; LSTM = 1.0 everywhere is a leakage red flag")
row(RD, "Hoang & Kim and others on ROAD", "-", "-", "no ROAD result from other peer-reviewed papers found/opened in B0", "-", "-", "-",
    "not found", "DATA", "gap: no leak-free (capture-level) ROAD baseline located")

CT = "can-train-and-test (DTU)"
row(CT, "Lampe & Meng, can-train-and-test (set_01 baselines)", "arXiv preprint 2023 (DOI 10.11583/DTU.24805533.v1 = data)",
    "arXiv:2308.04972",
    "set_01, accuracy/F1: test1 known veh+known atk: LogReg 0.9890/0.9878, BIRCH 0.9889/0.9834, IsoForest 0.9846/0.9812, MLP 0.9788/0.9811 (RF F1 0.0015, ExtraTrees 0.4442); test2 unknown veh: BIRCH 0.9745/0.9620, MLP 0.9666/0.9594, LogReg 0.9565/0.9539",
    "dataset-defined: train capture set vs 4 test subsets (known/unknown vehicle x known/unknown attack); captures disjoint",
    "no explicit dedup (authors: unique samples about half of lines in the .log/.csv pairs)", "known and unknown attacks",
    "opened", "LFC", "metric is probably the attack-class or overall F1 (not stated in the text read); only set_01 reported; many baselines collapse (F1 near 0)")
row(CT, "Lampe & Meng (same paper), test3 / test4", "arXiv 2023", "arXiv:2308.04972",
    "test3 known veh+unknown atk: GradBoost 0.9977/0.9966, LogReg 0.9976/0.9964, BIRCH 0.9976/0.9965, MLP 0.9974/0.9964; test4 unknown veh+unknown atk: BIRCH 0.9990/0.9984, GradBoost 0.9984/0.9982, MLP 0.9973/0.9976. Mean F1 over 18 models: test2 0.4214, test3 0.4581, test4 0.4472",
    "as above", "as above", "unknown attacks", "opened", "LFC",
    "test3/4 table header was cut in the fetched text; rows matched to the appendix by the fetch summary: treat as likely, not certain")
row(CT, "Kidmose & Meng, can-sleuth: Investigating and Evaluating Automotive IDS Datasets", "EICC 2024 (ACM)",
    "DOI 10.1145/3655693.3655696", "16 ML IDSs on hcrl-ch, hcrl-sa, can-train-and-test; 8 of 16 reach mean F1 > 0.9 on can-train-and-test",
    "per dataset splits", "not read", "known/unknown", "abstract", "CRIT", "authors of can-train-and-test; claims it separates models better than hcrl-ch")

C17 = "CICIDS2017"
row(C17, "Engelen, Rimmer, Joosen, Troubleshooting an Intrusion Detection Dataset: the CICIDS2017 Case Study",
    "IEEE S&P Workshops (SPW) 2021, pp 7-12", "DOI 10.1109/SPW53761.2021.00009",
    "CRITIQUE: traffic generation, flow construction, feature extraction and labelling errors; more than 20% of traffic relabelled/reconstructed; modified CICFlowMeter released",
    "-", "-", "-", "abstract", "CRIT", "per-class numbers not read (PDF unreadable by fetch tool)")
row(C17, "Lanvin et al., Errors in the CICIDS2017 dataset and the significant differences in detection performances it makes",
    "CRiSIS 2022, LNCS 13857 pp 18-33", "DOI 10.1007/978-3-031-31108-6_2 (Springer link seen in search)",
    "CRITIQUE: packet misordering, packet duplication, attacks performed but unlabelled (PortScan); corrected dataset changes measured performance",
    "-", "duplicated packets found", "-", "abstract (via search listing)", "CRIT", "numbers not read")
row(C17, "Pekar & Jozsa, Evaluating ML-Based Anomaly Detection Across Datasets of Varied Integrity", "Computers & Networks (accepted 2024)",
    "arXiv:2401.16843", "RF F1 on original CICIDS2017 per day, binary / multiclass: Tue 0.8709 / 0.9925, Wed 0.9874 / 0.9906, Thu 0.9404 / 0.9979, Fri 0.9977 / 0.9977. Corrected sets (WTMC-2021, CRiSIS-2022) similar: authors do not confirm large gains",
    "split ratio not stated in text read; per-day", "288,602 NaN flows removed; duplicates not described", "seen (all classes)", "opened", "LEAKY",
    "RF stays at 0.94-0.998 on every version: single-flow RF is easy on this set")
row(C17, "Moczkodan & Ragab, Do Transformers Actually Help Intrusion Detection? Temporal Sequence Evaluation on CIC-IDS2017",
    "arXiv preprint 2026", "arXiv:2606.11098",
    "9 models, random vs time (first 80% / last 20%) vs group-by-5-tuple splits; best macro-F1 0.89 (Transformer, non-padded windows); class-balanced RF the most robust; snippet-level claim: Transformer FPR 0.04% -> 2.7% under leakage-free evaluation (NOT verified in the PDF pages read)",
    "random 80/20 stratified, time 80/20, group 80/20 by 5-tuple; windows built after the split", "no flow dedup described (inf rows dropped)", "seen",
    "opened (pp 1-4)", "LFC", "preprint; windows of T=20 flows, so not a per-flow number; same paper lists other works: 99.20% (CNN-LSTM-Transformer) and 91.06% accuracy (Yao et al.) as reported random-split results (secondary)")
row(C17, "Sharafaldin, Lashkari, Ghorbani, Toward Generating a New IDS Dataset and Intrusion Traffic Characterization",
    "ICISSP 2018, pp 108-116", "DOI 10.5220/0006639801080116", "dataset paper; classifier numbers NOT read",
    "not read", "-", "-", "abstract", "DATA", "original CICFlowMeter labelling, known to contain the errors above")
row(C17, "Sinkron journal 2025 (random vs single temporal vs rolling temporal split on CIC-IDS2017)", "Sinkron 2025 (per search snippet)",
    "https://jurnal.polgan.ac.id/index.php/sinkron/article/download/16227/4139/31487",
    "snippet: random split gives F1 near 1.0 for several models; temporal lower", "random vs temporal", "unknown", "seen", "snippet", "CRIT",
    "UNVERIFIED, not opened")

C18 = "CSE-CIC-IDS2018"
row(C18, "Liu, Engelen, Lynar, Essam, Joosen, Error Prevalence in NIDS datasets: CIC-IDS-2017 and CSE-CIC-IDS-2018",
    "IEEE CNS 2022, pp 254-262", "DOI 10.1109/CNS56114.2022.9947235",
    "CRITIQUE: many undocumented errors in creation and labelling of both datasets; corrected re-creation published",
    "-", "-", "-", "abstract (via search listing)", "CRIT", "numbers not read")
row(C18, "Leevy & Khoshgoftaar, A survey and analysis of intrusion detection models based on CSE-CIC-IDS2018 Big Data",
    "Journal of Big Data 2020 (DOI not verified)", "-", "survey: best per-study scores very high, possibly overfitting; data-cleaning information inadequate",
    "varies", "inadequately documented", "seen", "snippet", "CRIT", "UNVERIFIED snippet; no peer-reviewed leak-free CSE-CIC-IDS2018 number found in B0")
row(C18, "preprint (June 2026) on CSE-CIC-IDS2018 / CIC-DDoS2019: random vs class-stratified vs class-blind temporal split",
    "preprints.org 202606.0903 (per snippet)", "-", "snippet: random and class-stratified temporal give similar results, class-blind temporal differs; near-neighbour traffic across a random split = memorisation",
    "random vs temporal", "unknown", "seen", "snippet", "CRIT", "UNVERIFIED, not opened")

VM = "VeReMi / VeReMi Extension"
row(VM, "Kamel, Sonnleitner, Kargl et al., VeReMi Extension: A Dataset for Comparable Evaluation of Misbehavior Detection in VANETs",
    "IEEE ICC 2020", "DOI 10.1109/ICC40277.2020.9149132 (HAL hal-02492739)", "dataset paper with local-detector benchmark; numbers NOT read (HAL blocked)",
    "-", "-", "19 attack types (class 0-19 in the combined CSV)", "abstract (via search listing)", "DATA", "")
row(VM, "Baharlouei, Makanju, Zincir-Heywood, Evaluating the Robustness of ADVENT on the VeReMi-Extension Dataset",
    "IFIP/IEEE CNSM 2024", "dl.ifip.org/db/conf/cnsm/cnsm2024/1571071980.pdf",
    "attack-onset detection: detection rate about 95% (figure), FNR 4.26-4.97%, FPR 1.41-3.48% (centralised); prior ADVENT work F1 99.66% (onset) and 97.85% (malicious node); node-level (time-sliced) F1 up to about 97 (figure)",
    "70% train / 30% test of each dataset, per vehicle; DoS family only (5 types)", "not mentioned", "seen DoS family only", "opened", "LEAKY",
    "numbers read from bar charts are approximate; only DoS/DDoS types")
row(VM, "Asensio-Garriga et al. (cited inside Baharlouei et al.)", "venue not read", "-",
    "F1 99.06 (DoS), 97.97 (DoS Disruptive), 92.56 (Disruptive Sybil), 99.77 (DoS Random), 94.46 (Random Sybil)",
    "not read", "not read", "seen DoS family", "secondary", "LEAKY", "original paper not opened")
row(VM, "VeMisNet (MDPI J. Sens. Actuator Netw. 14(5):100, 2025)", "MDPI 2025", "https://www.mdpi.com/2224-2708/14/5/100",
    "snippet: BiLSTM, 99.81% accuracy and F1 on 500 K samples", "not read (HTTP 403)", "unknown", "seen", "snippet", "LEAKY", "UNVERIFIED")
row(VM, "Sultana et al. 2022 (comparison of ML/DL on VeReMi Extension) and PAMPOS preprint (benign-only transformer, VeReMi++, AUC up to 0.98, F1 up to 0.95)",
    "2022 / arXiv 2605.06833 (2026)", "-", "snippets only: deep models miss offset-type attacks; benign-trained transformer handles unseen attacks on VeReMi++ (a different dataset)",
    "unknown", "unknown", "seen / unseen", "snippet", "CRIT", "UNVERIFIED, not opened")

GP = "GPS spoofing (AV-GPS, UAV, KITTI/comma2k19)"
row(GP, "Abrar et al., GPS-IDS: Anomaly-based GPS Spoofing Detection Framework for Autonomous Vehicles (introduces AV-GPS-Dataset)",
    "arXiv preprint v2, Dec 2024", "arXiv:2405.08359",
    "real data, MLP mean F1 0.944 (Case I 0.965, II 0.964, III 0.905), RF 0.919, XGB 0.915; MLP at tuned threshold FPR 0.0021, FNR 0.0012 (thresholds tuned on Dataset 3); detection delay 10 s",
    "stratified 5-fold (80/20) on each real dataset + cross-dataset test of the other datasets; fold split NOT by session", "not mentioned",
    "one spoof type (Gaussian-noise-stealth); no unseen type", "opened", "LEAKY",
    "the cross-dataset cases (train on one set, test the others) are closer to leak-free; sets are 636-62,042 rows, one RC rover testbed; our DATASETS.md D03 notes sessions glued and a file copy")
row(GP, "Whelan et al., UAV Attack Dataset (live HackRF spoofing + jamming)", "IEEE DataPort", "DOI 10.21227/00dg-0d12",
    "dataset only; no detection result on the page", "-", "-", "spoofing, jamming, MAVLink DoS", "abstract", "DATA",
    "authors recommend the live part over the simulated part")
row(GP, "Nayfeh et al., Real-time ML-based GPS Spoofing Solution for Location-dependent UAV Applications", "IEEE eIT 2023", "DOI 10.1109/eIT57321.2023.10187344",
    "abstract only: 'acceptable performance', no numbers; dataset from earlier work", "not stated", "-", "static / dynamic spoofing", "abstract", "DATA", "no usable bar")
row(GP, "KITTI-based and comma2k19-based GPS spoofing detection", "-", "-", "no peer-reviewed detection result found: attacks on KITTI/comma2k19 are injected by each author",
    "-", "-", "-", "not found", "DATA", "our KITTI/comma attacks have no published comparator; say so in B5")

LD = "LiDAR spoofing (KITTI)"
row(LD, "Hau, Demetriou, Munoz-Gonzalez, Lupu, Shadow-Catcher: Looking Into Shadows to Detect Ghost Objects in AV 3D Sensing",
    "ESORICS 2021", "arXiv:2008.12008", ">94% accuracy identifying anomalous shadows (vehicles, pedestrians, cyclists); 0.003-0.021 s per object",
    "object-level validation of injected ghost objects; split protocol NOT read", "not read", "ghost objects (injection), single attack family", "abstract", "LEAKY",
    "object-level accuracy, not per-scan FPR at a fixed budget: not comparable to our scan-level numbers")
row(LD, "Cho, Cao, Zhou, Mao, ADoPT: LiDAR Spoofing Attack Detection Based on Point-Level Temporal Consistency", "BMVC 2023 (per arXiv comment)",
    "arXiv:2310.14504", "nuScenes (NOT KITTI): FPR < 10%, TPR > 85%; outperforms CARLO and 3D-TC2", "not read", "-", "dense and sparse point injection", "abstract", "LEAKY",
    "different dataset; FPR 10% is far above our 1% budget")
row(LD, "Cross-Modal Phantom (arXiv 2604.21841) and measurement study (arXiv 2303.10555)", "arXiv 2026 / 2023", "-",
    "snippets: 85.5% attack success on 400 KITTI scenes against PointPillars (attack side); earlier work often assumed unvalidated attacker capabilities", "-", "-", "-", "snippet", "CRIT",
    "UNVERIFIED; relevant to RULES 5.7 (attack realism): published detection rates mostly use idealised injections")

ORDER = [CH, RD, CT, C17, C18, VM, GP, LD]

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "WP9")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "B0_literature.json"), "w", encoding="utf-8") as f:
        json.dump(dict(generated_by="tools/WP9_B0_build.py", legend=__doc__.split("status:")[1], rows=R), f, indent=1, ensure_ascii=False)
    prose = open(os.path.join(out, "B0_prose_part.md"), encoding="utf-8").read()
    L = ["# WP9 B0: literature bar (best published detection results, protocols, sources)", "",
         "Collected 2026-11-03/04 by web search and by opening the pages named in `status`. Every number below was read on a page we opened,",
         "except rows marked `snippet` (search-result text only: UNVERIFIED) and `secondary` (taken from another paper that cites it).",
         "bar: LFC leak-free-comparable, LEAKY random/unstated split, CRIT criticism of a protocol or dataset, DATA dataset paper without a readable number.", ""]
    L.append(prose)
    L.append("")
    L.append("## Tables")
    for ds in ORDER:
        L += ["", "### " + ds, "", "| bar | reference | venue, year, id | metric / result | split protocol | dedup | attacks | status |", "|---|---|---|---|---|---|---|---|"]
        for r in R:
            if r["dataset"] == ds:
                c = lambda s: str(s).replace("|", "/")
                L.append("| %s | %s | %s; %s | %s%s | %s | %s | %s | %s |" % (r["bar"], c(r["ref"]), c(r["venue_year"]), c(r["id"]), c(r["metric"]),
                         (" NOTE: " + c(r["note"])) if r["note"] else "", c(r["protocol"]), c(r["dedup"]), c(r["attacks"]), r["status"]))
    open(os.path.join(out, "B0_literature.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(len(R), "rows")
