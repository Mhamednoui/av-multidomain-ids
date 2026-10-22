"""WP3 S2 L1 sensor-geometry layers (domain "lidar", layer "L1", kind "physics"): v3 Layers over the five scan statistics
of lidar.geometry.l1_stats.

Rules (each a Layer; thresholds: physics where one exists, otherwise tie-safe 1 % of clean validation scans):
  ring_total     n_off_ring: returns at 8-80 m farther than 3 x 2 cm (spec range accuracy x 3) from the laser ring line
  ring_sector    sector_off_ring: the same count in the worst 10 deg sector (a localized injection)
  range          returns beyond the spec range (120 m) or nearer than the train minimum (any violation alarms)
  intensity      intensity outside [0, 1] (any violation alarms)
  single_return  two returns of one unambiguous laser within 0.02 deg at different ranges: impossible for a single-return
                 sensor (count above the clean-validation 1 % quantile)
  union          max over the rules of the validation-ECDF of their statistic; budget 1 % on clean validation scans.
Samples: a DataFrame with the columns of lidar.geometry.STAT_NAMES (one row per scan).
Physics limit stated plainly: a phantom placed on its laser ring that REPLACES the real return is a legal single-return scan
(CARLO, Sun et al. 2020, reach the same conclusion), so L1 cannot see it; L1 catches off-ring injections (box cloud) and
phantoms added next to a surviving real return (duplicate direction).
"""
import numpy as np

from common.layer import Layer
from lidar.geometry import STAT_NAMES


class L1Rule(Layer):
    domain, layer_id, kind = "lidar", "L1", "physics"

    def __init__(self, name, stat):
        super().__init__()
        self.name, self.stat = name, stat

    def raw_scores(self, samples):
        return np.asarray(samples[self.stat], dtype=float)

    def reasons(self, samples, raw, alarm):
        return [f"{self.name}: {self.stat} = {r:.0f} above the clean-scan limit" for r in raw]


class L1Union(Layer):
    domain, layer_id, kind, name = "lidar", "L1", "physics", "union"

    def __init__(self, stats=STAT_NAMES):
        super().__init__()
        self.stats = list(stats)
        self.ref = None

    def calibrate(self, val_normal, budget=0.01):
        self.ref = {s: np.sort(np.asarray(val_normal[s], dtype=float)) for s in self.stats}
        return super().calibrate(val_normal, budget)

    def parts(self, samples):
        return np.column_stack([np.searchsorted(self.ref[s], np.asarray(samples[s], dtype=float), side="left") / len(self.ref[s])
                                for s in self.stats])

    def raw_scores(self, samples):
        return self.parts(samples).max(axis=1)

    def reasons(self, samples, raw, alarm):
        P = self.parts(samples)
        return [f"sensor geometry: {self.stats[int(np.argmax(P[i]))]} outside the clean-scan range" for i in range(len(raw))]


def rules():
    return [L1Rule("ring_total", "n_off_ring"), L1Rule("ring_sector", "sector_off_ring"), L1Rule("range", "n_range"),
            L1Rule("intensity", "n_intensity"), L1Rule("single_return", "n_dup")]
