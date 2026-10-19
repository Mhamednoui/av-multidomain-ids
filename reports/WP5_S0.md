# WP5 S0: Data download (D12, D13, D14)

Date: 2026-10-19    Worker: sonnet

## Goal of the step
Download and verify VeReMi Extension, V2AIX JSON subset and Tampa BSM sample.

## Acceptance rule (notes/WP5_v2x.md, written before downloads)
D12 downloaded, licence recorded, parses, fields and labels found; D14 <= 2 GB, several days, many vehicles; D13 JSON only <= 5 GB whole recordings; >= 15 GB free; login/manual steps not worked around.

## What was done
- data: ../data_extra/D12_veremi_extension/, ../data_extra/D14_tampa_bsm/, (D13 empty, README)
- tools/WP5_verify_s0.py -> results/WP5/s0_data_check.json; DATASETS.md rows D12-D14; notes/WP5_v2x.md

## Results (results/WP5/s0_data_check.json)
| Dataset | Size | Messages | Senders | Labels |
|---|---|---|---|---|
| D12 | 1.21 GB csv | 3,194,808 | 24,663 (118,909 pseudonyms) | class 0..19, 0 genuine 1,900,539 |
| D14 | 39 MB | 34,464 | 226 | none (real, normal) |
| D13 | 0 | - | - | - |
Acceptance: D12 MET. D14 PARTIAL (public sample covers one day, 2021-03-19). D13 NOT MET (manual-approval request form).

## Problems, surprises, open questions
- D12 combined CSV lacks receiver id/position and simulation id; class-to-attack map not documented in the dataset page.
- D13: user must submit the request form (see notes). Licence forbids redistribution.
- D14: several days would need an ITS DataHub Sandbox request.

## Proposed next step
After the user obtains V2AIX access: download the JSON subset. Otherwise S1 can start on D12 + D14 only.
