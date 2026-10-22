"""CanDomain: the deployable CAN domain detector of v3 (WP2 S7, frozen for WP6 / WP7).

Purpose: turns the raw frames of one CAN capture / stream (t, arbitration ID, DLC, payload bytes) into
(1) one Evidence per 1 s window and layer (L1 specification rules, L2b signal relations, L3c per-signal predictors, L3d reverse-light state rule),
(2) one combined domain Evidence per window ("can.combined", layer "combined") with the physics reason of every alarm, and
(3) ego-motion estimates from the four wheel speeds (MotionEstimate, source "can").
Stack (default, decided in WP2 S7): L1 + L2b relations-only + L3c + L3d. L2a clock skew and L4 learned timing / payload models are OUT of the default (negative
results of S3 / S6; code kept in can/l2a_*.py, can/l4_*.py).
Layer scores: raw window score -> ECDF calibration on the pooled leave-one-capture-out clean windows -> noisy-or / max / logistic combiner of
common.combiner.DomainCombiner (method chosen on validation), alarm = score >= tie-safe 1% threshold of the pooled clean windows. No attack frame is used in any fit.
Inputs (score_capture): t (s, recorded order), ids, dlc, B (n x 8 uint8). A window is the integer second of the running-max clock and is emitted once its second
has passed (causal; the first second of a capture is not scored). Outputs: lists of common.evidence.Evidence / common.motion.MotionEstimate; save(folder) / load(folder).
Vehicle: the models are specific to the ROAD vehicle (anonymised DBC of one car). A different vehicle needs its own clean calibration; ID / DLC rules do not
transfer (S2: 100% false alarms zero-shot) and the DBC-based layers need that vehicle's DBC.
Reference: ARCHITECTURE.md sections 2-4; reports/M1_CAN.md; notes/WP2_brief.md "Frozen CAN domain output".
"""
import json
import pickle
from pathlib import Path

import numpy as np

from can import l3_predictors as P
from can import signals as S
from can.stack_core import CAT, DBC, UnitData, make_grid, window_raws, Z
from can.stack_eval import noisy_or_log
from common.combiner import DomainCombiner
from common.evidence import Evidence
from common.motion import MotionEstimate
from common.metrics import budget_threshold

SCHEMA_VERSION = 1
RULES = ["can.l1_id_allow", "can.l1_dlc", "can.l1_period", "can.l1_bus_load", "can.l1_flood"]
WHEELS = [(0x6E0, 0), (0x6E0, 1), (0x6E0, 2), (0x6E0, 3)]       # four wheel speeds (S4: identified from the attack metadata and correlation, DBC anonymised)
WHEEL_UNIT_MPS = 0.01 / 3.6        # ASSUMPTION: raw unit 0.01 km/h (typical; the anonymised DBC has factor 1 and no unit). Calibrate against GPS / LiDAR in WP6.
SPEED_SIGMA_MIN, SPEED_SIGMA_REL = 0.3, 0.03     # m/s floor and relative part of the 1-sigma of the wheel-speed estimate (engineering choice, wheel slip unmodelled)
LAYER_ORDER = ["L1", "L2b", "L3c", "L3d"]
LAYER_NAMES = {"L1": "can.l1_spec_rules", "L2b": "can.l2b_signal_relations", "L3c": "can.l3c_signal_predictors", "L3d": "can.l3d_reverse_state"}
LAYER_WHY = {"L1": "a specification rule of this vehicle is broken (unknown ID / DLC, wrong period, bus load or flood)",
             "L2b": "decoded signals leave the physical relations learned from attack-free driving",
             "L3c": "a signal disagrees with the prediction from the signals that physically tie to it",
             "L3d": "the reverse-light flag contradicts the gear state for longer than any legitimate lag"}


def layer_raws(tab: dict, cfg: dict, ecdf_rules: dict) -> dict:
    """Window raw of every layer (all windows of a window_raws table). cfg: l1_variant, K (L2b types or None), l3c (design, r_min, pool), l3d_floor."""
    k = cfg["l1_variant"]
    key = lambda r: f"l1_{r}#{k}" if r == "can.l1_period" else f"l1_{r}"
    out = {"L1": noisy_or_log(np.column_stack([ecdf_rules[r].transform(tab[key(r)]) for r in RULES]))}
    if cfg.get("K"):
        out["L2b"] = np.max(np.stack([tab[f"l2b_{x}"] for x in cfg["K"]]), axis=0)
    m, r, _ = cfg["l3c"]
    out["L3c"] = tab[f"l3c_{m}@{r}"]
    out["L3d"] = np.where(tab["l3d"] > cfg["l3d_floor"], tab["l3d"], 0.0).astype(np.float32)
    return out


class CanDomain:
    """Frozen domain: RoadModels + design + calibrators + combiner. Build with `freeze` (tools/WP2_S7_final.py)."""

    def __init__(self, models, cfg, ecdf_rules, calib, combiner: DomainCombiner, layer_thresholds: dict, budget=0.01):
        self.models, self.cfg, self.ecdf_rules, self.calib = models, cfg, ecdf_rules, calib
        self.combiner, self.layer_thresholds, self.budget = combiner, layer_thresholds, budget
        self.layers = [l for l in LAYER_ORDER if l in calib]

    # ---- scoring ---------------------------------------------------------------------------------
    def table(self, U: UnitData) -> dict:
        return window_raws(self.models, U)

    def calibrated(self, tab: dict) -> dict:
        raws = layer_raws(tab, self.cfg, self.ecdf_rules)
        return {l: self.calib[l].transform(raws[l]) for l in self.layers}

    def evidence_from_table(self, tab: dict, sample_prefix="", reasons=None):
        """(combined Evidence list, {layer: Evidence list}) for the scored windows (grid exists) of a window table."""
        cal = self.calibrated(tab)
        ok = np.flatnonzero(tab["ok"])
        names = sorted(self.layers)
        per = {l: [] for l in self.layers}
        for i in ok:
            for l in self.layers:
                s = float(cal[l][i])
                per[l].append(Evidence(domain="can", layer=l, name=LAYER_NAMES[l], t=float(tab["w_end"][i]), score=s,
                                       alarm=s >= self.layer_thresholds[l], sample_id=f"{sample_prefix}{int(tab['sec'][i])}"))
        comb_in = {LAYER_NAMES[l]: per[l] for l in self.layers}
        # DomainCombiner sorts layer names alphabetically; it expects the same layer names it was fitted with
        comb = self.combiner.combine(comb_in)
        for e, i in zip(comb, ok):
            e.name = "can.combined"
            if e.alarm:
                fired = [LAYER_NAMES[l] for l in self.layers if cal[l][i] >= self.layer_thresholds[l]]
                if reasons is not None and i in reasons:
                    e.details["culprit_signal"] = reasons[i]
                who = "; ".join(f"{LAYER_WHY[l]}" for l in self.layers if LAYER_NAMES[l] in fired) or "no single layer alarms, the evidence of several layers adds up"
                culprit = f" (signal {reasons[i]})" if reasons is not None and i in reasons else ""
                e.reason = f"CAN domain alarm in the second ending at {e.t:.2f} s: {who}{culprit}."
        return comb, per

    def score_capture(self, t, ids, dlc, B, name="capture", explain=True):
        """Evidence for every scored 1 s window of one capture. Returns (combined list, {layer name: list})."""
        U = UnitData(name, np.asarray(t, float), np.asarray(ids), np.asarray(dlc), np.asarray(B, np.uint8), np.zeros(len(t), np.int8))
        tab = self.table(U)
        reasons = self.explain(U, tab) if explain else None
        return self.evidence_from_table(tab, sample_prefix=name + "/", reasons=reasons)

    def explain(self, U: UnitData, tab: dict) -> dict:
        """Culprit signal (the continuous signal with the largest windowed CUSUM in the second) of every window where L3c is above its threshold."""
        m, r, _ = self.cfg["l3c"]
        mdl = self.models.l3c[m]
        cal = self.calibrated(tab)["L3c"]
        hot = np.flatnonzero(tab["ok"] & (cal >= self.layer_thresholds["L3c"]))
        if not len(hot):
            return {}
        tm = U.tm
        dec = S.decode_all(U.id, U.B, DBC)
        Gc, _, g0 = make_grid(tm, dec)
        z = P.z_matrix(mdl, Gc)
        cs = np.cumsum(np.vstack([np.zeros((1, z.shape[1])), np.maximum(z - P.CUSUM_K, 0.0)]), axis=0, dtype=np.float64)
        idx = np.arange(1, len(z) + 1)
        w = (cs[idx] - cs[np.maximum(idx - P.L3D_WIN, 0)])
        w[:, mdl.r2 < r] = -1
        gsec = np.floor(g0 + P.GRID_DT * np.arange(len(z))).astype(np.int64)
        out = {}
        for i in hot:
            rows = np.flatnonzero(gsec == tab["sec"][i])
            if len(rows):
                j = np.unravel_index(np.argmax(w[rows]), w[rows].shape)[1]
                out[i] = f"{CAT.cont[j][0]:#x}.{CAT.cont[j][1]}"
        return out

    # ---- ego motion ------------------------------------------------------------------------------
    def motion_estimates(self, t, ids, dlc, B):
        """One MotionEstimate (source "can") per second: unsigned speed from the mean of the four wheel speeds held at the end of the second.
        Needs only the wheel-speed ID (0x6e0). sigma = max(0.3 m/s, 3% of speed) (engineering choice). yaw_rate and displacement are not available from
        this DBC (None). A CAN attacker who rewrites the wheel-speed message controls this value: it is a claim, to be cross-checked in WP6."""
        t = np.asarray(t, float)
        ids = np.asarray(ids)
        tm = np.maximum.accumulate(t)
        rows = np.flatnonzero(ids == WHEELS[0][0])
        if not len(rows):
            return []
        dec = S.decode_all(ids[rows], np.asarray(B, np.uint8)[rows], {WHEELS[0][0]: DBC[WHEELS[0][0]]})
        rr, V = dec[WHEELS[0][0]]
        tw = tm[rows][rr]
        v = np.mean([V[:, k] for _, k in WHEELS], axis=0) * WHEEL_UNIT_MPS
        ends = np.arange(np.ceil(tm[0]) + 1.0, tm[-1] + 1e-9, 1.0)
        pos = np.searchsorted(tw, ends, side="right") - 1
        out = []
        for e, p in zip(ends, pos):
            if p < 0:
                continue
            sp = float(v[p])
            out.append(MotionEstimate(t=float(e), source="can", speed=sp, yaw_rate=None, displacement=None,
                                      sigma=float(max(SPEED_SIGMA_MIN, SPEED_SIGMA_REL * sp))))
        return out

    # ---- persistence ---------------------------------------------------------------------------------
    def save(self, folder):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        pickle.dump({"models": self.models, "cfg": self.cfg, "ecdf_rules": self.ecdf_rules, "calib": self.calib, "combiner": self.combiner,
                     "layer_thresholds": self.layer_thresholds, "budget": self.budget, "schema": SCHEMA_VERSION},
                    open(folder / "domain.pkl", "wb"))
        meta = {"schema": SCHEMA_VERSION, "budget": self.budget, "layers": self.layers, "cfg": self.cfg,
                "layer_thresholds": self.layer_thresholds,
                "combined": {"method": self.combiner.method, "threshold": self.combiner.threshold, "selection": self.combiner.selection},
                "vehicle": "ROAD (anonymised DBC); not transferable to another vehicle without its own clean calibration and DBC"}
        (folder / "domain.json").write_text(json.dumps(meta, indent=1, default=float))

    @classmethod
    def load(cls, folder):
        d = pickle.load(open(Path(folder) / "domain.pkl", "rb"))
        assert d["schema"] == SCHEMA_VERSION
        return cls(d["models"], d["cfg"], d["ecdf_rules"], d["calib"], d["combiner"], d["layer_thresholds"], d["budget"])
