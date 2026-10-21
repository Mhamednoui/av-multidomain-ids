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
