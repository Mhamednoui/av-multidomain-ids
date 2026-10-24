"""WP3 S9: example Evidence and MotionEstimate fixtures for WP6 / WP7 (results/WP3/S9/example_evidence_lidar.json, example_lidar_motion_estimates.json).
Uses the first scans of test drive 0095 through the frozen domain. Usage: python -u -W ignore tools/WP3_S9_fixtures.py"""
import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS
from lidar import ego
from lidar.data import FRAME_DT, load, scan_files
from lidar.domain import LidarDomain

R = RESULTS / "WP3" / "S9"
d = LidarDomain.load(R / "frozen_lidar")
f, pose = scan_files("0095"), ego.poses("0095")
s = d.stream()
out = []
for i in range(3):
    c, per = s.push(load(f[i]), pose[i], t=i * FRAME_DT, sample_id=f"0095/{i}")
    out.append({"combined": c.to_dict(), "layers": {k: v.to_dict() for k, v in per.items()}})
(R / "example_evidence_lidar.json").write_text(json.dumps(out, indent=1, default=float))
n = 31
P, q = d.odometry(f[:n])
t = np.arange(n) * FRAME_DT
est = d.motion_estimates([1.5, 2.5, 3.0], P, t, q)
(R / "example_lidar_motion_estimates.json").write_text(json.dumps([asdict(e) for e in est], indent=1, default=float))
print(len(est), est[0])
