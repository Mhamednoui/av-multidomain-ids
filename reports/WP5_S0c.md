# WP5 S0c: V2AIX data (D13) download, inventory, adapter, split

Date: 2026-10-24    Worker: sonnet medium (T2)

## Goal of the step
Get the real ETSI CAM dataset V2AIX (user-provided link), inventory it, extract whole recordings (~5 GB) across scenarios, build the adapter to the unified schema with the ego GNSS pose as receiver, split by recording, verify. No detection.

## Acceptance rule (written in notes/WP5_v2x.md before the download, 2026-10-24)
A1 archive complete + inventoried; A2 extracted <= 5.5 GB over >= 2 strata, >= 15 GB free; A3 adapter passes schema.validate, units tested; A4 splits disjoint by recording, 60/20/20 +- one recording; A5 plausibility reported; A6 no detection, nothing licensed in git.

## What was done
- Downloaded v2aix_json.zip (1,007,346,151 bytes, testzip OK) to ../data_extra/D13_v2aix/. Inventory from the zip directory only (results/WP5/s0c_inventory.md): 2,228 files, 22.16 GB, 13 location strata x (joined.json + scenarios/<ts>.json).
- Selection rule on paths / sizes only (seeded round-robin over strata, 5 GB): 1,540 recordings, 4.999 GB (results/WP5/s0c_selection.json), all 13 strata. joined.json not extracted.
- Adapter v2x/v2aix.py (adapters.load_v2aix calls it); tests/v2x/test_v2aix.py (7 tests: unit conversions, unavailable codes, RSU container, time unwrapping, ego interpolation / gap / static / status, schema, split); old stub test replaced. 386 tests pass.
- Split: v2aix.split_recordings (60/20/20 per (Mobile|Stationary, location) stratum, seed 42) -> results/WP5/splits_v2aix.json.
- Tools: tools/WP5_S0c_{inventory,extract,verify}.py. All reads with python -I, nothing executed from the data.

## Results (results/WP5/s0c_verify.json, s0c_tables.md)
| split | recordings | messages | senders | Mobile msgs | Stationary msgs |
|---|---|---|---|---|---|
| train | 907 | 123,593 | 1,181 | 18,549 | 105,044 |
| val | 304 | 41,285 | 380 | 7,440 | 33,845 |
| test | 304 | 47,425 | 395 | 4,338 | 43,087 |

- 212,303 CAMs, 1,515 recordings with CAMs (25 empty), 1,956 (recording, station) senders. CAM only (no DENM), station type 5 only. Field completeness 100% for position, speed, acl, yaw rate, pos_sigma; heading 99.7%; spd_sigma 48%; acl_sigma 0%; rx pose 95.5%.
- Ego GNSS present (cohda_mk5; oxts_rt3000 for Sensor-Context). Ego's own CAMs absent.
- Sender-ego distance: Mobile p50 172 m / p99 5.0 km / max 6.6 km; Stationary p50 590 m / p99 4.2 km / max 8.05 km; urban stationary sites max 327 m.
- Speed 0..163.82 m/s (3 glitch values above 70); implied vs reported speed |diff| p99 12.9 m/s; CAM interval median 0.35 s.
- Acceptance: A1-A4, A6 MET; A5 reported (see notes/WP5_v2x.md).

## Problems, surprises, open questions
- Stationary dominates (88% of messages): any detection evaluation must report Mobile and Stationary separately. Mobile V2X-only clips are 2-3 s long, 42% of Highway ones without ego pose within 2 s (rx NaN, not extrapolated).
- Sender clock offsets are not recoverable: delayed-message injection and checks use relative age only.
- Radio range is km-scale: the VeReMi acceptance-range threshold does not transfer.
- Question: for S3b, evaluate Mobile (ego moving) and Stationary (RSU receiver) separately, with thresholds from val of each? (proposed yes).

## Proposed next step
S3b: receiver-based checks (acceptance range, sudden appearance) and the frozen stack on real CAM traffic; FA on genuine val/test messages by environment.
