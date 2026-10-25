"""LidarRunner: streaming wrapper of the FROZEN LiDAR domain (lidar/domain.py LidarDomain, results/WP3/S9/frozen_lidar), one scan at a time (WP7 S2).

Purpose: feed velodyne scans (N x 4 float32: x forward, y left, z up, intensity 0-1) with the ego pose of each scan and get the combined domain Evidence
("lidar.combined") plus the four per-layer Evidence (L1 geometry, L2a intensity, L2c background, L2d tracking) of that scan. The frozen stream keeps only the previous scan
(L2c / L2d compare a scan with the one before it), so the runner is stateless apart from that and reset(key) clears it. The first scan of a stream has no previous scan: L2c / L2d
are unavailable and contribute rank 0 (flagged in details["first_scan_no_previous"]).
Sample: mapping with "points", "pose" (x, y, yaw planar pose of the scan in any local world frame; KITTI: lidar.ego.poses from OXTS), "t" (scan time, s), optional "sample_id".
Cost: about 1.84 s per scan on this machine (results/WP3/S9/timing.json, measured again in WP7 S2): the system does NOT keep up with a 10 Hz sensor on one core; period_s = 0.1.
Exactness: this IS the frozen code path (LidarStream.push), nothing is re-implemented; WP6 S5b replayed raw test scans through it and found the stored layer scores equal (tools/WP6_S5b_lidar.py check).
Reference: reports/M1_LiDAR.md, notes/WP3_brief.md "Frozen LiDAR domain output".
"""
from typing import List

from common.evidence import Evidence
from lidar.domain import LAYERS, LidarDomain
from system.runner import Runner


class LidarRunner(Runner):
    domain = "lidar"
    name = "lidar.runner"
    status = "frozen"
    period_s = 0.1                      # 10 Hz velodyne scans

    def __init__(self, folder_or_domain, bus=None, per_layer=True):
        super().__init__(bus)
        self.dom = folder_or_domain if isinstance(folder_or_domain, LidarDomain) else LidarDomain.load(folder_or_domain)
        self.per_layer = per_layer
        self.stream = self.dom.stream()

    def _reset(self, key):
        self.stream.reset()

    def _size(self):
        return self.stream.n

    def _push(self, sample) -> List[Evidence]:
        comb, per = self.stream.push(sample["points"], sample["pose"], float(sample.get("t", 0.0)), sample.get("sample_id"))
        out = [comb]
        if self.per_layer:
            out.extend(per[x] for x in LAYERS)
        return out
