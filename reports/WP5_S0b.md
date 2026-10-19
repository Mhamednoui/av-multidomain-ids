# WP5 S0b: more Tampa BSM data (several days, >= 300 vehicles)

Date: 2026-10-20    Worker: sonnet (medium)

## Goal of the step
Find substantially more real Tampa BSM data than the public one-night sample (38 physical vehicles): >= 7 days, >= 300 vehicles, <= 3 GB, public and without login.

## Acceptance rule (notes/WP5_v2x.md, 'S0b', written before interpreting the probes)
MET only with a public no-login source of >= 7 days / >= 300 physical vehicles, licence OK, <= 3 GB. If every source needs login, registration or a sandbox request: NOT MET, say exactly what the user must do, no workaround.

## What was done
Probes only (no download, nothing written to ../data_extra): Socrata API (row count, time range, catalog search), ITS DataHub S3 bucket (both name spellings, several list URLs), catalog.data.gov, dataset metadata.

## Results
| Source | Finding |
|---|---|
| data.transportation.gov nm7w-nvbm | 34,464 rows in total = the file we already have; 2021-03-19 00:17-06:59 UTC only; not paged/extendable |
| other Tampa datasets on data.transportation.gov | SPaT sample, TIM sample, 5 aggregated BSM maps: no extra per-message BSMs |
| S3 usdot-its-cvpilot-publicdata / usdot-its-cvpilot-public-data | exists, listing AccessDenied (403) for anonymous users; not worked around |
| catalog.data.gov | links back to the same sample |
Acceptance: NOT MET (no public no-login source). Linking/dedupe was not re-run (no new files).

## What the user must do
1. Open https://its.dot.gov/data/data-request (ITS DataHub Sandbox request) and request the full Tampa CV Pilot BSM raw data (Tampa Hillsborough Expressway Authority, THEA). Say it is for academic research (intrusion detection / misbehaviour detection on BSMs); ask for several weekdays of daytime data, ideally >= 7 days, as flat JSON/CSV, and for the licence / terms. Contact listed in the dataset: data.itsjpo@dot.gov.
2. Alternative: ask the same contact whether the S3 bucket usdot-its-cvpilot-public-data allows anonymous listing or give the exact object keys / a download link, if the sandbox is slow.
3. When files arrive, place them in ../data_extra/D14_tampa_bsm/full/ and tell the orchestrator; a worker then runs the dedupe/linking (v2x/tampa_link.py), reports days / ids / physical vehicles, and reruns tools/WP5_S1b_build.py and WP5_S1b_rerun.py.

## Problems / open questions
Tampa stays an illustration (3 test vehicles) until then; VeReMi remains the benchmark with statistical power. Other real-data option already open: D13 V2AIX (also needs a request form).
