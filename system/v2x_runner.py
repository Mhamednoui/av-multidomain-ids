"""V2X physics-only domain (frozen recipe of M1-V2X) and its streaming runner, one received message at a time (WP7 S1).

Domain (V2XPhysicsDomain): the deployable physics-only stack L1 + L2 + L3 of reports/M1_V2X.md, built by the recipe of tools/WP5_S6_run.py (no V2X domain object exists in
v2x/; WP5 froze the recipe, not a saved file): 12 checks = L1 beacon_rate + field_ranges; L2 pos_speed, pos_heading, speed_change, implied_speed, heading_rate,
accel_consistency, overlap; L3 kf_nis, kf_cusum_hi (Kalman parameters results/WP5/s4_params_veremi.json), track_birth. Raw scores come from v2x.l4.message_scores (the
same code the WP5 harness used), cast to float32 exactly like the S6 feature tables; each check is ECDF-calibrated on GENUINE validation messages with the tie-safe 1%
threshold; combined score = max of the calibrated scores (combiner "max", chosen by WP5 on validation halves for this group), threshold = tie-safe 1% of the genuine
validation combined scores. fit() is called on the VeReMi validation split without held-out types 6 / 12 / 17 (as S6). Saved as JSON (calibrators are sorted arrays).
Evidence: per message one combined (domain "v2x", layer "combined", name "v2x.combined", sample_id = msg_id) and optionally the 12 per-check Evidence (layers L1 / L2 / L3).

Runner (V2XRunner): messages arrive in time order from many senders (one receiver's view). The layers need, for one message, only
  (a) the earlier messages of the same track (Kalman segment, pair checks, beacon rate), and
  (b) for the overlap check: every message of other tracks heard in the last 1 s, and for the birth check: the first message of every track born in the last 10 s;
  the first message of each included track is added so no old track looks newborn.
The runner keeps those, builds that small context table, runs the frozen raw-score code on it and takes the row of the new message: the result equals the one obtained on the
whole table (tests/system, tools/WP7_S1_v2x.py). Cost: grows with the length of the sender's own track and with the traffic of the last second.
Order contract: input in nondecreasing stream time. Caveat (frozen code): v2x.l3.birth_density also counts births with EQUAL timestamp that come later in the table; a stream
cannot know them. The runner counts equal-timestamp arrivals in `tie_events` (0 on VeReMi validation) and decreasing timestamps in `out_of_order`.
Reference: reports/M1_V2X.md; notes/WP5_brief.md; v2x/l1.py, l2.py, l3.py, l4.py.
"""
import json
from collections import deque
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

from common.calibration import ECDFCalibrator
from common.evidence import Evidence
from common.metrics import budget_threshold
from system.runner import Runner
from v2x import l1, l2, l3, l4

L1_N = ["v2x.beacon_rate", "v2x.field_ranges"]
L2_N = ["v2x.pos_speed", "v2x.pos_heading", "v2x.speed_change", "v2x.implied_speed", "v2x.heading_rate", "v2x.accel_consistency", "v2x.overlap"]
L3_N = ["v2x.kf_nis", "v2x.kf_cusum_hi", "v2x.track_birth"]
LAYER_NAMES = L1_N + L2_N + L3_N
LAYER_ID = {**{n: "L1" for n in L1_N}, **{n: "L2" for n in L2_N}, **{n: "L3" for n in L3_N}}
RAW_KEY = {"v2x.beacon_rate": "rate", "v2x.field_ranges": "field_raw", "v2x.pos_speed": "pos_speed", "v2x.pos_heading": "pos_heading", "v2x.speed_change": "speed_change",
           "v2x.implied_speed": "implied_speed", "v2x.heading_rate": "heading_rate", "v2x.accel_consistency": "accel_consistency", "v2x.overlap": "overlap",
           "v2x.kf_nis": "nis", "v2x.kf_cusum_hi": "cusum_hi", "v2x.track_birth": "birth"}
HELDOUT = [6, 12, 17]
BUDGET = 0.01
CTX_COLUMNS = ["msg_id", "sender", "track", "t", "x", "y", "speed", "vx", "vy", "heading", "acl", "yaw_rate", "rx_id"]
OVERLAP_S, BIRTH_S, MARGIN_S = l2.W_OVERLAP, l3.BIRTH_WINDOW_S, 0.5


class V2XPhysicsDomain:
    def __init__(self, tracker: l3.Tracker, budget=BUDGET):
        self.tracker, self.budget = tracker, budget
        self.cal = {}
        self.thr = {}
        self.comb_thr = None
        self.method = "max"
        self._layers = None

    # ---- raw scores ----------------------------------------------------------------------------------
    def raws(self, df) -> dict:
        """Raw scores of the 12 checks for every row of a (time-ordered) message table; float32 like the S6 feature tables."""
        r = l4.message_scores(df, self.tracker)
        return {n: np.asarray(r[RAW_KEY[n]], dtype=np.float32) for n in LAYER_NAMES}

    def calibrated(self, raws) -> dict:
        return {n: self.cal[n].transform(np.asarray(raws[n], float)) for n in LAYER_NAMES}

    # ---- fit -----------------------------------------------------------------------------------------
    def fit(self, val_df, genuine=None):
        """val_df: validation messages (held-out types removed), genuine = bool mask (label == 0)."""
        raws = self.raws(val_df)
        g = (val_df["label"].to_numpy() == 0) if genuine is None else np.asarray(genuine, bool)
        cals = {}
        for n in LAYER_NAMES:
            c = ECDFCalibrator().fit(np.asarray(raws[n], float)[g])
            cals[n] = c
            self.thr[n] = float(budget_threshold(c.transform(np.asarray(raws[n], float)[g]), self.budget))
        self.cal = cals
        comb = np.max(np.stack([cals[n].transform(np.asarray(raws[n], float)) for n in LAYER_NAMES]), axis=0)
        self.comb_thr = float(budget_threshold(comb[g], self.budget))
        return self

    # ---- Evidence --------------------------------------------------------------------------------------
    def _layer_objects(self):
        if self._layers is None:
            objs = {l.name: l for l in l1.make_layers() + l2.make_layers() + l3.make_layers(self.tracker)}
            self._layers = {n: objs[n] for n in LAYER_NAMES}
        return self._layers

    def evidence(self, df, raws, idx, per_layer=False) -> List[Evidence]:
        """Evidence of the rows idx of df given the raw dict of THAT table (same row positions). [combined (+ 12 per-layer)] per row."""
        cal = self.calibrated(raws)
        lay = self._layer_objects()
        out = []
        for i in idx:
            t = float(df["t"].iat[i])
            sid = str(df["msg_id"].iat[i])
            sender = str(df["sender"].iat[i])
            scores = {n: float(cal[n][i]) for n in LAYER_NAMES}
            fired = sorted([(s, n) for n, s in scores.items() if s >= self.thr[n]], reverse=True)
            comb = max(scores.values())
            alarm = bool(comb >= self.comb_thr)
            reason = ""
            if alarm:
                why = "; ".join(f"{n} ({s:.3f}): " + lay[n].reasons(df.iloc[[i]], np.asarray([raws[n][i]]), np.asarray([True]))[0] for s, n in fired[:3]) \
                    if fired else "the combined score is above its budget threshold"
                reason = f"V2X message from sender {sender}: {why}"
            out.append(Evidence(domain="v2x", layer="combined", name="v2x.combined", t=t, score=comb, alarm=alarm, reason=reason,
                                details={"method": self.method, "layer_scores": scores}, sample_id=sid))
            if per_layer:
                for n in LAYER_NAMES:
                    a = bool(scores[n] >= self.thr[n])
                    out.append(Evidence(domain="v2x", layer=LAYER_ID[n], name=n, t=t, score=scores[n], alarm=a,
                                        reason=lay[n].reasons(df.iloc[[i]], np.asarray([raws[n][i]]), np.asarray([True]))[0] if a else "",
                                        details={"raw": float(raws[n][i])}, sample_id=sid))
        return out

    def score_table(self, df, per_layer=False) -> List[Evidence]:
        """BATCH reference: Evidence for every row of a whole time-ordered table."""
        return self.evidence(df, self.raws(df), range(len(df)), per_layer)

    # ---- persistence -----------------------------------------------------------------------------------
    def save(self, folder):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        meta = {"schema": 1, "budget": self.budget, "method": self.method, "layers": LAYER_NAMES, "thresholds": self.thr, "combined_threshold": self.comb_thr,
                "tracker_params": self.tracker.params.to_dict(), "cal": {n: {"scale": c.scale_, "sorted": c.sorted_.tolist()} for n, c in self.cal.items()},
                "recipe": "tools/WP5_S6_run.py without L4; fit on VeReMi validation without held-out types 6/12/17; genuine rows calibrate"}
        (folder / "domain.json").write_text(json.dumps(meta))

    @classmethod
    def load(cls, folder):
        m = json.loads((Path(folder) / "domain.json").read_text())
        d = cls(l3.Tracker(l3.KalmanParams(**m["tracker_params"])), m["budget"])
        d.thr, d.comb_thr, d.method = m["thresholds"], m["combined_threshold"], m["method"]
        for n, c in m["cal"].items():
            k = ECDFCalibrator()
            k.sorted_, k.scale_ = np.asarray(c["sorted"], float), float(c["scale"])
            d.cal[n] = k
        return d


class V2XRunner(Runner):
    domain = "v2x"
    name = "v2x.runner"
    status = "frozen"
    period_s = 0.1

    def __init__(self, dom: V2XPhysicsDomain, bus=None, per_layer=False):
        super().__init__(bus)
        self.dom, self.per_layer = dom, per_layer
        self._reset("")

    def _reset(self, key):
        self.tracks = {}              # track -> list of row dicts (whole history of the track)
        self.first = {}               # track -> first row dict
        self.recent = deque()         # rows of the last OVERLAP_S (+margin) seconds, all tracks
        self.births = deque()         # (t, track) of births in the last BIRTH_S (+margin) seconds
        self.seq = 0
        self.last_t = -np.inf
        self.tie_events = 0
        self.out_of_order = 0
        self.n_ctx_rows = []

    def _size(self):
        return self.seq

    @staticmethod
    def _row(sample, seq):
        r = {c: sample.get(c) for c in CTX_COLUMNS}           # dict or pandas row; a missing receiver id stays None
        r["seq"] = seq
        return r

    def _push(self, sample) -> List[Evidence]:
        row = self._row(sample, self.seq)
        self.seq += 1
        t, tr = float(row["t"]), row["track"]
        if t == self.last_t:
            self.tie_events += 1
        if t < self.last_t:
            self.out_of_order += 1
        self.last_t = max(self.last_t, t)
        # prune what the layers can no longer see
        while self.recent and self.recent[0]["t"] < t - OVERLAP_S - MARGIN_S:
            self.recent.popleft()
        while self.births and self.births[0][0] < t - BIRTH_S - MARGIN_S:
            self.births.popleft()
        hist = self.tracks.setdefault(tr, [])
        is_new = not hist
        # context: own history + this message + other tracks' recent rows + first rows of the tracks involved
        rows = list(hist)
        rows.append(row)
        have = {id(r) for r in rows}
        involved = {r["track"] for r in self.recent if r["track"] != tr} | {b[1] for b in self.births if b[1] != tr}
        for r in self.recent:
            if r["track"] != tr:
                rows.append(r)
                have.add(id(r))
        for o in involved:
            f = self.first[o]
            if id(f) not in have:
                rows.append(f)
        ctx = pd.DataFrame(rows).sort_values(["t", "seq"], kind="stable").reset_index(drop=True)
        self.n_ctx_rows.append(len(ctx))
        i = int(np.flatnonzero(ctx["seq"].to_numpy() == row["seq"])[0])
        raws = self.dom.raws(ctx)
        out = self.dom.evidence(ctx, raws, [i], self.per_layer)
        # update the state with the new message
        hist.append(row)
        self.recent.append(row)
        if is_new:
            self.first[tr] = row
            self.births.append((t, tr))
        return out
