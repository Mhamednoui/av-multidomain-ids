"""GPSRunner: streaming wrapper of the FROZEN GPS domain (gps/domain.py GPSDomain, results/WP1/frozen_gps), one fix at a time (WP7 S1).

Purpose: feed GPS fixes (1 Hz, with IMU / odometry / compass fields and the LiDAR-odometry columns lid_*) one by one and get the combined domain Evidence
("gps.combined") and the per-layer Evidence of that fix. State: the fixes of the current run (drive); reset(run) clears it.
How: the frozen layers (B2 dead reckoning, L1 rules, EKF NIS, CUSUMs, L2d LiDAR-odometry residuals) are causal per-run programs without a step() entry point
(WP1 did not provide one and this WP may not edit gps/). The runner therefore re-scores the PREFIX of the run with the frozen code and returns the last row; because the layers
are causal that equals the whole-run result for that fix (tests/system, tools/WP7_S1_*.py). Cost: one prefix re-score per fix (grows with the run length; an upper bound
of an incremental version). Stateless between runs: no information crosses reset().
Sample: a mapping (dict / pandas row) with the gps/stream.py columns and the L2D columns lid_z_1, lid_z_3, lid_z_10, lid_resid_1, lid_resid_3, lid_course
(the LiDAR odometry is an upstream sensor product, not recomputed here). Output: list[Evidence]: [combined] + per-layer Evidence of the fix.
Reference: notes/WP1_brief.md "Frozen GPS domain output"; reports/M1_GPS.md section 8.
"""
from typing import List

import pandas as pd

from common.evidence import Evidence
from gps import domain as GD
from gps import stream as S
from system.runner import Runner

INPUT_COLUMNS = list(S.COLUMNS) + GD.L2D_COLUMNS


class GPSRunner(Runner):
    domain = "gps"
    name = "gps.runner"
    status = "frozen"
    period_s = 1.0

    def __init__(self, folder, bus=None, per_layer=True):
        super().__init__(bus)
        self.dom = GD.GPSDomain.load(folder)
        self.per_layer = per_layer
        self.rows: List[dict] = []

    def _reset(self, key):
        self.rows = []

    def _size(self):
        return len(self.rows)

    def _push(self, sample) -> List[Evidence]:
        row = dict(sample)
        if "run" not in row:
            row["run"] = self.key or "run"
        if "k" not in row:
            row["k"] = len(self.rows)
        self.rows.append(row)
        df = pd.DataFrame(self.rows)
        df = GD.prepare(df, lidar=self.dom.lidar)
        ev, per = self.dom.score(df, with_layers=True)
        out = [ev[-1]]
        if self.per_layer:
            out.extend(per[n][-1] for n in self.dom.names)
        return out
