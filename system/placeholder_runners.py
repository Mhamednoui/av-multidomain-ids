"""LiDAR interim runner and network placeholder runner (WP7 S1). Both are LABELLED: Evidence.details["status"] and Runner.status say so.

LidarInterimRunner (status "interim"): the WP3 S1 baseline = the v2 XGBoost scan classifier retrained in v3 (4 classes Normal / PointDrop / IntensitySpoof / GhostCluster on the
429-dim descriptor: 211 per-scan features + 211 scan-to-scan differences + 7 summaries; lidar.features.describe / temporal; model ../data_extra/cache_v3/WP3/retrained_deployed.json).
Score = ECDF calibration of 1 - P(Normal) on the NORMAL VALIDATION scans of the WP3 S1 cache, alarm = tie-safe 1% threshold. It is NOT the final LiDAR domain: WP3 S2-S4 results
(single-return physics, object-level checks) are not frozen; the baseline has known blind spots (phantoms that replace real returns). Use only to exercise the runtime.
One scan in, one Evidence out; state = descriptor of the previous scan of the drive (the first scan of a drive has no previous: its temporal features are zero, flagged in details).
Sample: dict {"points": N x 4 float32 (x y z intensity in 0..1), "t": seconds, "sample_id": "<drive>/<file>"}.

NetworkRunner (status "placeholder"): M1-NET is not frozen (WP4 S7 running, no reports/M1_NET.md). Without a domain it emits a neutral Evidence per flow (score 0, no alarm) so the
bus, latency log and fusion plumbing can be exercised with the final interface. With `domain` = an object that has score_stream(flows DataFrame) -> (combined list, per-layer dict)
(network.domain.NetworkDomain's documented interface) it re-scores a rolling buffer and returns the combined Evidence of the new flow with details["final"] as that domain defines it
(window semantics: the Evidence of a flow is final only when its windows closed). This adapter is written to the DOCUMENTED interface and tested with a stand-in object only.
Reference: notes/WP3_brief.md, results/WP3/cache/a3.json, network/domain.py docstring, notes/WP7_system.md.
"""
import json
from pathlib import Path
from typing import List

import numpy as np

from common.calibration import ECDFCalibrator
from common.evidence import Evidence
from common.metrics import budget_threshold
from lidar.features import describe, temporal
from system.runner import Runner

MODEL_PATH_REL = Path("cache_v3") / "WP3" / "retrained_deployed.json"


class LidarInterimModel:
    """XGBoost 4-class scan model + ECDF calibration. fit_calibration(scores_val_normal) -> sets calibrator and threshold."""

    def __init__(self, model_path, budget=0.01):
        import xgboost as xgb
        self.model = xgb.XGBClassifier()
        self.model.load_model(str(model_path))
        self.model.set_params(device="cpu", n_jobs=2)
        self.model_path, self.budget = str(model_path), budget
        self.cal, self.threshold = None, None

    def raw(self, X) -> np.ndarray:
        """1 - P(Normal) for rows of the 429-dim feature matrix (float32)."""
        return 1.0 - self.model.predict_proba(np.atleast_2d(X).astype(np.float32))[:, 0]

    def fit_calibration(self, raw_val_normal):
        self.cal = ECDFCalibrator().fit(raw_val_normal)
        self.threshold = float(budget_threshold(self.cal.transform(raw_val_normal), self.budget))
        return self

    def save_calibration(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps({"model": self.model_path, "budget": self.budget, "threshold": self.threshold, "cal": self.cal.to_dict(),
                                          "status": "interim (WP3 S1 v2-baseline retrained in v3)"}))

    def load_calibration(self, path):
        d = json.loads(Path(path).read_text())
        self.budget, self.threshold = d["budget"], d["threshold"]
        self.cal = ECDFCalibrator.from_dict(d["cal"])
        return self


class LidarInterimRunner(Runner):
    domain = "lidar"
    name = "lidar.interim_runner"
    status = "interim"
    period_s = 0.1

    def __init__(self, model: LidarInterimModel, bus=None):
        super().__init__(bus)
        self.m = model
        self.prev = None
        self.n = 0

    def _reset(self, key):
        self.prev, self.n = None, 0

    def _size(self):
        return self.n

    def features(self, pts):
        cur = describe(pts)
        first = self.prev is None
        row = np.r_[cur, temporal(cur, cur if first else self.prev)]
        self.prev = cur
        return row, first

    def _push(self, sample) -> List[Evidence]:
        row, first = self.features(sample["points"])
        raw = float(self.m.raw(row)[0])
        score = float(self.m.cal.transform(raw))
        alarm = bool(score >= self.m.threshold)
        self.n += 1
        return [Evidence(domain="lidar", layer="combined", name="lidar.interim_v2_baseline", t=float(sample["t"]), score=score, alarm=alarm,
                         reason=(f"interim LiDAR baseline: the scan descriptor looks like point drop / intensity spoofing / a ghost cluster (attack probability {raw:.3f})" if alarm else ""),
                         details={"raw_p_attack": raw, "first_scan_no_previous": first, "model": "WP3 S1 retrained v2 baseline (interim)"},
                         sample_id=str(sample.get("sample_id", self.n - 1)))]


class NetworkRunner(Runner):
    domain = "network"
    name = "network.runner"
    status = "placeholder"
    period_s = 0.001

    def __init__(self, domain=None, bus=None, buffer=2000):
        super().__init__(bus)
        self.dom, self.buffer_n = domain, buffer
        self.rows = []
        self.n = 0

    def _reset(self, key):
        self.rows, self.n = [], 0

    def _size(self):
        return self.n

    def _push(self, flow) -> List[Evidence]:
        self.n += 1
        t = float(flow.get("t", flow.get("ts", self.n)))
        sid = str(flow.get("sample_id", self.n - 1))
        if self.dom is None:
            return [Evidence(domain="network", layer="combined", name="network.placeholder", t=t, score=0.0, alarm=False, reason="",
                             details={"note": "no network detector wired: M1-NET not frozen"}, sample_id=sid)]
        import pandas as pd
        self.rows.append(dict(flow))
        self.rows = self.rows[-self.buffer_n:]
        comb, _ = self.dom.score_stream(pd.DataFrame(self.rows))
        e = comb[-1]
        e.sample_id = sid
        return [e]
