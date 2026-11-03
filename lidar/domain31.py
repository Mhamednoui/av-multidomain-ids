"""LidarDomain31: the v3.1 deployable LiDAR domain (WP8 S3). v3 lidar/domain.py is untouched.

Same four headline layers and the same inputs / Evidence contract as the v3 LidarDomain (L1 sensor geometry, L2a object intensity, L2c background
model, L2d tracking), with (1) the fast statistics of lidar.fast (one ring assignment per scan, voxel-0.1 clustering, no object table, cached
range images of the previous scan: about 0.1 s per scan instead of 1.2-1.8 s) and (2) the per-layer-budget union combiner of lidar.combine31
(a strong layer keeps its own budget share, so PointDrop is not diluted by the other layers).
Inputs: float32 N x 4 scan (x fwd, y left, z up, intensity 0-1), pose (x, y, yaw) of the scan, time. Causal: a scan depends on itself and the
previous scan (the first scan of a stream has no L2c / L2d: rank 0, flagged). Outputs: common.evidence.Evidence (one combined + one per layer).
Layer raw score = max over the layer's statistics of the ECDF rank of the statistic on the clean reference (OOF scores of the fit drives).
Save / load: one pickle with arrays only (about 6 MB). Reference: notes/WP8_v31.md (S3), reports/WP8_S3.md."""
import pickle
from pathlib import Path

import numpy as np

from common.evidence import Evidence
from lidar import geometry as G
from lidar.combine31 import LAYERS, Union
from lidar.fast import IntensityScorer, PrevScan, ScanStats

SCHEMA_VERSION = 31
A_STATS = ["int_hi", "int_lo", "cnt_int_hi", "cnt_int_lo"]
LAYER_STATS = {"L1": list(G.STAT_NAMES), "L2a": A_STATS, "L2c": ["miss_w20"], "L2d": ["app_cc", "fix_tot"]}
NAMES = {"L1": "lidar.l1_geometry", "L2a": "lidar.l2a_intensity", "L2c": "lidar.l2c_background", "L2d": "lidar.l2d_tracking"}
PHYSICS = {
    "L1": "sensor geometry broken: returns off the laser rings, impossible range / intensity or two returns in one beam",
    "L2a": "object surface inconsistent with clean objects at that range (intensity of a patch is unusual: spoofed reflectivity)",
    "L2c": "returns the previous scan predicts in a ring / azimuth window are missing: part of the scene was removed",
    "L2d": "a surface appeared in free space or follows the sensor instead of the world: injected object",
}


class Domain31:
    def __init__(self, table, prm, intensity_ref, stat_ref, union, c_stats, meta, a_stats=None):
        self.table, self.prm, self.meta = table, prm, meta
        self.iref, self.scorer = intensity_ref, IntensityScorer(intensity_ref)
        self.stat_ref = {k: np.sort(np.asarray(v, float)) for k, v in stat_ref.items()}
        self.union, self.c_stats = union, list(c_stats)
        self.a_stats = list(a_stats) if a_stats is not None else list(A_STATS)
        self.layer_stats = dict(LAYER_STATS, L2c=self.c_stats, L2a=self.a_stats)
        self.stats = ScanStats(table, prm)

    # ---- raw scores from the statistic records (shared by batch evaluation and the stream) ------------------
    def raw_from_records(self, l1, a, pair, n_valid=0):
        """dict layer -> raw score of ONE scan. l1: array of the 5 L1 statistics, a: array of the 4 L2a statistics, pair: dict or None,
        n_valid: number of scored tiles (scale-free count statistics f_cnt_*)."""
        v = dict(zip(G.STAT_NAMES, l1))
        v.update(zip(A_STATS, a))
        v["f_cnt_int_hi"], v["f_cnt_int_lo"] = a[2] / max(n_valid, 1.0), a[3] / max(n_valid, 1.0)
        if pair is not None:
            v.update(pair)
        raw = {}
        for lay in LAYERS:
            if lay in ("L2c", "L2d") and pair is None:
                raw[lay] = 0.0
                continue
            raw[lay] = float(max(np.searchsorted(self.stat_ref[s], v[s], side="left") / len(self.stat_ref[s]) for s in self.layer_stats[lay]))
        return raw

    def evidence(self, raw, t=0.0, sample_id="", first=False):
        R = {l: np.array([raw[l]]) for l in LAYERS}
        ranks = self.union.ranks(R)[0]
        stat = float(self.union.stat(R)[0])
        alarm = bool(stat >= 0.0)
        per = {}
        for j, lay in enumerate(LAYERS):
            fired = bool(ranks[j] >= self.union.tau[j]) if self.union.method == "union" else False
            per[lay] = Evidence(domain="lidar", layer=lay, name=NAMES[lay], t=float(t), score=float(ranks[j]), alarm=fired,
                                reason=(PHYSICS[lay] if fired else ""),
                                details={"raw": float(raw[lay]), "available": not (first and lay in ("L2c", "L2d"))}, sample_id=str(sample_id))
        reason = ""
        if alarm:
            dom = LAYERS[int(np.argmax(ranks - self.union.tau))] if self.union.method == "union" else LAYERS[int(np.argmax(ranks))]
            reason = f"LiDAR domain alarm (union of layers at their own budgets): {PHYSICS[dom]}"
        comb = Evidence(domain="lidar", layer="combined", name="lidar.combined", t=float(t), score=float(self.union.score(R)[0]), alarm=alarm,
                        reason=reason, details={"method": self.union.method, "stat": stat, "layer_raw": raw, "first_scan_no_previous": first,
                                                "layer_budgets": [float(b) for b in np.atleast_1d(self.union.budgets)]}, sample_id=str(sample_id))
        return comb, per

    def stream(self):
        return Stream31(self)

    # ---- persistence -------------------------------------------------------------------------------------
    def save(self, folder):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        parts = {"schema": SCHEMA_VERSION, "table": self.table.to_dict(), "prm": self.prm, "iref": {"nmin": self.iref.nmin, "i": self.iref.i},
                 "stat_ref": self.stat_ref, "union": self.union, "c_stats": self.c_stats, "a_stats": self.a_stats, "meta": self.meta}
        with open(folder / "domain31.pkl", "wb") as fh:
            pickle.dump(parts, fh, protocol=4)

    @classmethod
    def load(cls, folder):
        with open(Path(folder) / "domain31.pkl", "rb") as fh:
            p = pickle.load(fh)
        assert p["schema"] == SCHEMA_VERSION
        ir = type("IntensityCells", (), {})()
        ir.nmin, ir.i = p["iref"]["nmin"], p["iref"]["i"]
        return cls(G.RingTable.from_dict(p["table"]), p["prm"], ir, p["stat_ref"], p["union"], p["c_stats"], p["meta"], p["a_stats"])


class Stream31:
    """push(pts, pose, t, sample_id) -> (combined Evidence, {layer: Evidence}). reset() at the start of a drive."""

    def __init__(self, domain):
        self.d, self.prev, self.n = domain, None, 0

    def reset(self):
        self.prev, self.n = None, 0

    def push(self, pts, pose, t=0.0, sample_id=None):
        d = self.d
        l1, tl, pair, cur = d.stats.compute(pts, pose, self.prev)
        a = d.scorer.scan_stats(tl["range"].to_numpy(), tl["n_points"].to_numpy(), tl["int_mean"].to_numpy())
        raw = d.raw_from_records(l1, a, pair, d.scorer.n_valid(tl["range"].to_numpy(), tl["n_points"].to_numpy()))
        out = d.evidence(raw, t, sample_id if sample_id is not None else self.n, first=self.prev is None)
        self.prev = PrevScan(pts, pose, img=cur)
        self.n += 1
        return out
