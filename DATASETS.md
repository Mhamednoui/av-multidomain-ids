# Datasets v3

Status on 20 Oct 2026. Disk free: 51.9 GB. Download only after the user approves the size
(RULES 3.4); put new data in `../data_extra/<id>_<name>/`; update this file (status, size on
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
| D10 | CICIDS2017 full labelled flows (GeneratedLabelledFlows, with IPs, ports, timestamps) | WP4: host / time logic, time split | real lab traffic | ~0.3 GB zip (to confirm) | UNB CIC (form), mirrors exist: verify against the official files | https://www.unb.ca/cic/datasets/ids-2017.html |
| D11 | can-train-and-test (DTU, Lampe & Meng 2023; v1.5 by Kidmose & Meng 2024) | WP2: 4 vehicles (Chevrolet, Subaru), 9 attacks, known / unknown vehicle test splits | real cars | 7.5 GB | DTU data repository (licence to check) | https://data.dtu.dk/articles/dataset/can-train-and-test/24805533 ; paper arXiv 2308.04972 |
| D12 | VeReMi Extension (Kamel et al. 2020) | WP5: labelled V2X misbehaviour benchmark (comparable with literature) | simulated (Veins / SUMO, Luxembourg scenario) | ~3.2 M labelled messages (size to confirm) | Mendeley Data (licence to check) | https://data.mendeley.com/datasets/k62n4z9gdz |
| D13 | V2AIX (RWTH ika, 2024): real ETSI ITS CAM / DENM messages in public traffic | WP5: real V2X messages (normal behaviour), inject misbehaviour | real | JSON 20 GB full (to confirm; ROS bags 1.26 TB: do not download) | non-commercial; v2aix.ika.rwth-aachen.de | arXiv 2403.10221 |
| D14 | Tampa CV Pilot BSM sample (US DOT ITS DataHub) | WP5: real BSMs (alternative / complement to D13) | real | sample (to confirm) | CC BY-SA 4.0 | catalog.data.gov "Tampa CV Pilot Basic Safety Message" |
| D15 | OpenStreetMap extract around Karlsruhe (KITTI area) | WP1 map matching, WP5 road plausibility | real map | < 100 MB | ODbL | Geofabrik / Overpass API |

Real V2X with labelled real attacks: none found (search 20 Oct 2026). Standard practice (e.g.
VCADS) = real field messages + physically consistent injected misbehaviour; VeReMi for
comparability. Newer candidates to check: VeReMi NextGen (Ulm, 2026, 15 attack types,
train / val / test splits), MisbehaviorX (IEEE DataPort, Veins, 68 attacks), V2X-PAD (NS-3).

## 3. Batch B (optional, decide per item)

| Id | Dataset | For | Size | Access / licence |
|---|---|---|---|---|
| D20 | KITTI raw camera images (image_02) + calibration for the 23 drives | WP3 camera cross-check of LiDAR objects | ~18 GB download again (zips), keep image_02 only (to confirm) | CC BY-NC-SA 3.0 |
| D21 | nuScenes v1.0-mini (6 cameras, 1 LiDAR, 5 radars) | WP3 radar / camera cross-check | a few GB (to confirm) | non-commercial, account |
| D22 | comma2k19, one ~10 GB chunk (CAN + raw GNSS + IMU + camera, same car) | WP1 / WP2 / WP6: real CAN wheel speed + GNSS on one car (motion witnesses) | ~10 GB per chunk, 100 GB total | MIT; github.com/commaai/comma2k19 |
| D23 | CSE-CIC-IDS2018 processed CSVs | WP4 cross-dataset test | several GB (check with `aws s3 ls --no-sign-request --summarize s3://cse-cic-ids2018/`) | AWS open data, no account |
| D24 | TOW-IDS automotive Ethernet (AVTP, gPTP, UDP-from-CAN; 5 attack scenarios) | WP4 in-vehicle Ethernet (closer to an AV than CICIDS) | to confirm | IEEE DataPort (may need login), DOI 10.21227/bz0w-zc12 |
| D25 | VeReMi NextGen | WP5 | to confirm | Ulm University (OPARU) |
| D26 | UrbanNav (Hong Kong urban canyons: GNSS RINEX, IMU, LiDAR) | WP1 realistic urban GNSS errors | 17-43 GB per sequence | academic; low priority |

## 4. Rough disk plan

Batch A: ~8 GB without D13; ~28 GB with the full V2AIX JSON (prefer a subset of drives).
Batch B items one at a time. Keep at least 10 GB free at all times.
