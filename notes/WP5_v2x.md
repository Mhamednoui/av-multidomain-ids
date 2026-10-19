# WP5 V2X notes

## 2026-10-19 S0 Data download: acceptance rule (written before any download/result)
S0 is MET if all hold:
1. D12 VeReMi Extension downloaded to ../data_extra/D12_veremi_extension/, licence recorded, files parse, fields present
   (sender id, time, position, speed, heading) and ground-truth label values (attack types) found; message and sender counts recorded.
2. D14 Tampa BSM sample (<= ~2 GB) downloaded, several days and many distinct vehicles, parsed; fields present.
3. D13 V2AIX JSON only (no ROS bags), <= 5 GB, whole recordings, mixed scenarios if metadata allows; licence recorded.
4. >= 15 GB disk free throughout. Anything needing login/manual click is NOT worked around: recorded with the exact user action; item then reported PARTIAL.

## 2026-10-19 S0 results (numbers from results/WP5/s0_data_check.json, script tools/WP5_verify_s0.py)
- D12: Mendeley k62n4z9gdz, CC BY 4.0, sha256 matches. CSV 3,194,808 rows, 24,663 `sender`, 118,909 `senderPseudo`. Fields: sendTime, sender, senderPseudo, messageID, class, pos/spd/acl/hed (x,y,z) plus *_n noise-sigma columns. No receiver id, no simulation id, no receiver position in this combined CSV (limits S3 acceptance-range check and group-by-simulation splits; split by sender id; raw VeReMi logs would be needed otherwise -> maybe D25 NextGen). class values 0..19, 0 genuine = 1,900,539 (59.5%); the class-to-attack-name map is NOT in the dataset page (assumed to follow F2MD/VeReMi Ext attack order: check against paper before S1). posz/spdz/aclz/hedz all 0.
- D14: 34,464 BSMs, 226 vehicle ids, only ONE day (2021-03-19, ~6.7 h). Acceptance wanted several days: NOT met by the public sample; fuller data = ITS DataHub Sandbox request (user). Enough for normal-behaviour modelling with 72 vehicles >= 100 msgs. Raw units: lat/long 1e-7 deg, speed 0.02 m/s, heading 0.0125 deg (J2735).
- D13: V2AIX is a Streamlit site; Download button opens a request form (manual approval, "all requests are approved manually"). Not worked around, nothing submitted. User must: open https://v2aix.ika.rwth-aachen.de, click Download, fill form, tick 2 boxes, wait for approval mail with the link; then give link to a worker (JSON format only; pick Mobile Aachen/Cologne, highway, rural + Stationary, whole files, <=5 GB). Licence: non-commercial, cite, no redistribution of data or modified versions.
- Disk free after: ~48 GB.
- Acceptance: D12 MET; D14 PARTIAL (one day, 226 vehicles); D13 NOT DONE (needs user). Overall S0 PARTIAL.
