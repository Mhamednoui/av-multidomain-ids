"""LidarDomain: the deployable LiDAR domain detector of v3 (WP3 S9, frozen for WP6 S5b / WP7).

Purpose: turn a stream of velodyne scans (+ the ego pose of every scan) into Evidence: one combined domain Evidence per scan
("lidar.combined", layer "combined") and one Evidence per headline layer, each with the physics reason of its alarm; plus the LiDAR odometry
MotionEstimate (source "lidar", passed through from gps.lidar_odom, independent of GPS / CAN).
Headline zero-shot stack (no attack label anywhere in the fit; thresholds by leave-one-drive-out over the 16 train+val KITTI drives):
  L1  sensor geometry: points off the 64 laser rings, impossible ranges / intensities, two returns in one beam direction (lidar.geometry)
  L2a object intensity (and, only if frozen with it, density) of angular tiles inside clusters versus clean objects at the same range (lidar.density)
  L2c background model: returns the previous scan (moved by the ego pose) predicts per ring / azimuth window but the scan does not have (lidar.background)
  L2d tracking: a surface that appears in free space or follows the sensor instead of the world (lidar.track)
Combiner: lidar.combine.Stack (max / noisy_or / split of the ECDF ranks, chosen on validation, label-free), threshold = tie-safe 1 % of the
out-of-fold clean scores of the 16 train+val drives. Not in the stack: L2b occlusion (optional), L3 (dropped), L4 (seen families only).
Inputs: scan = float32 N x 4 (x forward, y left, z up, intensity 0-1); pose = (x, y, yaw) planar pose of the scan in any local world frame
(KITTI: lidar.ego.poses from OXTS; the ego pose is an INPUT - a deployment without INS may feed LiDAR odometry poses, untested); prev = (scan, pose)
of the previous scan (None for the first scan: L2c / L2d are then not available and contribute rank 0, flagged in details).
Outputs: common.evidence.Evidence; save(folder) / load(folder) (domain.pkl + domain.json + intensity_ecdf.npz + the ring table and calibration it needs; ~6 MB).
Reference: ARCHITECTURE.md sections 2-4; reports/M1_LiDAR.md; notes/WP3_brief.md "Frozen LiDAR domain output"."""
import json
import pickle
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from common.evidence import Evidence
from lidar import background as B
from lidar import calibration as C
from lidar import density as D
from lidar import geometry as G
from lidar import s4_eval as E4
from lidar import segment as S
from lidar.background_build import pair_row
from lidar.combine import Stack
from lidar.s4_build import tiles as make_tiles

SCHEMA_VERSION = 1
LAYERS = ("L1", "L2a", "L2c", "L2d")
COLS = ["raw_" + x for x in LAYERS]
NAMES = {"L1": "lidar.l1_geometry", "L2a": "lidar.l2a_intensity", "L2c": "lidar.l2c_background", "L2d": "lidar.l2d_tracking"}
PHYSICS = {
    "L1": "sensor geometry broken: returns off the laser rings, impossible range / intensity or two returns in one beam",
    "L2a": "object surface inconsistent with clean objects at that range (intensity of a patch is unusual: spoofed reflectivity)",
    "L2c": "returns the previous scan predicts in a ring / azimuth window are missing: part of the scene was removed",
    "L2d": "a surface appeared in free space or follows the sensor instead of the world: injected object",
}
UNAVAILABLE = ("L2c", "L2d")                       # need the previous scan


class IntensityModel(D.ObjectModel):
    """The intensity half of lidar.density.ObjectModel: the only half the headline L2a (intensity part) reads. The density tables (9 million
    reference residuals) are dropped, so the frozen file is 5 MB instead of 110 MB; the four intensity columns of scores() are identical to
    ObjectModel.scores (same code path, tested), the two density columns are 0."""

    @classmethod
    def from_model(cls, m):
        o = cls(m.calib, m.nmin)
        o.i, o.nref = m.i, m.nref
        return o

    def scores(self, objs):
        out = np.zeros((len(objs), 4))
        m = self.valid(objs)
        if not m.any():
            return pd.DataFrame(out, columns=D.STATS, index=objs.index)
        o = objs[m]
        im = o["int_mean"].to_numpy()
        rb, _ = self.keys(o)
        nb = np.clip(np.searchsorted(D.N_EDGES, o["n_points"].to_numpy(), side="right") - 1, 0, len(D.N_EDGES) - 2)
        res = np.zeros((m.sum(), 4))
        for r in np.unique(rb):
            mr = rb == r
            for q in np.unique(nb[mr]):
                mq = mr & (nb == q)
                res[mq, 2], res[mq, 3] = D.tail_scores(self.i.get((r, q), self.i[(r, -1)]), im[mq])
        out[m] = res
        return pd.DataFrame(out, columns=D.STATS, index=objs.index)


class LidarDomain:
    def __init__(self, parts, stack, meta):
        self.table, self.calib, self.model, self.prm = parts["table"], parts["calib"], parts["model"], parts["prm"]
        self.layers = {"L1": parts["l1"], "L2a": parts["a2"], "L2c": parts["l2c"], "L2d": parts["l2d"]}
        self.stack, self.meta = stack, meta
        self.edges = B.ring_edges(self.table)

    # ---- statistics of one scan -------------------------------------------------------------------
    def statistics(self, pts, pose, prev=None):
        """(L1 statistics row, L2a tile-statistics row, S6 pair statistics row or None) of one scan."""
        tab, lab, _ = S.segment(pts, self.table, self.prm, return_labels=True)
        tl = make_tiles(pts, lab, self.table.assign(pts)["k"])
        tl.insert(0, "scan", "s")
        tl["ring_min"], tl["ring_max"], tl["az_span"] = 0.0, 7.0, 2.0 - 0.1728
        a2 = E4.scan_frame(self.model, tl, pd.DataFrame({"scan": ["s"]}))
        l1 = pd.DataFrame([dict(zip(G.STAT_NAMES, G.l1_stats(pts, self.table)))])
        s6 = None if prev is None else pd.DataFrame([pair_row(prev[0], prev[1], pts, pose, self.edges)])
        return l1, a2, s6

    def raw_scores(self, pts, pose, prev=None):
        """dict layer -> raw score (float) of one scan; layers that need the previous scan score 0.0 on the first scan."""
        l1, a2, s6 = self.statistics(pts, pose, prev)
        raw = {"L1": float(self.layers["L1"].raw_scores(l1)[0]), "L2a": float(self.layers["L2a"].raw_scores(a2)[0])}
        for x in UNAVAILABLE:
            raw[x] = float(self.layers[x].raw_scores(s6)[0]) if s6 is not None else 0.0
        return raw, (l1, a2, s6)

    # ---- Evidence ----------------------------------------------------------------------------------
    def score_scan(self, pts, pose, prev=None, t=0.0, sample_id=""):
        """(combined Evidence, {layer: Evidence}) of one scan. Causal: depends on this scan and the previous one only."""
        raw, (l1, a2, s6) = self.raw_scores(pts, pose, prev)
        frames = {"L1": l1, "L2a": a2, "L2c": s6, "L2d": s6}
        per = {}
        for x in LAYERS:
            lay = self.layers[x]
            if frames[x] is None:
                per[x] = Evidence(domain="lidar", layer=x, name=NAMES[x], t=float(t), score=0.0, alarm=False, reason="",
                                  details={"raw": 0.0, "available": False}, sample_id=str(sample_id))
                continue
            ev = lay.score(frames[x].assign(t=float(t), sample_id=str(sample_id)))[0]
            ev.name, ev.reason = NAMES[x], (PHYSICS[x] + f" [{ev.reason}]" if ev.alarm else "")
            ev.details["available"] = True
            per[x] = ev
        row = pd.DataFrame([{c: raw[c[4:]] for c in COLS}])
        stat = float(self.stack.stat(row)[0])
        alarm = bool(stat >= self.stack.threshold)
        score = float(self.stack.cal.transform(np.array([stat]))[0])
        reason = ""
        if alarm:
            dom = LAYERS[int(self.stack.dominant(row)[0])]
            fired = [x for x in LAYERS if per[x].alarm]
            reason = f"LiDAR domain alarm ({self.stack.method}): {PHYSICS[dom]}" + (f"; layers alone over their own 1 %: {', '.join(fired)}" if fired else "; no layer alone is over its own 1 %, the shared budget raised the bar")
        comb = Evidence(domain="lidar", layer="combined", name="lidar.combined", t=float(t), score=score, alarm=alarm, reason=reason,
                        details={"method": self.stack.method, "stat": stat, "layer_scores": {x: per[x].score for x in LAYERS},
                                 "layer_raw": raw, "first_scan_no_previous": prev is None, "stack_threshold": float(self.stack.threshold)},
                        sample_id=str(sample_id))
        return comb, per

    def stream(self):
        return LidarStream(self)

    # ---- LiDAR odometry MotionEstimate (passthrough of gps.lidar_odom, source "lidar") ---------------
    @staticmethod
    def odometry(paths, log=None):
        """Scan-to-scan point-to-plane ICP over ordered scan files -> (planar poses P (n,3) in the first scan's frame, quality (n-1,5))."""
        from gps import lidar_odom as LO
        rel, q = LO.scan_odometry(paths, log=log)
        return LO.chain_poses(rel), q

    @staticmethod
    def motion_estimates(t_fix, P, t_scan, quality=None):
        """MotionEstimate list (source "lidar", body frame, displacement over the last second) at the times t_fix from the odometry poses P at
        the scan times t_scan. quality: the (n-1,5) quality array of odometry(); a fix whose last second contains an ICP fallback gets sigma x3."""
        from gps import lidar_odom as LO
        ok = None
        if quality is not None:
            tq = np.asarray(t_scan, float)[1:]
            ok = np.array([bool((np.asarray(quality)[(tq > t - 1.0) & (tq <= t), 4] == 0).all()) for t in np.asarray(t_fix, float)])
        return LO.motion_estimates(np.asarray(t_fix, float), P, np.asarray(t_scan, float), quality_ok=ok)

    # ---- persistence -------------------------------------------------------------------------------
    def save(self, folder, ring_table_file, calib_file):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy(ring_table_file, folder / "ring_table.json")
        shutil.copy(calib_file, folder / "calibration_beta.npz")
        model = self.model
        if isinstance(model, IntensityModel):
            np.savez_compressed(folder / "intensity_ecdf.npz", **{f"{k[0]}_{k[1]}": v for k, v in model.i.items()})
            model = IntensityModel(model.calib, model.nmin)
        parts = {"model": model, "prm": self.prm, "l1": self.layers["L1"], "a2": self.layers["L2a"], "l2c": self.layers["L2c"],
                 "l2d": self.layers["L2d"], "stack": self.stack, "meta": self.meta, "schema": SCHEMA_VERSION}
        with open(folder / "domain.pkl", "wb") as fh:
            pickle.dump(parts, fh, protocol=4)
        info = dict(self.meta, schema=SCHEMA_VERSION, method=self.stack.method, budget=self.stack.budget, stack_threshold=float(self.stack.threshold),
                    layers=list(LAYERS), layer_thresholds={x: float(self.layers[x].threshold) for x in LAYERS})
        (folder / "domain.json").write_text(json.dumps(info, indent=1))

    @classmethod
    def load(cls, folder):
        folder = Path(folder)
        with open(folder / "domain.pkl", "rb") as fh:
            p = pickle.load(fh)
        assert p["schema"] == SCHEMA_VERSION
        model = p["model"]
        if isinstance(model, IntensityModel):
            z = np.load(folder / "intensity_ecdf.npz")
            model.i = {tuple(int(x) for x in k.split("_")): z[k] for k in z.files}
        parts = {"table": G.RingTable.load(folder / "ring_table.json"), "calib": C.load_calib(folder / "calibration_beta.npz"), "model": model,
                 "prm": p["prm"], "l1": p["l1"], "a2": p["a2"], "l2c": p["l2c"], "l2d": p["l2d"]}
        return cls(parts, p["stack"], p["meta"])


class LidarStream:
    """Feed scans in time order: push(pts, pose, t, sample_id) -> (combined Evidence, per-layer dict). reset() at the start of a drive."""

    def __init__(self, domain):
        self.d, self.prev, self.n = domain, None, 0

    def reset(self):
        self.prev, self.n = None, 0

    def push(self, pts, pose, t=0.0, sample_id=None):
        out = self.d.score_scan(pts, pose, self.prev, t, sample_id if sample_id is not None else self.n)
        self.prev = (pts, np.asarray(pose, float))
        self.n += 1
        return out
