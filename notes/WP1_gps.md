# WP1 GPS notes

## 2026-10-19 S0 (download D15 OSM)
Acceptance rule (written before any result):
- Extract covers the lat/lon bbox of all 23 KITTI 2011_09_26 drives (OXTS) + ~1 km margin:
  100% of OXTS fixes of every drive fall inside the extract bbox (and inside bbox minus 500 m).
- File loads with python -I; contains > 0 highway ways and their nodes; every drive has road
  ways within 50 m of >= 95% of its fixes (sanity: map is the right place).
- Size < 100 MB; >= 15 GB disk free after download; licence ODbL recorded with attribution.
Done (tools/WP1_osm_bbox.py -> results/WP1/osm_bbox.json; tools/WP1_osm_verify.py -> results/WP1/osm_verify.json):
- 23 KITTI drives, OXTS bbox lat 48.94231..49.06758, lon 8.33725..8.47829; +1 km margin
  lat 48.93333..49.07656, lon 8.32356..8.49199.
- Overpass query (all highway=* ways + nodes) -> ../data_extra/D15_osm/karlsruhe_highways.json,
  36,924,973 bytes (35.2 MB), 57,018 ways, 193,170 nodes, OSM timestamp 2026-10-19T21:54:50Z.
  Contains footways/paths/service etc. (map matching in S6 should filter to drivable classes).
- All 23 drives: 100% of fixes inside bbox+margin; 100% of fixes (min over drives) within 50 m of a road.
- Disk free after: 52 GB. Licence ODbL 1.0, attribution (c) OpenStreetMap contributors.
- Untrusted data read with python -I, JSON only; nothing executed.
Acceptance: MET (all criteria above).
