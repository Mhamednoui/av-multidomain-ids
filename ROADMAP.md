# Roadmap v3

Written 20 Oct 2026 by the session that built v2 (seed: `../codes_v2/ROADMAP_v3.md`).

## 1. Why v3 (what v2 proved)

| Evidence from v2 (numbers in `../codes_v2/RESULTS_v2.md`) | Lesson |
|---|---|
| GPS model trained on a slow robot (AV-GPS): 63% false alarms on a car (KITTI) | learned models encode the platform, not the attack |
| Car-Hacking CAN model used on another car (ROAD): 0.5% recall | same |
| ROAD payload model raised alarms on real reverse driving (ID 0x0D0) | it learned the attack's values, not the attack |
| GPS dead-reckoning check (no training): 1.6% false alarms on a new car, every jump caught | physics transfers |
| Drone: PX4's own EKF gate never fired under live spoofing; a GPS-vs-IMU check fired at the first spoofed fix | consistency checks work, with the right test |
| LiDAR phantom proxy (points filling a box) denser than any real object; part of its "51%" detection was that artefact | evaluation attacks must be physically consistent |
| Zero-day layer only sees detector outputs: unseen Bot 5% | anomaly detection must look at the raw domain data |
| Fusion thresholds chosen for F1 let false alarms drift to 5.5%; random validation halves hid a meta-classifier memorising drives (11.8% false alarms on test) | fixed false-alarm budget, group-aware validation |

## 2. Target design (details in ARCHITECTURE.md)

Each domain (network, CAN, GPS, LiDAR, V2X) = four kinds of independent layers + a combiner:
L1 specification rules, L2 physics / consistency checks, L3 normal-behaviour models (clean data
of the target vehicle only), L4 supervised models (attack data). Above the domains: a
cross-domain layer (the vehicle's motion is measured by CAN, GPS/IMU, LiDAR and announced over
V2X: the witness that disagrees is the attacked one), then fusion, temporal correlation and
response. Every alert says which layer fired and why.

## 3. Work packages and order

```
WP0 Foundation (alone, first)
   │  contracts, common code, harness, docs, git
   ▼
WP1 GPS   WP2 CAN   WP3 LiDAR   WP4 Network   WP5 V2X      (parallel, at most 3 at a time)
   │         │          │           │            │
   └─────────┴──────────┴─────┬─────┴────────────┘
                              ▼
WP6 Cross-domain + fusion + zero-day + correlator/response
                              ▼
WP7 System: streaming runtime, simulation v3, full re-run, RESULTS_v3, publication
```

Suggested waves (machine: one GPU, 12 cores): wave 1 = WP1 GPS, WP2 CAN, WP5 V2X (data small or
in hand, CPU-light); wave 2 = WP3 LiDAR, WP4 Network (GPU / big data). WP6 may start its
motion-witness steps once WP1 S5 (LiDAR odometry) is approved.

| WP | File | Owns | Depends on |
|---|---|---|---|
| WP0 Foundation | workpackages/WP0_foundation.md | common/, tests/common/, tools/WP0_*, docs | - |
| WP1 GPS | workpackages/WP1_gps.md | gps/ | WP0 |
| WP2 CAN | workpackages/WP2_can.md | can/ | WP0 |
| WP3 LiDAR | workpackages/WP3_lidar.md | lidar/ | WP0 |
| WP4 Network | workpackages/WP4_network.md | network/ | WP0 |
| WP5 V2X | workpackages/WP5_v2x.md | v2x/ | WP0 |
| WP6 Cross-domain | workpackages/WP6_crossdomain.md | crossdomain/, fusion/ | WP1-WP5 milestones |
| WP7 System | workpackages/WP7_system.md | system/ | WP6 |

## 4. Milestones

| Id | Meaning | Check |
|---|---|---|
| M0 | foundation approved | contracts frozen; harness reproduces a v2 number exactly |
| M1-GPS / M1-CAN / M1-LiDAR / M1-NET / M1-V2X | domain combiner done | ablation table + external test; beats the v2 baseline on that domain's target (WP file) or explains why not |
| M2 | cross-domain + fusion | "which domain lies" accuracy; system false alarms within budget on test |
| M3 | system | streaming simulation of all 5 domains; RESULTS_v3.md generated; all tests pass |
| M4 | publication | only with the user's approval |

## 5. Baselines to beat (v2, test data)

| Domain | v2 result | v3 target (decided now, before any v3 result) |
|---|---|---|
| GPS | slow drift 0.2-0.5 m/s: 0-11% of rows; dead-reckoning rule 1.58% FA; UAV: GPS-vs-IMU alarm at the first spoofed fix | slow drift 0.2-0.5 m/s detected within 30 s in >= 60% of runs at <= 1% FA on unseen KITTI drives; UAV not worse |
| CAN | ROAD: 0 false alerts at window level, masquerade 0-27%, reverse driving false alarms (payload model), coolant missed; cross-car transfer 0.5% | ROAD masquerade captures detected with <= 1 false alert per hour; no reverse-driving false alarm; can-train-and-test unknown-vehicle results reported |
| LiDAR | ray-cast add phantom 39% appearing / 30% persistent at ~1% FA; realistic budget phantoms 1-9%; near sparse phantoms mostly missed | ray-cast phantoms (50-400 added points) >= 60% at 1% FA on unseen drives; near sparse > 50%; full replacement phantom stays the documented physics bound unless a camera / radar check is added |
| Network | 99.73% on known attacks (random split); unseen Bot 5.8% | time-split evaluation; unseen Bot > 70% at the same false-alarm level; cross-dataset 2017 -> 2018 reported |
| V2X | none (new domain) | VeReMi Extension results comparable with the literature; injected misbehaviour on real messages reported per attack type |
| System | simulation 91.67% acc, 1.90% FA, phantom block 8.3% | system FA <= 2% with every attack block detected (persistent phantom included) |

## 6. Datasets

See DATASETS.md. Downloads happen inside each WP as step S0, each one approved by the user
with its size. Disk free on 20 Oct 2026: 51.9 GB.
