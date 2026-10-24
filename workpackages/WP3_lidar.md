# WP3 LiDAR

Goal: detect LiDAR spoofing (phantom objects, point removal, intensity spoofing) with
object-level physical checks instead of only a whole-scan descriptor.

Owns: `lidar/`, `tests/lidar/`, `results/WP3/`, `notes/WP3_lidar.md`, `reports/WP3_*`, `tools/WP3_*`.
Data: D04 KITTI (velodyne + oxts); optional D20 KITTI images, D21 nuScenes mini (S8).

## Baseline (v2, `../codes_v2/results/lidar*.json`)
Test (7 unseen drives): 90.19% acc, AUC 0.970. At ~1% FA: PointDrop 83.9%, IntensitySpoof
99.9%, box-cloud phantom 51.4% (inflated by an artefact: up to 1,500 points where a real car at
30 m returns ~270). Physically consistent ray-cast phantoms: added 39.1% appearing / 30.2%
persistent; 50-400-point budget added 8.8% / 4.5%; replacing ~1% (= FA, physics bound).
Sequence detector: 9/14 persistent box-cloud phantom episodes alarmed within 3 s. Simulation
phantom block 8.3% (near sparse phantoms missed).
Target (fixed): ray-cast phantoms (50-400 added points) >= 60% at 1% FA on unseen drives; near
(5-15 m) sparse phantoms > 50%; the full replacing phantom stays the documented physics bound
unless S8 adds a camera / radar check.

## Steps
- S0 (optional, later) Data: D20 or D21 for S8, after approval.
- S1 Data layer + attack generator: copy from v2 `lidar/features.py` (`raycast_ghost`,
  `apply_attack`, descriptor incl. patch features) and the drive split; evaluation phantoms are
  ray-cast only (add / replace / budget); the box cloud is kept only to compare with v2.
  Scan sequences per drive (copy `lidar/sequence.py` logic), groups = "<drive>/<file>".
- S2 L1 sensor geometry: points on the 64 laser rings (elevation within tolerance of a ring),
  range / intensity limits, returns per direction.
- S3 Object segmentation: ground removal + clustering; object table per scan (centroid,
  range, extent, point count, angular extent).
- S4 L2a density vs range per object: expected points from the HDL-64E angular resolution
  (~0.08-0.4 deg horizontal x ~0.4 deg vertical) for the object's size and range; too sparse
  near or too dense far = suspicious.
- S5 L2b free space / occlusion per object (CARLO, Sun et al. USENIX Security 2020): rays
  through the object's silhouette that return from behind it = not a solid object.
- S6 L2c background model (expected returns per ring / azimuth, ego-motion compensated with
  OXTS) for removal attacks; L2d object tracking with ego-motion compensation (a phantom fixed
  to the sensor follows the car's own acceleration exactly).
- S7 L3 normal-only object statistics; L4 retrain the v2 descriptor model in the harness.
- S8 (optional) camera or radar cross-check of LiDAR objects.
- S9 Combiner + ablation + sequence-level evaluation -> milestone M1-LiDAR report.

## Pitfalls from v2
- Never evaluate on the box-cloud phantom alone (density artefact).
- Two trainings with realistic small phantoms as a class failed (label noise): a class that is
  physically indistinguishable from normal must not be a training class.
- Scan file names repeat across drives: always "<drive>/<file>".
- Validation drives are harder than test drives; KITTI frames ~0.1032 s apart.

## Progress
- 2026-10-22 S1 done, REVIEW: v2 descriptor and all v2 baseline numbers reproduced exactly on the v3 layer (A1-A7 MET). See reports/WP3_S1.md, notes/WP3_brief.md.
- 2026-10-24 S4 done, REVIEW: L2a density/intensity (tiles), see reports/WP3_S4.md
