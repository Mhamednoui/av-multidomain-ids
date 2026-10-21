"""WP5 S4: L3 per-sender Kalman tracker with innovation tests, as v3 Layers (domain "v2x", layer "L3", kind "normal_model").

Purpose: a normal-motion model of every sender (track = claimed pseudonym stream). Each beacon is compared with what the
filter predicted from the earlier beacons of the same track; the innovation is tested with the normalised innovation squared
(NIS, chi-square) per message and with per-track CUSUMs on the NIS. No attack data is used anywhere.

Model (constant velocity, white-noise acceleration; state s = [x, y, vx, vy], measurement z = [x, y, vx, vy], H = I):
  predict   s- = F s,   F = [[I, dt I], [0, I]]
            P- = F P F^T + Q,   Q = sa^2 [[dt^3/3 I, dt^2/2 I], [dt^2/2 I, dt I]]
  innovate  nu = z - s-,  S = P- + R,  R = diag(sp^2, sp^2, sv^2, sv^2),  NIS = nu^T S^-1 nu   (~ chi2(4) if the model is right)
  update    K = P- S^-1,  s = s- + K nu,  P = (I - K) P-
  init      at the first message of a segment: s = z, P = R; that message is not scored (raw 0).
A segment restarts when dt > DT_MAX (5 s, the same gap rule as L2) or dt <= 0, or when the velocity of the message is undefined.
(sp, sv, sa) are fitted by maximum likelihood of the innovations, 0.5 (ln det S + NIS) summed over genuine TRAIN tracks only
(fit_noise); floors SP_MIN, SV_MIN. The velocity measurement is speed x unit heading vector (VeReMi: the spd vector).

Layers (raw scores, higher = more attack-like):
  KfNis       v2x.kf_nis       NIS of the message (upper tail of the chi-square test).
  KfCusumHi   v2x.kf_cusum_hi  C_k = max(0, C_(k-1) + NIS_k - K_HI) per segment, K_HI = chi2(4) 95% quantile: sustained inconsistency.
  KfCusumLo   v2x.kf_cusum_lo  C_k = max(0, C_(k-1) + K_LO - NIS_k) per segment, K_LO = chi2(4) 25% quantile: "too consistent"
                               tracks (position and velocity repeated without measurement noise: frozen / verbatim streams).
  TrackBirth  v2x.track_birth  first message of a track: number of other track births within +-300 m (Chebyshev, claimed positions)
                               in the last 10 s; 0 for other messages. Needs no receiver position. Detects pseudonym churn
                               (Sybil with a fresh pseudonym per message) that one-message tracks hide from the filter.
Causal: the score of a message uses only earlier messages of its own track (births: earlier births of any track). A batch must
contain whole tracks (and for births the neighbouring traffic). Thresholds: validation genuine, 1% budget, tie-safe (calibrate_masked).
References: Bar-Shalom, Li, Kirubarajan, Estimation with Applications to Tracking and Navigation (2001), ch. 5 (NIS consistency test),
ch. 11; Page (1954) CUSUM; Kamel et al., VeReMi Extension (ICC 2020).
"""
import json
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.spatial import cKDTree
from scipy.stats import chi2

from common.config import SEED
from v2x.l2 import _L2

DT_MAX = 5.0
DIM = 4
K_HI = float(chi2.ppf(0.95, DIM))        # 9.488
K_LO = float(chi2.ppf(0.25, DIM))        # 1.923
CHI2_95 = K_HI
CHI2_05 = float(chi2.ppf(0.05, DIM))     # 0.711
SP_MIN, SV_MIN, SA_MIN = 0.05, 0.02, 0.01
BIRTH_RADIUS_M = 300.0
BIRTH_WINDOW_S = 10.0


@dataclass
class KalmanParams:
    sp: float = 1.0       # position measurement sigma (m)
    sv: float = 0.1       # velocity measurement sigma (m/s)
    sa: float = 1.0       # acceleration process noise (m/s^2 per sqrt(s))

    def to_dict(self):
        return asdict(self)


def _col(df, name, default=np.nan):
    return df[name].to_numpy(dtype=float) if name in df.columns else np.full(len(df), default)


def measurements(df):
    """z = [x, y, vx, vy] per row and a flag velocity-defined."""
    x, y = _col(df, "x"), _col(df, "y")
    vx, vy = _col(df, "vx"), _col(df, "vy")
    sp, h = _col(df, "speed"), _col(df, "heading")
    bad = ~(np.isfinite(vx) & np.isfinite(vy))
    vx = np.where(bad, sp * np.cos(h), vx)
    vy = np.where(bad, sp * np.sin(h), vy)
    ok = np.isfinite(vx) & np.isfinite(vy) & np.isfinite(x) & np.isfinite(y)
    return np.stack([x, y, np.where(ok, vx, 0.0), np.where(ok, vy, 0.0)], 1), ok


class Segments:
    """Rows sorted by (track, t), cut into filter segments."""

    def __init__(self, df):
        n = len(df)
        codes = pd.factorize(df["track"])[0]
        t = df["t"].to_numpy(dtype=float)
        self.order = np.lexsort((t, codes))
        o = self.order
        self.n = n
        z, ok = measurements(df)
        self.z, self.ok = z[o], ok[o]
        c, ts = codes[o], t[o]
        dt = np.zeros(n)
        dt[1:] = np.round(np.diff(ts), 3)
        new = np.ones(n, bool)
        new[1:] = (c[1:] != c[:-1]) | (dt[1:] > DT_MAX) | (dt[1:] <= 0)
        new |= ~self.ok
        self.dt = dt
        self.seg = np.cumsum(new) - 1
        self.nseg = int(self.seg[-1] + 1) if n else 0
        starts = np.flatnonzero(new)
        self.pos = np.arange(n) - starts[self.seg] if n else np.zeros(0, int)
        self.starts = starts
        self.maxlen = int(self.pos.max() + 1) if n else 0
        o2 = np.argsort(self.pos, kind="stable")
        self.by_step = o2
        self.step_bounds = np.searchsorted(self.pos[o2], np.arange(self.maxlen + 1))


def _Q(dt, sa):
    m = len(dt)
    Q = np.zeros((m, 4, 4))
    a, b, c = sa ** 2 * dt ** 3 / 3, sa ** 2 * dt ** 2 / 2, sa ** 2 * dt
    for i in (0, 1):
        Q[:, i, i], Q[:, i, i + 2], Q[:, i + 2, i], Q[:, i + 2, i + 2] = a, b, b, c
    return Q


def run_filter(seg: Segments, p: KalmanParams, cusum=False, loglik=False):
    """Batched Kalman filter over all segments (step j of all segments at once). Returns arrays in SORTED row order:
    nis (0 where not scored), scored (bool), and optionally cusum_hi, cusum_lo, and the summed log-likelihood."""
    n = seg.n
    R = np.diag([p.sp ** 2, p.sp ** 2, p.sv ** 2, p.sv ** 2])
    nis = np.zeros(n)
    scored = np.zeros(n, bool)
    chi = np.zeros(n)
    clo = np.zeros(n)
    ll = 0.0
    if n == 0:
        return nis, scored, chi, clo, ll
    xs = np.zeros((seg.nseg, 4))
    Ps = np.zeros((seg.nseg, 4, 4))
    ch = np.zeros(seg.nseg)
    cl = np.zeros(seg.nseg)
    st = seg.starts
    xs[:] = seg.z[st]
    Ps[:] = R
    eye = np.eye(4)
    for j in range(1, seg.maxlen):
        rows = seg.by_step[seg.step_bounds[j]:seg.step_bounds[j + 1]]
        if not len(rows):
            continue
        s = seg.seg[rows]
        dt = seg.dt[rows]
        F = np.broadcast_to(eye, (len(rows), 4, 4)).copy()
        F[:, 0, 2] = dt
        F[:, 1, 3] = dt
        xm = np.einsum("mij,mj->mi", F, xs[s])
        Pm = F @ Ps[s] @ F.transpose(0, 2, 1) + _Q(dt, p.sa)
        S = Pm + R
        nu = seg.z[rows] - xm
        Si = np.linalg.inv(S)
        v = np.einsum("mi,mij,mj->m", nu, Si, nu)
        K = Pm @ Si
        xs[s] = xm + np.einsum("mij,mj->mi", K, nu)
        Pn = (eye - K) @ Pm
        Ps[s] = 0.5 * (Pn + Pn.transpose(0, 2, 1))
        nis[rows] = v
        scored[rows] = True
        if cusum:
            ch[s] = np.maximum(0.0, ch[s] + v - K_HI)
            cl[s] = np.maximum(0.0, cl[s] + K_LO - v)
            chi[rows], clo[rows] = ch[s], cl[s]
        if loglik:
            ll += float(0.5 * (np.linalg.slogdet(S)[1] + v).sum())
    return nis, scored, chi, clo, ll


def neg_loglik(theta, seg: Segments):
    p = KalmanParams(max(np.exp(theta[0]), SP_MIN), max(np.exp(theta[1]), SV_MIN), max(np.exp(theta[2]), SA_MIN))
    _, scored, _, _, ll = run_filter(seg, p, loglik=True)
    return ll / max(int(scored.sum()), 1)


def fit_noise(genuine_train: pd.DataFrame, max_tracks=800, max_msgs=120, seed=SEED, init=None):
    """Maximum-likelihood (sp, sv, sa) on GENUINE TRAIN rows only (the caller passes nothing else; this function never sees labels,
    validation, test or attack rows). Subsample: `max_tracks` random tracks with >= 5 messages, first `max_msgs` messages each.
    Returns (KalmanParams, info dict)."""
    rng = np.random.RandomState(seed)
    ln = genuine_train.groupby("track").size()
    cand = np.array(sorted(ln.index[ln >= 5]))
    pick = set(rng.choice(cand, min(max_tracks, len(cand)), replace=False).tolist())
    sub = genuine_train[genuine_train["track"].isin(pick)].sort_values(["track", "t"], kind="stable")
    sub = sub[sub.groupby("track").cumcount() < max_msgs]
    seg = Segments(sub)
    x0 = np.log([init.sp, init.sv, init.sa]) if init else np.log([1.0, 0.1, 1.0])
    r = minimize(neg_loglik, x0, args=(seg,), method="Nelder-Mead", options={"xatol": 1e-3, "fatol": 1e-5, "maxiter": 200})
    th = r.x
    p = KalmanParams(float(max(np.exp(th[0]), SP_MIN)), float(max(np.exp(th[1]), SV_MIN)), float(max(np.exp(th[2]), SA_MIN)))
    info = {"n_tracks": len(pick), "n_messages": int(len(sub)), "n_scored": int(Segments(sub).n - Segments(sub).nseg),
            "neg_loglik_per_message": float(r.fun), "nfev": int(r.nfev), "converged": bool(r.success),
            "senders_used": sorted(set(sub["sender"].astype(str))) if "sender" in sub.columns else None}
    return p, info


def consistency(nis, scored):
    """NIS consistency on genuine data: mean vs DIM, fraction above the chi2 95% bound (expected 5%), below the 5% bound (expected 5%)."""
    v = nis[scored]
    if not len(v):
        return {"n": 0}
    return {"n": int(len(v)), "dim": DIM, "nis_mean": float(v.mean()), "nis_median": float(np.median(v)),
            "expected_median": float(chi2.ppf(0.5, DIM)), "frac_above_chi2_95": float((v > CHI2_95).mean()),
            "frac_below_chi2_05": float((v < CHI2_05).mean()), "q99": float(np.quantile(v, 0.99)),
            "chi2_q99": float(chi2.ppf(0.99, DIM))}


class Tracker:
    """Shared by the four layers: holds the fitted parameters and caches the last filter run (keyed on the table object)."""

    def __init__(self, params: KalmanParams = None):
        self.params = params or KalmanParams()
        self._key, self._df, self._val = None, None, None

    def fit(self, genuine_train):
        self.params, info = fit_noise(genuine_train)
        self._key = None
        return info

    def run(self, df):
        key = (id(df), len(df))
        if self._key != key:
            seg = Segments(df)
            nis, scored, chi, clo, _ = run_filter(seg, self.params, cusum=True)
            out = {k: np.empty(len(df)) for k in ("nis", "chi", "clo")}
            out["scored"] = np.empty(len(df), bool)
            for k, v in (("nis", nis), ("chi", chi), ("clo", clo), ("scored", scored)):
                out[k][seg.order] = v
            self._key, self._df, self._val = key, df, out      # keep df alive so id() stays valid
        return self._val

    def save(self, path):
        json.dump(self.params.to_dict(), open(path, "w"))


class _L3(_L2):
    domain, kind, layer_id = "v2x", "normal_model", "L3"
    physical = False
    needs_attack_data = False

    def __init__(self, tracker: Tracker):
        super().__init__()
        self.tracker = tracker

    def reasons(self, df, raw, alarm):
        return [f"{self.name}: track inconsistent with its own earlier beacons (score {r:.1f})" for r in raw]


class KfNis(_L3):
    name = "v2x.kf_nis"

    def raw_scores(self, df):
        return self.tracker.run(df)["nis"]

    def reasons(self, df, raw, alarm):
        return [f"beacon differs from the track prediction (NIS {r:.0f}, a normal sender stays near {DIM})" for r in raw]


class KfCusumHi(_L3):
    name = "v2x.kf_cusum_hi"

    def raw_scores(self, df):
        return self.tracker.run(df)["chi"]

    def reasons(self, df, raw, alarm):
        return [f"track keeps disagreeing with its own motion model (CUSUM {r:.0f})" for r in raw]


class KfCusumLo(_L3):
    name = "v2x.kf_cusum_lo"

    def raw_scores(self, df):
        return self.tracker.run(df)["clo"]

    def reasons(self, df, raw, alarm):
        return [f"track is suspiciously exact: no measurement noise for several beacons (CUSUM {r:.1f})" for r in raw]


def birth_density(df, radius=BIRTH_RADIUS_M, window=BIRTH_WINDOW_S):
    """Per row: for the first message of each track, number of OTHER births (first messages of other tracks) with claimed position within
    `radius` m (Chebyshev) and time in [t - window, t]; 0 for other rows. Causal in time (later births are not counted)."""
    n = len(df)
    out = np.zeros(n)
    if n == 0:
        return out
    codes = pd.factorize(df["track"])[0]
    t = df["t"].to_numpy(dtype=float)
    o = np.lexsort((t, codes))
    first = np.zeros(n, bool)
    first[o[0]] = True
    cs = codes[o]
    first[o[1:][cs[1:] != cs[:-1]]] = True
    idx = np.flatnonzero(first)
    if len(idx) < 2:
        return out
    x, y = df["x"].to_numpy(dtype=float)[idx], df["y"].to_numpy(dtype=float)[idx]
    tb = t[idx]
    sc = radius / (window / 2)                      # time axis scaled so that +-window/2 equals the radius
    tree = cKDTree(np.stack([x, y, tb * sc], 1))
    centres = np.stack([x, y, (tb - window / 2) * sc], 1)
    cnt = tree.query_ball_point(centres, r=radius, p=np.inf, return_length=True)
    out[idx] = np.maximum(cnt - 1, 0)               # the birth itself is inside its own window
    return out


class TrackBirth(_L3):
    name = "v2x.track_birth"

    def raw_scores(self, df):
        return birth_density(df)

    def reasons(self, df, raw, alarm):
        return [f"{r:.0f} other new identities appeared within 300 m in the last 10 s" for r in raw]


def make_layers(tracker: Tracker):
    return [KfNis(tracker), KfCusumHi(tracker), KfCusumLo(tracker), TrackBirth(tracker)]
