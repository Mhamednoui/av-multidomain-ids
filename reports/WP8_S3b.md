# WP8 S3b: LiDAR speed with compiled kernels (numba)

## Summary
Rule L1 is MET. With the numba kernels the frozen_lidar31 domain scans in **median 73-76 ms, p99 110-135 ms per scan** (numpy path of S3: median 141-178 ms, p99 240-294 ms; v3: 1.2-1.8 s). Outputs are **identical** to the numpy path on all 2,085 V31_val scans (and on the 1,113 scans used in S3): 0 alarm differences, max |diff| = 0.0 on the four layer raw scores, the combined statistic and score. JIT warm-up is separate: 0.4-0.6 s per process with the on-disk cache, about 12 s for the very first compile. numba==0.60.0 (llvmlite==0.43.0) added to requirements.txt.

## What was done
- `lidar/fast_nb.py` (new): four kernels, each an operation-for-operation mirror of the numpy function (same float64 / float32 arithmetic, same first-minimum tie-break, same label order as scipy): ring assignment (windowed laser search with margin, per-bin median common mode), voxel clustering (voxel centroids, grid neighbour search at radius e0, union-find), range images (count, nearest, nearest non-ground), ground cell minima. cache=True.
- `lidar/fast.py`: flag `USE_NUMBA` (`fast.set_numba(True)` or env `AV_LIDAR_NUMBA=1`; default off), each function dispatches to the kernel, the numpy code stays as fallback (also when numba is missing). Frozen domain files unchanged.
- Rule: no kernel had to be dropped; all four are exact (kernel-level check on 89 scans plus the stream check below).

## Equality (validation drives only, no H31)
Comparator: the numpy path of the same frozen_lidar31 (the S3 score file uses leave-one-drive-out references, so it is not the right comparator; a first run against it showed 8 alarm differences that are that protocol difference, not the kernels).
results/WP8/S3b/equality_run1_vs_np1.json: all 2,085 scans and first 1,113 scans: alarm_differences 0, max_abs_diff 0.0 (L1, L2a, L2c, L2d, stat, score). Rule met (0 alarms, <= 1e-9).
Per-scan scores: results/WP8/scores/S3b/lidar_val_{run1,run2,np1}.npz (rule 6).

## Timing (stream push, one core, file read excluded, warm-up excluded)
| run | path | median ms | p99 ms | max ms | other python processes (tasklist, own process excluded) |
|---|---|---|---|---|---|
| run1 | numba | 75.8 | 109.6 | 128 | 1 |
| run2 (repeat) | numba | 73.2 | 134.5 | 141 | 0-2 (first drives 1-2, later 0) |
| np1 (reference) | numpy | 168.4 | 294.0 | 343 | 1 plus the test suite I ran at the same time |
Median <= 0.10 s and p99 <= 0.25 s hold in both numba runs. The machine was not idle (S6 worker, S1 download), so the p99 varies between runs (110 vs 135 ms); the medians agree within 3 ms. The np1 row is a loaded reference, S3 reported 141-178 ms for the numpy path. Stage costs of the numba path (ms, drive 0011): voxel clustering about 14, ring assignment about 15, range images about 6 each (2 per scan in a stream), rest in numpy (tiles, L1 statistics, L2c/L2d statistics, scoring).
JSON: results/WP8/S3b/speed_{run1,run2,np1}.json.

## Tests
tests/v31/test_fast_nb.py (3 tests: real-scan equality of the four kernels, synthetic clusters, flag default off). Full suite: 517 passed, 0 failed, 2 skipped (results/WP8/logs/S3b_tests.log).

## Files
lidar/fast_nb.py, lidar/fast.py (flag), tests/v31/test_fast_nb.py, tools/WP8_S3b_{speed,compare,kern,prof,prof2}.py, requirements.txt, results/WP8/S3b/, results/WP8/scores/S3b/, logs results/WP8/logs/S3b_*.log.

## Open points
- The flag is off by default; S2 / S7 runners should call `lidar.fast.set_numba(True)` (same results, 2x faster). A process started fresh pays 0.4-0.6 s once (cache in lidar/__pycache__/*.nbi; first ever compile about 12 s).
- Remaining time is spread over numpy code; further gains would need compiling tiles / pair statistics, not needed for L1.
