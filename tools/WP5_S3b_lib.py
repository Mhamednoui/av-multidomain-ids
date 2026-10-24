"""WP5 S3b shared setup: V2AIX tables per environment and split, the frozen domain (variant A), the V2AIX-validation re-calibration (variant B), the receiver-position
layers, the alarm configurations and k val per configuration. Everything is fitted on the VALIDATION recordings of the environment; test is only scored.
Used by WP5_S3b_clean.py and WP5_S3b_inject.py (python -I, from codes_v3/)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd

from system.v2x_runner import V2XPhysicsDomain
from v2x import l1, l3, l_rx, v2aix
from v2x import v2aix_eval as ev

OUT = ROOT / "results" / "WP5"
FROZEN = ROOT / "results" / "WP7" / "frozen_v2x"
ENVS = ["Mobile", "Stationary"]
MIN_LOC_VAL = 300          # per-location range threshold only where the validation has at least this many messages with a receiver position
# max-combined configurations (threshold = tie-safe 1% of all genuine validation messages); the appearance layer has its own population and its own threshold:
# "appear" = its own alarm, "rx" = range OR appear, "physics+rx" = (max of the 12 checks and the range) OR appear.
CONFIGS = {"L1": ev.L1_N, "L2": ev.L2_N, "L3": ev.L3_N, "physics": ev.LAYER_NAMES, "physics+range": ev.LAYER_NAMES + ["v2x.acceptance_range"]}


def load_env(part: str, env: str, sp=None) -> pd.DataFrame:
    sp = sp or json.loads((OUT / "splits_v2aix.json").read_text())
    recs = [r for r in sp[part] if r.startswith(env + "/")]
    df = v2aix.load_all(recordings=recs)
    df["env"] = env
    df["loc"] = df["recording"].map(v2aix.stratum_of)
    return df.sort_values(["recording", "track", "t"], kind="stable").reset_index(drop=True)


class Setup:
    def __init__(self, env: str):
        self.env = env
        self.sp = json.loads((OUT / "splits_v2aix.json").read_text())
        self.dom = V2XPhysicsDomain.load(FROZEN)
        self.tracker = l3.Tracker(l3.KalmanParams(**self.dom.tracker.params.to_dict()))
        self.val = load_env("val", env, self.sp)
        self.raw_val = ev.raws(self.tracker, self.val)
        g = np.ones(len(self.val), bool)
        self.A = ev.Calib.frozen(self.dom)
        self.B = ev.Calib.fit(self.raw_val, g)
        self.fresh = l1.Freshness().calibrate(self.val, 0.01)      # not in the frozen VeReMi stack (VeReMi has no message age); V2AIX has age_s
        self.range = l_rx.AcceptanceRange().calibrate_fit(self.val, g)
        self.appear = l_rx.AppearanceData().calibrate_fit(self.val, g)
        self.range_loc = {}
        for loc, h in self.val.groupby("loc"):
            if np.isfinite(h["rx_x"]).sum() >= MIN_LOC_VAL:
                idx = h.index.to_numpy()
                lay = l_rx.AcceptanceRange().calibrate_fit(h, np.ones(len(h), bool))
                self.range_loc[loc] = lay
        cal_val = self.cal_all(self.val, self.raw_val)
        self.cfg_thr = {k: ev.group_threshold(cal_val, names, g) for k, names in CONFIGS.items()}
        alarms_val = self.alarms(self.val, cal_val)
        self.k_val = {}
        for name, a in alarms_val.items():
            self.k_val[name] = ev.k_for_budget(ev.sender_counts(self.val, a)["n_alarm"])

    def cal_all(self, df, raw):
        """Calibrated (variant B) scores of the 12 checks + the two receiver layers."""
        cal = self.B.calibrated(raw)
        cal["v2x.acceptance_range"] = self.range.calibrated(df)
        cal["v2x.appearance_data"] = self.appear.calibrated(df)
        return cal

    def _fresh_alarm(self, df):
        return self.fresh.calibrator.transform(self.fresh.raw_scores(df)) >= self.fresh.threshold

    def range_loc_alarm(self, df):
        a = self.range.alarms(df)
        for loc, lay in self.range_loc.items():
            m = (df["loc"] == loc).to_numpy()
            if m.any():
                a[m] = lay.alarms(df[m])
        return a

    def alarms(self, df, cal) -> dict:
        """Boolean alarm arrays of the configurations at the V2AIX-validation thresholds (variant B)."""
        out = {k: ev.Calib.combined(cal, names) >= self.cfg_thr[k] for k, names in CONFIGS.items()}
        out["range"] = self.range.alarms(df)              # own population: 1% of the genuine validation messages that have a receiver position
        out["range_loc"] = self.range_loc_alarm(df)
        out["appear"] = self.appear.alarms(df)
        out["fresh"] = self._fresh_alarm(df)
        out["physics+fresh"] = out["physics"] | out["fresh"]
        out["rx"] = out["range"] | out["appear"]
        out["physics+rx"] = out["physics+range"] | out["appear"]
        return out

    def alarms_A(self, df, raw):
        cal = self.A.calibrated(raw)
        return self.A.alarm(cal), self.A.layer_alarms(cal)

    def score(self, df):
        """Everything needed to judge a table: raw, B calibrated, B alarms, A alarms (combined + per layer), B per-layer alarms."""
        raw = ev.raws(self.tracker, df)
        cal = self.cal_all(df, raw)
        al = self.alarms(df, cal)
        aA, lA = self.alarms_A(df, raw)
        al["A_physics"] = aA
        return {"raw": raw, "cal": cal, "alarm": al, "A_layers": lA, "B_layers": self.B.layer_alarms(cal)}
