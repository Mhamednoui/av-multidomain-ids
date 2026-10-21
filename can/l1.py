"""WP2 S2: L1 specification rules for CAN, as v3 Layers (domain "can", layer "L1", kind "rule").

Rules (each needs no attack data; learned from attack-free traffic of ONE vehicle, `Profile`):
  id_allow  frame ID never seen in the clean training traffic (1 / 0).
  dlc       DLC not among the DLCs seen for that ID (known IDs only).
  period    periodic IDs only: arrival earlier or later than the learned period beyond a per-ID tolerance;
            raw = max(0, (1 - dt/p) / tol_early, (dt/p - 1) / tol_late), dt = gap to the previous frame of the
            same ID, clipped at 0 (frames.dt_clipped; the sign of dt is never a feature).
  bus_load  bits on the bus in the trailing 1 s (47 + 8 * DLC bits per frame, stuffing ignored) / 1000.
  flood     frames with ID <= the lowest legit ID (= highest-priority legit message) in the trailing 1 s.
Two units: "frame" (one raw score per frame, causal) and "window" (1 s windows; window raw = max of the frame raw
scores inside it, as in v2 window alerts). Calibration (ECDF map + tie-safe budget threshold) is done by
Layer.calibrate on clean validation samples of the unit. A rule can only see what the specification says: a
masquerade that keeps ID, DLC, period and bus load (same-ID replacement frames) is invisible to all five.

Inputs: feature dicts from `make_features` (t, tm = running max of t, id, dlc, dt_id, load, lo, optional window index,
label, att, clean). Outputs: raw arrays; Layer.score gives Evidence lists (small data); big captures use the arrays.
References: Cho & Shin, CIDS (USENIX Security 2016) and Taylor et al. 2016 (frequency/period anomaly detection);
Song, Woo & Kim 2016 (Car-Hacking dataset, ID and interval rules); Verma et al. 2022 (ROAD).
"""
import json

import numpy as np

from can.frames import dt_clipped
from common.calibration import ECDFCalibrator
from common.evidence import Evidence
from common.layer import Layer
from common.metrics import budget_threshold

OVERHEAD_BITS = 47
VARIANTS = [(0.99, 0.05), (0.999, 0.05), (0.99, 0.25), (0.999, 0.25)]   # (quantile q, floor) of the tolerance
MIN_PERIODIC_N = 30
MAX_SPREAD = 0.5            # periodic: interquartile range of the gaps <= 0.5 x median gap
WIN_SPAN = 10 ** 7          # wkey = group_code * WIN_SPAN + window index
SUB_MAX = 50000             # max dt samples per ID kept per add() call (deterministic stride)


# ------------------------------------------------------------------ features
def make_features(t, ids, dlc, label=None, att=None, clean=None, group_code=0, windows=True) -> dict:
    """Profile-independent per-frame quantities of ONE capture, frames in recorded order.
    dt_id: gap to the previous frame of the same ID (dt_clipped, NaN for the first frame of an ID).
    load: bits in the trailing 1 s (incl. this frame) / 1000, using tm = running max of t (monotone clock).
    lo: index of the first frame inside the trailing second (for other trailing sums).
    group_code: int or per-frame int array (capture / part code); window key = group_code * WIN_SPAN + floor(tm)."""
    t = np.asarray(t, dtype=np.float64)
    ids = np.asarray(ids)
    dlc = np.asarray(dlc)
    n = len(t)
    tm = np.maximum.accumulate(t)
    order = np.argsort(ids, kind="stable")
    d = dt_clipped(t[order])
    ids_s = ids[order]
    d[np.r_[True, ids_s[1:] != ids_s[:-1]]] = np.nan
    dt_id = np.empty(n, dtype=np.float32)
    dt_id[order] = d
    lo = np.searchsorted(tm, tm - 1.0, side="right").astype(np.int32)
    cs = np.concatenate(([0], np.cumsum(OVERHEAD_BITS + 8 * dlc.astype(np.int64))))
    load = ((cs[1:] - cs[lo]) / 1000.0).astype(np.float32)
    F = {"t": t, "tm": tm, "id": ids.astype(np.int64), "dlc": dlc.astype(np.int16), "dt_id": dt_id,
         "lo": lo, "load": load,
         "label": np.zeros(n, np.int8) if label is None else np.asarray(label, np.int8),
         "att": np.zeros(n, np.int16) if att is None else np.asarray(att, np.int16),
         "clean": np.ones(n, bool) if clean is None else np.asarray(clean, bool)}
    if windows:
        win = np.floor(tm).astype(np.int64)
        F["wkey"] = (np.asarray(group_code, dtype=np.int64) * WIN_SPAN + win) * np.ones(n, np.int64)
        add_window_index(F)
    return F


def add_window_index(F: dict):
    """wo: stable order by window key; ws: start of each window in that order; wkeys: unique keys;
    w_end: largest tm inside each window (the time at which the window alert can be raised)."""
    wo = np.argsort(F["wkey"], kind="stable")
    k = F["wkey"][wo]
    ws = np.flatnonzero(np.r_[True, k[1:] != k[:-1]])
    F["wo"], F["ws"], F["wkeys"] = wo, ws, k[ws]
    F["w_end"] = np.maximum.reduceat(F["tm"][wo], ws)


def window_reduce(F: dict, values, how="max") -> np.ndarray:
    v = np.asarray(values)[F["wo"]]
    if how == "max":
        return np.maximum.reduceat(v, F["ws"])
    if how == "min":
        return np.minimum.reduceat(v, F["ws"])
    raise ValueError(how)


# ------------------------------------------------------------------ profile
class ProfileBuilder:
    """Accumulates clean traffic (several captures) and finishes into a Profile."""

    def __init__(self):
        self.dlc_pairs = set()
        self.dt = {}
        self.count = {}

    def add(self, ids, dlc, dt_id):
        ids = np.asarray(ids, dtype=np.int64)
        if len(ids) == 0:
            return self
        for v in np.unique(ids * 16 + np.asarray(dlc, dtype=np.int64)):
            self.dlc_pairs.add(int(v))
        order = np.argsort(ids, kind="stable")
        s_id, s_dt = ids[order], np.asarray(dt_id)[order]
        starts = np.flatnonzero(np.r_[True, s_id[1:] != s_id[:-1]])
        ends = np.r_[starts[1:], len(s_id)]
        for a, b in zip(starts, ends):
            i = int(s_id[a])
            self.count[i] = self.count.get(i, 0) + (b - a)
            x = s_dt[a:b]
            x = x[np.isfinite(x)]
            if len(x) > SUB_MAX:
                x = x[:: int(np.ceil(len(x) / SUB_MAX))]
            self.dt.setdefault(i, []).append(x.astype(np.float64))
        return self

    def finish(self) -> "Profile":
        ids = np.array(sorted(self.count), dtype=np.int64)
        mask = np.zeros(len(ids), dtype=np.int64)
        pos = {int(i): k for k, i in enumerate(ids)}
        for v in self.dlc_pairs:
            mask[pos[v // 16]] |= 1 << (v % 16)
        P = Profile()
        P.ids, P.dlc_mask = ids, mask
        P.n = np.array([self.count[int(i)] for i in ids])
        n = len(ids)
        P.periodic, P.p = np.zeros(n, bool), np.ones(n)
        P.e_q = {q: np.zeros(n) for q in (0.99, 0.999)}
        P.l_q = {q: np.zeros(n) for q in (0.99, 0.999)}
        P.spread = np.zeros(n)
        for k, i in enumerate(ids):
            x = np.concatenate(self.dt[int(i)]) if self.dt.get(int(i)) else np.zeros(0)
            if len(x) < MIN_PERIODIC_N:
                continue
            p = float(np.median(x))
            q25, q75 = np.quantile(x, [0.25, 0.75])
            if p <= 0:
                continue
            P.p[k], P.spread[k] = p, (q75 - q25) / p
            P.periodic[k] = P.spread[k] <= MAX_SPREAD
            r = x / p
            for q in (0.99, 0.999):
                P.e_q[q][k] = np.quantile(1.0 - r, q)
                P.l_q[q][k] = np.quantile(r - 1.0, q)
        P.set_variant(0)
        return P


class Profile:
    """Per-vehicle specification learned from clean traffic: allow-list, DLC sets, periods, tolerances."""

    def __init__(self):
        self.ids = np.zeros(0, np.int64)
        self.variant = 0

    @property
    def floor_id(self) -> int:
        return int(self.ids[0])

    def set_variant(self, k: int):
        q, fl = VARIANTS[k]
        self.variant = k
        self.tol_e = np.maximum(self.e_q[q], fl)
        self.tol_l = np.maximum(self.l_q[q], fl)
        return self

    def lookup(self, ids):
        pos = np.searchsorted(self.ids, ids)
        pos = np.minimum(pos, len(self.ids) - 1)
        return pos, self.ids[pos] == ids

    def to_dict(self) -> dict:
        return {"ids": self.ids.tolist(), "dlc_mask": self.dlc_mask.tolist(), "n": self.n.tolist(),
                "periodic": self.periodic.tolist(), "p": self.p.tolist(), "spread": self.spread.tolist(),
                "e_q": {str(q): v.tolist() for q, v in self.e_q.items()},
                "l_q": {str(q): v.tolist() for q, v in self.l_q.items()}, "variant": self.variant}

    @classmethod
    def from_dict(cls, d: dict) -> "Profile":
        P = cls()
        P.ids, P.dlc_mask = np.array(d["ids"], np.int64), np.array(d["dlc_mask"], np.int64)
        P.n, P.periodic, P.p = np.array(d["n"]), np.array(d["periodic"], bool), np.array(d["p"])
        P.spread = np.array(d["spread"])
        P.e_q = {float(q): np.array(v) for q, v in d["e_q"].items()}
        P.l_q = {float(q): np.array(v) for q, v in d["l_q"].items()}
        return P.set_variant(d["variant"])

    def summary(self) -> dict:
        return {"n_ids": int(len(self.ids)), "n_periodic": int(self.periodic.sum()),
                "floor_id": self.floor_id, "variant": VARIANTS[self.variant]}


# ------------------------------------------------------------------ rules
class CanRule(Layer):
    domain = "can"
    kind = "rule"
    layer_id = "L1"
    needs_attack_data = False

    def __init__(self, profile: Profile = None, unit: str = "frame"):
        super().__init__()
        self.profile, self.unit = profile, unit

    # to override: one raw score per frame of the feature dict
    def frame_raw(self, F) -> np.ndarray:
        raise NotImplementedError

    def raw_scores(self, samples) -> np.ndarray:
        r = np.asarray(self.frame_raw(samples), dtype=np.float64)
        return window_reduce(samples, r) if self.unit == "window" else r

    def calibrate(self, F, budget=0.01, unit_mask=None):
        """Layer.calibrate on the units (frames / windows) of F selected by unit_mask (clean ones)."""
        raw = self.raw_scores(F)
        return self.calibrate_from_raw(raw if unit_mask is None else raw[unit_mask], budget)

    def calibrate_from_raw(self, raw, budget=0.01):
        """Same as calibrate, from raw clean scores already computed (several captures concatenated)."""
        raw = np.asarray(raw, dtype=float)
        self.calibrator = ECDFCalibrator().fit(raw)
        self.budget = budget
        self.threshold = budget_threshold(self.calibrator.transform(raw), budget)
        return self

    def calibrated(self, raw) -> np.ndarray:
        return self.calibrator.transform(np.asarray(raw, dtype=float))

    def alarms(self, raw) -> np.ndarray:
        return self.calibrated(raw) >= self.threshold

    def evidence(self, raw, t, sample_ids) -> list:
        """Evidence list from precomputed raw scores (same numbers as score())."""
        raw = np.asarray(raw, dtype=float)
        cal = self.calibrator.transform(raw)
        alarm = cal >= self.threshold
        why = self.reasons(None, raw, alarm)
        return [Evidence(domain=self.domain, layer=self.layer_id, name=self.name, t=float(t[i]),
                         score=float(cal[i]), alarm=bool(alarm[i]), reason=why[i] if alarm[i] else "",
                         details={"raw": float(raw[i])}, sample_id=str(sample_ids[i])) for i in range(len(raw))]

    def score(self, samples) -> list:
        if self.calibrator is None:
            raise RuntimeError("calibrate() first")
        raw = self.raw_scores(samples)
        if self.unit == "window":
            return self.evidence(raw, samples["w_end"], samples["wkeys"])
        return self.evidence(raw, samples["t"], np.arange(len(raw)))

    def reasons(self, samples, raw, alarm) -> list:
        w = "window" if self.unit == "window" else "frame"
        return [f"CAN {w} breaks the {self.name} rule (score {r:.3g}): {self.why}" for r in raw]

    def clone(self, unit: str):
        return type(self)(self.profile, unit)


class IdAllowList(CanRule):
    name = "can.l1_id_allow"
    why = "arbitration ID never seen on this vehicle's normal traffic"

    def frame_raw(self, F):
        _, known = self.profile.lookup(F["id"])
        return (~known).astype(np.float64)


class DlcPerId(CanRule):
    name = "can.l1_dlc"
    why = "DLC not among those this ID uses on this vehicle"

    def frame_raw(self, F):
        pos, known = self.profile.lookup(F["id"])
        bit = (self.profile.dlc_mask[pos] >> F["dlc"].astype(np.int64)) & 1
        return (known & (bit == 0)).astype(np.float64)


class PeriodPerId(CanRule):
    name = "can.l1_period"
    why = "message arrived much earlier or later than its learned period"

    def frame_raw(self, F):
        P = self.profile
        pos, known = P.lookup(F["id"])
        dt = F["dt_id"].astype(np.float64)
        ok = known & P.periodic[pos] & np.isfinite(dt)
        r = np.where(ok, dt, 0.0) / P.p[pos]
        e = (1.0 - r) / P.tol_e[pos]
        l = (r - 1.0) / P.tol_l[pos]
        return np.where(ok, np.maximum(0.0, np.maximum(e, l)), 0.0)


class BusLoad(CanRule):
    name = "can.l1_bus_load"
    why = "more bits on the bus in the last second than in normal traffic"

    def frame_raw(self, F):
        return F["load"].astype(np.float64)


class TopPriorityFlood(CanRule):
    name = "can.l1_flood"
    why = "too many highest-priority-ID frames in the last second"

    def frame_raw(self, F):
        m = (F["id"] <= self.profile.floor_id).astype(np.int64)
        cs = np.concatenate(([0], np.cumsum(m)))
        return (cs[1:] - cs[F["lo"]]).astype(np.float64)


RULE_CLASSES = [IdAllowList, DlcPerId, PeriodPerId, BusLoad, TopPriorityFlood]


def build_rules(profile: Profile, unit: str) -> dict:
    return {c.name: c(profile, unit) for c in RULE_CLASSES}


def calibrate_rules(rules: dict, F, unit_mask, budget: float) -> dict:
    for r in rules.values():
        r.calibrate(F, budget, unit_mask)
    return rules


def raw_all(rules: dict, F) -> dict:
    """name -> raw array (frame or window unit, per the rules' unit)."""
    return {n: r.raw_scores(F) for n, r in rules.items()}


def noisy_or(cal_list) -> np.ndarray:
    out = np.ones_like(cal_list[0], dtype=np.float64)
    for c in cal_list:
        out *= 1.0 - c
    return 1.0 - out


def combined_threshold(cal_clean_list, budget: float) -> float:
    return budget_threshold(noisy_or(cal_clean_list), budget)
