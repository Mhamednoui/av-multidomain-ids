# Datasets v3

Status on 20 Oct 2026. Disk free: 51.9 GB. Downloads pre-approved within
RULES 3.4 (user, 2026-10-19); put new data in `../data_extra/<id>_<name>/`; update this file (status, size on
disk, date, licence checked).

Sizes marked "(to confirm)" come from web searches on 20 Oct 2026 and must be checked on the
source page before downloading.

## 1. In hand

| Id | Dataset | Domain | Real / synthetic | Location | Size on disk | Licence | Notes |
|---|---|---|---|---|---|---|---|
| D01 | CICIDS2017 sample (from MTH-IDS) | network | real traffic, lab attacks | ../codes/data/CICIDS2017_sample.csv | small | see MTH-IDS (MIT) / CIC | no IPs, ports or timestamps; 22% duplicate flows |
| D02 | Car-Hacking (HCRL) | CAN | real car, injected attacks | ../codes/data/{DoS,Fuzzy,RPM,gear}_dataset.csv | ~1 GB | HCRL terms | attacks only in the first ~75-80% of each file |
| D03 | AV-GPS-Dataset | GPS | real slow robot | ../codes/data/AV-GPS-Dataset/ | small | see paper | files = several sessions glued; spoofed sessions show 0-1 satellites (artefact); file 0 = copy of part of file 1 |
| D04 | KITTI raw, 23 drives of 2011_09_26 (velodyne + oxts only) | LiDAR, GPS | real | 0001, 0015: ../codes/data/Depth/; 21 others: ../data_extra/kitti_raw/ | 7.6 GiB | CC BY-NC-SA 3.0 | frames ~0.1032 s apart; OXTS is RTK (too clean); scan file names repeat across drives |
| D05 | ROAD (ORNL) | CAN | real car, real verified attacks | ../data_extra/road/road/ | 3.4 GB | CC BY 4.0 | decoded signals + anonymized.dbc in signal_extractions/; microsecond timestamps; masquerade captures = edited copies |
| D06 | UAV Attack Dataset (live part extracted) | GPS | real drone, live HackRF spoofing + jamming | ../data_extra/gps_uav/ | 0.7 GB zip | IEEE DataPort open access | 3 live flights only (benign / jamming / spoofing): case study |

## 2. To download: batch A (needed by the plan)

| Id | Dataset | For | Real / synthetic | Size | Access / licence | Source |
|---|---|---|---|---|---|---|
| D10 | CICIDS2017 full labelled flows (GeneratedLabelledFlows, with IPs, ports, timestamps). DOWNLOADED 2026-10-21 to ../data_extra/D10_cicids2017_generated_flows/ (raw/GeneratedLabelledFlows.zip 283,876,488 B, sha256 7bdbef28... = HF LFS record; extracted/TrafficLabelling/ 8 CSV, 1.2 GB). SOURCE IS AN UNOFFICIAL MIRROR: https://huggingface.co/datasets/bencorn/CICIDS2017 (csvs/GeneratedLabelledFlows.zip). Official UNB site was unreachable (unb.ca "temporarily restricted" for off-campus users on 2026-10-21). Layout: 85 columns, leading space in header names (stripped by WP4 tools); 3,119,345 rows incl. 288,602 all-empty separator rows in Thursday-Morning-WebAttacks (labelled rows 2,830,743); labels = 15 known CICIDS2017 labels; Monday timestamp format dd/mm/yyyy. Details: notes/WP4_network.md, results/WP4/s0_d10_inventory.json | Unofficial mirror; card says licence "other"; CIC/UNB terms (research use, cite Sharafaldin et al. 2018). Integrity: sha256 matches the mirror's LFS record only, not checked against UNB | https://www.unb.ca/cic/datasets/ids-2017.html (official, currently restricted) |
| D11 | can-train-and-test (DTU, Lampe & Meng 2023). DOWNLOADED 2026-10-19 (figshare version 1, published 2023-12-15) | WP2: 4 vehicles (2011 Chevrolet Impala, 2011 Chevrolet Traverse, 2016 Chevrolet Silverado, 2017 Subaru Forester), 9+ attack types, known / unknown vehicle test splits | real cars, injected attacks | 7.47 GB extracted (1.51 GB zip, MD5 verified); free disk after: 44 GB | CC BY 4.0 (read from the DTU page and the figshare API) | ../data_extra/D11_can-train-and-test/can-train-and-test/ ; source https://data.dtu.dk/articles/dataset/can-train-and-test/24805533 (DOI 10.11583/DTU.24805533.v1); paper arXiv 2308.04972. Layout: section 5 |
| D12 | VeReMi Extension (Kamel et al. 2020; combined CSV by Slama et al.) | WP5: labelled V2X misbehaviour benchmark | simulated (Veins / SUMO, LuST) | DOWNLOADED 2026-10-19 to ../data_extra/D12_veremi_extension/ : mixalldata_clean.csv 1.21 GB (+ tar.xz 0.33 GB), 3,194,808 messages, 24,663 senders, class 0-19 (0 = genuine, 59.5%); columns sendTime, sender, senderPseudo, pos/spd/acl/hed x,y,z (+ noise cols), no receiver id / no per-simulation id | CC BY 4.0 (checked via Mendeley API) | https://data.mendeley.com/datasets/k62n4z9gdz ; WP5 S0 check: results/WP5/s0_data_check.json |
| D13 | V2AIX (RWTH ika, 2024) real ETSI ITS CAM; cite Hoffmann et al., arXiv 2403.10221 | WP5 real V2X messages | real | DOWNLOADED 2026-10-24 (user-provided sciebo link): ../data_extra/D13_v2aix/v2aix_json.zip (1.01 GB, 22.2 GB uncompressed, 2,228 files); 1,540 whole recordings (scenarios/*.json, 5.0 GB, all 13 strata) extracted to extracted/json/, parsed cache in cache/ (derived, never commit). CAM only (no DENM), 212,303 parsed CAMs in 1,515 recordings, ego GNSS (cohda / oxts) present, ego own CAMs absent. Inventory results/WP5/s0c_inventory.md, adapter v2x/v2aix.py, splits results/WP5/splits_v2aix.json | non-commercial research, cite paper, do NOT redistribute dataset or modified versions / per-message derived files (README.txt of the archive; only abstract derivatives such as trained models are allowed) | https://v2aix.ika.rwth-aachen.de |
| D14 | Tampa CV Pilot BSM sample (US DOT FHWA) | WP5 real BSMs | real | DOWNLOADED 2026-10-19 to ../data_extra/D14_tampa_bsm/bsm_sample.csv 39 MB: 34,464 BSMs, 226 vehicle ids (ids are per RSU: 19,527 distinct msgs after dedupe, ~38 physical vehicles, see reports/WP5_S1b.md), ONE day only (2021-03-19, 00:17-06:59 UTC), 72 vehicles with >=100 msgs; lat/long (1e-7 deg), speed, heading, secMark, accel, yaw present. Full raw data only via ITS DataHub Sandbox request | CC BY-SA 4.0 (Socrata metadata) | https://data.transportation.gov/d/nm7w-nvbm |
| D15 | OpenStreetMap highway ways, Karlsruhe (KITTI bbox + 1 km) | WP1 map matching, WP5 road plausibility | real map | 35.2 MB json (57,018 ways, 193,170 nodes) | ODbL 1.0; attribution (c) OpenStreetMap contributors | DOWNLOADED 2026-10-19 via Overpass API (OSM base 2026-10-19T21:54Z) to ../data_extra/D15_osm/karlsruhe_highways.json; see SOURCE.txt there |

Real V2X with labelled real attacks: none found (search 20 Oct 2026). Standard practice (e.g.
VCADS) = real field messages + physically consistent injected misbehaviour; VeReMi for
comparability. Newer candidates to check: VeReMi NextGen (Ulm, 2026, 15 attack types,
train / val / test splits), MisbehaviorX (IEEE DataPort, Veins, 68 attacks), V2X-PAD (NS-3).

## 3. Batch B (optional, decide per item)

| Id | Dataset | For | Size | Access / licence |
|---|---|---|---|---|
| D20 | KITTI raw camera images (image_02) + calibration for the 23 drives | WP3 camera cross-check of LiDAR objects | ~18 GB download again (zips), keep image_02 only (to confirm) | CC BY-NC-SA 3.0 |
| D21 | nuScenes v1.0-mini (6 cameras, 1 LiDAR, 5 radars) | WP3 radar / camera cross-check | a few GB (to confirm) | non-commercial, account |
| D22 | comma2k19, one ~10 GB chunk (CAN + raw GNSS + IMU + camera, same car). PARTLY DOWNLOADED 2026-10-22 (WP6 S1): Chunk_1 (8.73 GB zip on huggingface.co/datasets/commaai/comma2k19) read by HTTP range requests, only processed_log CAN / GNSS / IMU + global_pose kept (video, raw logs skipped): 538 MB transferred, 1.31 GB on disk in ../data_extra/D22_comma2k19/Chunk_1/ (20 routes, 189 one-minute segments, one car; "|" in route names replaced by "_"); tools/WP6_S1_comma_fetch.py | WP1 / WP2 / WP6: real CAN wheel speed + GNSS on one car (motion witnesses) | ~10 GB per chunk, 100 GB total | MIT (checked on the HF card, 2026-10-22); github.com/commaai/comma2k19 |
| D23 | CSE-CIC-IDS2018 processed CSVs. DOWNLOADED 2026-10-21 (all 10 files, complete) to ../data_extra/D23_cse-cic-ids2018/raw/ : 6,886,649,507 B (6.9 GB, below the 10 GB limit, so no day selection). Source https://cse-cic-ids2018.s3.ca-central-1.amazonaws.com/Processed%20Traffic%20Data%20for%20ML%20Algorithms/ (listing saved: results/WP4/s0_d23_s3_listing_raw.xml). Sizes match S3 listing; ETag is multipart (not plain MD5). Layout: 80 columns (Dst Port, Protocol, Timestamp, ...; Label), except Thuesday-20-02 with 84 columns and Src/Dst IP header names (Flow ID, Src IP, ...). 7 of 10 files at the Excel row limit (6 at exactly 1,048,575 data rows, 1 at 1,048,574): suspected truncation, to be checked. 16,232,943 data rows; label values per file in results/WP4/s0_d23_inventory.json | AWS open data, no account; licence as published on the CIC page (CIC research terms, cite Sharafaldin et al. 2018) | s3://cse-cic-ids2018/ |
| D24 | TOW-IDS automotive Ethernet (AVTP, gPTP, UDP-from-CAN; 5 attack scenarios). NOT DOWNLOADED: IEEE DataPort page shows "LOGIN TO ACCESS DATASET FILES" (checked 2026-10-21). User action: log in to IEEE DataPort and download, or tell the orchestrator to proceed with credentials. Licence CC BY 4.0 (page metadata) | WP4 in-vehicle Ethernet (closer to an AV than CICIDS) | to confirm | IEEE DataPort (login required for files), DOI 10.21227/bz0w-zc12; https://ieee-dataport.org/documents/tow-ids-automotive-ethernet-intrusion-dataset |
| D25 | VeReMi NextGen | WP5 | to confirm | Ulm University (OPARU) |
| D26 | UrbanNav (Hong Kong urban canyons: GNSS RINEX, IMU, LiDAR) | WP1 realistic urban GNSS errors | 17-43 GB per sequence | academic; low priority |
| D27 | OpenStreetMap drivable highway ways, Tampa (D14 bbox + ~300 m) | WP5 S3 map / road plausibility on Tampa BSMs | real map | DOWNLOADED 2026-10-19 via Overpass API (OSM base 2026-10-19T22:42Z) to ../data_extra/D27_osm_tampa/tampa_highways.json 1.4 MB: 1,782 ways, 6,934 nodes, drivable classes only; see SOURCE.txt there | ODbL 1.0; attribution (c) OpenStreetMap contributors | https://www.openstreetmap.org |
| D28 | OTIDS (Kia Soul CAN, HCRL): attack-free + DoS / Fuzzy / Impersonation captures (4 files, 0.41 GB). In hand since v1, added to this file in WP8 S1 (decision 4, 2026-11-03) | CAN | real car, injected attacks | ../codes/data/Attack_free_dataset.txt, ../codes/data/DoS_attack_dataset.txt, ../codes/data/Fuzzy_attack_dataset.txt, ../codes/data/Impersonation_attack_dataset.txt | 0.41 GB | HCRL dataset terms (research use; cite Lee et al. 2017 OTIDS); exact licence text to confirm on the source page | source: HCRL (Hanyang Univ., OCSLab) OTIDS data, page URL to confirm (not re-checked online in S1). WP8 use: V31_val = Attack_free first 30% of frames; H31 = the rest of Attack_free + the 3 attack files at capture level only (no per-frame labels) |
| D02n | Car-Hacking (HCRL) normal_run: attack-free drive of the same vehicle as D02 (Hyundai YF Sonata). In hand since v1, added to this file in WP8 S1 (decision 4, 2026-11-03) | CAN | real car, no attacks | ../codes/data/normal_run_data.txt | 0.09 GB (87,371,776 B) | HCRL dataset terms, as D02; exact licence text to confirm on the source page | source: HCRL (Hanyang Univ., OCSLab) Car-Hacking dataset, same source as D02, page URL to confirm (not re-checked online in S1). WP8 use: H31 clean false alarms on this vehicle (fresh, never scored by v3) |

## 4. Rough disk plan

Batch A: ~8 GB without D13; ~28 GB with the full V2AIX JSON (prefer a subset of drives).
Batch B items one at a time. Keep at least 15 GB free at all times.

## 5. D11 can-train-and-test: layout (WP2 S0, 2026-10-19)

Folder `../data_extra/D11_can-train-and-test/` holds `raw/can-train-and-test.zip` (1,507,455,719 B,
MD5 bd6509d670c0a0009cb3ecab34111bcd = published) and the extracted `can-train-and-test/`
(README.md + `set_01..set_04`/`{train_01, test_01_known_vehicle_known_attack,
test_02_unknown_vehicle_known_attack, test_03_known_vehicle_unknown_attack,
test_04_unknown_vehicle_unknown_attack}`/`<attack>-<n>.csv`). 236 CSV, 193,240,845 frames.
Columns: `timestamp, arbitration_id (hex str), data_field (hex str, no DLC column), attack (0/1)`.
Known / unknown vehicle per set: set_01 Impala / Silverado; set_02 Traverse / Subaru;
set_03 Silverado / Subaru; set_04 Subaru / Traverse. Full numbers: `results/WP2/s0_inventory.json`,
`s0_summary.txt`. Caveats: many files are byte-identical copies shared across sets (174 distinct
of 236); timestamps start at the synthetic epoch 1672531200.0 in every file; small timestamp
inversions around injected frames. CORRECTED by WP2 S1 (2026-10-20, reports/WP2_S1.md):
12,527 inversions in 100 files, down to -7.9 ms, 12,394 adjacent to an injected frame: keep
recorded order, use `dt_clipped`, never use the sign of dt as a feature. set_01/test_04 is NOT
Silverado: its 12 files are byte copies of set_02/test_01 (Traverse, confirmed by ID-set
fingerprint); 41 files with non-discriminative ID sets take the subset's majority vehicle
(source recorded per file). 32,378 frames with empty data_field (dlc 0), all in fuzzing files;
one file has a trailing tab. 62 duplicate pairs, none inside one set.
