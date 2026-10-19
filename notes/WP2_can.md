# Notes WP2 CAN

## 2026-10-19 S0 start: acceptance rule (written before results)
S0 is MET if: (1) licence read from the source page and allows research use; (2) all files of
the DTU article 24805533 are in ../data_extra/D11_can-train-and-test/ with sizes equal to the
published sizes and MD5 equal to the published checksums (if published); (3) archives
extracted with >= 15 GB free left on disk; (4) at least one CSV per vehicle/attack family
parses with python -I (columns, row count, label values listed); (5) DATASETS.md D11 row and
a layout section updated. If disk would breach 15 GB: stop after download+verify and ask.

## 2026-10-19 S0 results
- Licence: CC BY 4.0 (DTU page / figshare API) -> research use allowed.
- Source: figshare article 24805533, one file can-train-and-test.zip, 1,507,455,719 B, published
  MD5 bd6509d670c0a0009cb3ecab34111bcd; local md5sum identical; zipfile.testzip() = None.
  Version on the site is v1 (2023-12-15). The "7.5 GB" in DATASETS.md is the extracted size
  (7,471,445,612 B in the zip listing; 7,471,443,340 B of CSV on disk). Download took ~45 min
  (curl -C -, ~0.5 MB/s). Disk after extraction: 44 GB free (>= 15 GB kept). Zip kept in raw/.
- Extracted with Python zipfile under -I; nothing executed. 236 CSV + README, 193,240,845 frames.
- All 236 files: header timestamp,arbitration_id,data_field,attack; labels only {0,1}; no NaN
  timestamps; data_field hex length 2..17 chars (DLC 1..8, a 17-char = odd length value exists:
  to look at in S1); all start at 1672531200.0 (synthetic epoch).
- Many files have tiny timestamp inversions (<= 0.15 ms, e.g. rpm-3: 100 inversions, 56 on attack
  rows): float precision of epoch seconds; S1 must sort stably or use relative time.
- 174 distinct files of 236 (62 duplicate groups across sets, e.g. set_01 test_02 DoS-3 ==
  set_03 train_01 DoS-3): a vehicle/capture must be assigned to ONE side in S1 splits.
- Accessory captures (accessory-*) have no attack frames (like ROAD accessory); also
  set_04/test_04/force-neutral-2.csv has none. Test sets contain no attack-free file: normal
  frames are inside the attack captures (before/after the attack).
- Files: tools/WP2_s0_verify.py, WP2_s0_summary.py, WP2_s0_extra.py; results/WP2/s0_inventory.json,
  s0_summary.txt, s0_duplicates.json, s0_extra.txt.
- Acceptance rule (1)-(5): all MET (parsed ALL files, not just one per family).
