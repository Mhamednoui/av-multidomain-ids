# WP1 S0: download D15 OSM extract

Date: 2026-10-19    Worker: sonnet (WP1)

## Goal of the step
Download an OSM extract covering the KITTI drives' bounding box (+~1 km) for S6 map matching.

## Acceptance rule (notes/WP1_gps.md, written before results)
All OXTS fixes of all 23 drives inside bbox+margin; file loads with python -I with ways and
nodes; >= 95% of each drive's fixes within 50 m of a road way; size < 100 MB; >= 15 GB free;
licence recorded.

## What was done
- tools/WP1_osm_bbox.py, tools/WP1_osm_verify.py; results/WP1/osm_bbox.json, osm_verify.json
- Data: ../data_extra/D15_osm/karlsruhe_highways.json (+ SOURCE.txt), Overpass API, 2026-10-19.
- DATASETS.md D15 row updated.

## Results (results/WP1/osm_verify.json)
| item | value |
|---|---|
| size | 36,924,973 bytes |
| ways / nodes | 57,018 / 193,170 |
| drives inside bbox+1 km | 23 / 23 |
| min over drives of fraction of fixes within 50 m of a road | 1.0 |
| free disk | 52 GB |
Acceptance: MET

## Ablation row(s)
n/a (data step)

## Problems, surprises, open questions
Extract includes all highway classes (footway, path, steps...); S6 must filter to drivable
roads. Way-edge nodes lie slightly outside the bbox (node bbox lat to 49.115).

## Proposed next step
S1 data layer.
