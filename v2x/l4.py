"""WP5 S5: L4 supervised misbehaviour model for V2X, as a v3 Layer (domain "v2x", layer "L4", kind "supervised").

Purpose: learn, from labelled VeReMi attacks, how the plausibility evidence of L1-L3 combines into an attack score. The
model sees ONLY plausibility features produced by the earlier layers (residuals, NIS, CUSUM state, beacon rate, birth density,
trailing-window aggregates of these). It never sees raw position, raw speed, sender id or absolute time: those encode the
simulation, not the attack. Two cheap track descriptors (index of the message in its track, time since the previous message)
are in the table as group T and are ablated in the evaluation (tools/WP5_S5_l4.py).
Features (all causal; track = claimed pseudonym stream; window = last WINDOW messages of the track, current one included):
  M  per message: pos_speed, pos_heading, speed_change, implied_speed, heading_rate, accel_consistency, overlap (L2 raw scores),
                  kf_nis, kf_cusum_hi (L3), rate (L1 beacon rate / 10 Hz), field_violation (L1 field_ranges raw >= 1)
  W  window     : max / mean of nis and pos_speed, max of pos_heading, implied_speed, speed_change, heading_rate, rate, mean of
                  accel_consistency, number of window messages with NIS above the chi2(4) 95% bound
  N  network    : birth_density of the first message of the track (L3 track_birth), carried along the track; is_first
  T  time / id  : track_pos (capped), dt_prev
kf_cusum_lo is NOT a feature (supervisor decision after S4: its false alarms do not transfer to real standing vehicles).
Model: xgboost gradient-boosted trees (hist, CPU), binary attack / genuine. Scores in [0, 1]; Layer.calibrate() maps them to the
empirical CDF of validation genuine scores and fixes the 1% budget threshold like every other layer.
Inputs: unified message table (v2x/schema.py) with whole tracks; a fitted l3.Tracker. Outputs: feature_table(), L4 Layer.
References: Kamel et al., VeReMi Extension (ICC 2020) and F2MD (IEEE TVT 2020); Chen & Guestrin, XGBoost (KDD 2016).
"""
import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.stats import chi2

from common.config import SEED
from common.layer import Layer
from v2x import l1, l2, l3

WINDOW = 10
POS_CAP = 30
NIS_BOUND = float(chi2.ppf(0.95, l3.DIM))

RAW_NAMES = ["pos_speed", "pos_heading", "speed_change", "implied_speed", "heading_rate", "accel_consistency", "overlap",
             "nis", "cusum_hi", "rate"]
M_FEATURES = RAW_NAMES + ["field_violation"]
W_FEATURES = ["w_nis_max", "w_nis_mean", "w_pos_speed_max", "w_pos_speed_mean", "w_pos_heading_max", "w_implied_speed_max",
              "w_speed_change_max", "w_heading_rate_max", "w_rate_max", "w_accel_consistency_mean", "w_n_nis_high"]
N_FEATURES = ["birth_density", "track_birth_density", "is_first"]
T_FEATURES = ["track_pos", "dt_prev"]
FEATURES = M_FEATURES + W_FEATURES + N_FEATURES + T_FEATURES
GROUPS = {"M": M_FEATURES, "W": W_FEATURES, "N": N_FEATURES, "T": T_FEATURES}
MEMORY_FEATURES = ["cusum_hi"] + W_FEATURES              # features that carry the past of the track (class-12 diagnostic)
RATE_BIRTH_FEATURES = ["rate", "w_rate_max"] + N_FEATURES + ["birth_density"]
FORBIDDEN = {"x", "y", "speed", "vx", "vy", "heading", "t", "sender", "pseudo", "track", "msg_id", "label", "attack", "lat", "lon", "rx_x", "rx_y"}
assert not (set(FEATURES) & FORBIDDEN)

XGB_DEFAULT = dict(max_depth=5, min_child_weight=1, learning_rate=0.1, subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0)


def feature_sets():
    """Named feature subsets used by the leakage ablation."""
    a1 = [f for f in FEATURES if f not in T_FEATURES]
    a2 = [f for f in a1 if f not in RATE_BIRTH_FEATURES]
    nomem = [f for f in FEATURES if f not in MEMORY_FEATURES]
    return {"full": list(FEATURES), "A1_no_time_track": a1, "A2_residuals_only": a2, "no_memory": nomem}


def message_scores(df, tracker: "l3.Tracker") -> dict:
    """Raw L1-L3 scores of every message (table order) that feed the features. Whole tracks must be in df."""
    out = {}
    for lay in l2.make_layers():
        if lay.name in ("v2x.pos_speed", "v2x.pos_heading", "v2x.speed_change", "v2x.implied_speed", "v2x.heading_rate",
                        "v2x.accel_consistency", "v2x.overlap"):
            out[lay.name.split(".", 1)[1]] = np.asarray(lay.raw_scores(df), dtype=float)
    run = tracker.run(df)
    out["nis"] = np.asarray(run["nis"], dtype=float)
    out["cusum_hi"] = np.asarray(run["chi"], dtype=float)
    out["rate"] = l1.rate_hz(df) / l1.LIMITS["RATE_MAX_HZ"]
    out["field_raw"] = np.asarray(l1.FieldRanges().raw_scores(df), dtype=float)
    out["birth"] = np.asarray(l3.birth_density(df), dtype=float)
    return out


def _window_agg(v, pos, w, how):
    """Trailing aggregate over the last w rows of the same track; v and pos in track/time order."""
    n = len(v)
    acc = v.astype(float).copy()
    if how == "mean":
        cnt = np.ones(n)
    for k in range(1, w):
        sh = np.zeros(n)
        sh[k:] = v[:n - k]
        ok = pos >= k
        if how == "max":
            acc = np.where(ok, np.maximum(acc, sh), acc)
        elif how == "mean":
            acc = acc + np.where(ok, sh, 0.0)
            cnt = cnt + ok
        elif how == "count":
            acc = acc + np.where(ok, sh, 0.0)
    return acc / cnt if how == "mean" else acc


def feature_table(df, tracker: "l3.Tracker", raw: dict = None) -> pd.DataFrame:
    """All feature columns (FEATURES) plus the raw columns needed by the baseline layers (field_raw, birth), float32, table order."""
    raw = raw if raw is not None else message_scores(df, tracker)
    n = len(df)
    codes = pd.factorize(df["track"])[0]
    t = df["t"].to_numpy(dtype=float)
    order = np.lexsort((t, codes))
    c, ts = codes[order], t[order]
    first = np.ones(n, bool)
    first[1:] = c[1:] != c[:-1]
    idx = np.arange(n)
    start = np.maximum.accumulate(np.where(first, idx, 0))
    pos = idx - start
    S = {k: raw[k][order] for k in RAW_NAMES + ["birth", "field_raw"]}
    f = {k: S[k] for k in RAW_NAMES}
    f["field_violation"] = (S["field_raw"] >= 1.0).astype(float)
    nis_high = (S["nis"] > NIS_BOUND).astype(float)
    f["w_nis_max"] = _window_agg(S["nis"], pos, WINDOW, "max")
    f["w_nis_mean"] = _window_agg(S["nis"], pos, WINDOW, "mean")
    f["w_pos_speed_max"] = _window_agg(S["pos_speed"], pos, WINDOW, "max")
    f["w_pos_speed_mean"] = _window_agg(S["pos_speed"], pos, WINDOW, "mean")
    f["w_pos_heading_max"] = _window_agg(S["pos_heading"], pos, WINDOW, "max")
    f["w_implied_speed_max"] = _window_agg(S["implied_speed"], pos, WINDOW, "max")
    f["w_speed_change_max"] = _window_agg(S["speed_change"], pos, WINDOW, "max")
    f["w_heading_rate_max"] = _window_agg(S["heading_rate"], pos, WINDOW, "max")
    f["w_rate_max"] = _window_agg(S["rate"], pos, WINDOW, "max")
    f["w_accel_consistency_mean"] = _window_agg(S["accel_consistency"], pos, WINDOW, "mean")
    f["w_n_nis_high"] = _window_agg(nis_high, pos, WINDOW, "count")
    f["birth_density"] = S["birth"]
    f["track_birth_density"] = S["birth"][start]
    f["is_first"] = first.astype(float)
    f["track_pos"] = np.minimum(pos, POS_CAP).astype(float)
    dt = np.zeros(n)
    dt[1:] = np.round(np.diff(ts), 3)
    f["dt_prev"] = np.where(first, 0.0, dt)
    f["field_raw"] = S["field_raw"]
    out = np.empty((n, len(f)), dtype=np.float32)
    names = list(f)
    for j, k in enumerate(names):
        out[order, j] = np.nan_to_num(f[k], nan=0.0, posinf=1e9, neginf=0.0).astype(np.float32)
    return pd.DataFrame(out, columns=names)


# ----------------------------------------------------------------------------------------------------------------
class GBModel:
    """xgboost wrapper: fit on a feature subset, predict P(attack), gain importance."""

    def __init__(self, features, params=None, n_estimators=None, seed=SEED):
        self.features = list(features)
        self.params = dict(XGB_DEFAULT, **(params or {}))
        self.n_estimators = n_estimators
        self.seed = seed
        self.model = None
        self.best_iteration = None

    def _make(self, n_estimators, early):
        return xgb.XGBClassifier(n_estimators=n_estimators, tree_method="hist", n_jobs=4, random_state=self.seed,
                                 eval_metric="aucpr", early_stopping_rounds=early, **self.params)

    def fit(self, X, y, X_val=None, y_val=None, max_estimators=600, patience=30):
        Xa = np.asarray(X[self.features], dtype=np.float32)
        if X_val is not None:
            self.model = self._make(max_estimators, patience)
            self.model.fit(Xa, np.asarray(y, int), eval_set=[(np.asarray(X_val[self.features], dtype=np.float32), np.asarray(y_val, int))], verbose=False)
            self.best_iteration = int(self.model.best_iteration)
            self.n_estimators = self.best_iteration + 1
        else:
            self.model = self._make(self.n_estimators or 100, None)
            self.model.fit(Xa, np.asarray(y, int), verbose=False)
        return self

    def predict(self, X):
        return self.model.predict_proba(np.asarray(X[self.features], dtype=np.float32))[:, 1]

    def importance(self):
        g = self.model.get_booster().get_score(importance_type="total_gain")
        tot = sum(g.values()) or 1.0
        names = self.model.get_booster().feature_names
        out = {}
        for k, v in g.items():
            out[self.features[int(k[1:])] if k.startswith("f") and k[1:].isdigit() else k] = v / tot
        if names is None:
            pass
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))


class L4(Layer):
    """v3 Layer around a fitted GBModel: raw score = P(attack) from the plausibility features of the frame."""
    domain, name, kind, layer_id = "v2x", "v2x.l4_gb", "supervised", "L4"
    needs_attack_data = True
    physical = False

    def __init__(self, model: GBModel, tracker: "l3.Tracker"):
        super().__init__()
        self.gb, self.tracker = model, tracker

    def raw_scores(self, df):
        return self.gb.predict(feature_table(df, self.tracker))

    def reasons(self, df, raw, alarm):
        return [f"plausibility evidence of the beacon stream looks like a learned attack pattern (score {r:.2f})" for r in raw]
