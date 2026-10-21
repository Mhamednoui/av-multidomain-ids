"""WP2 S3: L2a ECU clock-skew fingerprinting for CAN (Cho & Shin, CIDS, USENIX Security 2016), as a v3 Layer.

Idea: every ECU sends a periodic ID with its own oscillator, so the receive times of one ID drift linearly with a
fixed skew. A masquerade (same ID and period sent by another transmitter) changes that slope / its noise.
Per periodic ID, streaming and causal, gaps g = frames.dt_clipped to the previous frame of the same ID (the sign of
dt is never used), clipped to 3 T:
  batch of N gaps, c_j = sum_{i<=j}(g_i - mu_T), offset O_k = mean_j c_j, accumulated offset A_k = sum_m O_m
  ("drift" form: mu_T = calibrated mean period T; "paper" form: mu_T = mean gap of the batch and |O| accumulated),
  x_k = elapsed time at the batch end; skew S_k by scalar recursive least squares without intercept, A_k = S x_k:
    K = P x / (lam + x^2 P);  S <- S + K (A_k - S x);  P <- (P - K x P) / lam
  identification error e_k = A_k - S_{k-1} x_k ("acc") or (A_k - A_{k-1}) - S_{k-1} (x_k - x_{k-1}) ("inc"),
  z_k = (e_k - median_i) / (1.4826 MAD_i) (clean calibration traffic), two-sided CUSUM on clip(z, +-10):
    C+ <- max(0, C+ + z - kappa),  C- <- max(0, C- - z - kappa),  score = max(C+, C-).
The first W batches of an ID in a capture are not scored (RLS warm-up). Frame score = CUSUM state after the last
closed batch of its ID; window score = max over the window (can.l1.window_reduce).
Inputs: feature dicts of can.l1.make_features (id, dt_id), a can.l1.Profile (periodic IDs and medians), clean frames.
Outputs: float32 frame scores; SkewProfile (to_dict). Needs no attack data. Numba kernel (numba 0.60 is in the tf env).
References: Cho & Shin 2016 (CIDS); Sagong et al. 2018 and Tian et al. 2018 discuss weaknesses of skew fingerprinting.
"""
import numpy as np
from numba import njit

from can.l1 import CanRule, Profile

LAM, KAPPA, ZCLIP, WARMUP, GAP_CAP = 0.99, 1.0, 10.0, 10, 3.0
MIN_STAT_BATCHES = 20
SCALE_Q, SCALE_FLOOR = 0.99, 2.0
# (form, N, error mode): form 0 = drift (mu_T = T), 1 = paper (batch mean, |O|); error 0 = acc, 1 = inc
BETA, BURN, SD_FLOOR, WINSOR = 0.98, 10, 0.5, 4.0     # local baseline (norm = 1): EWMA memory, burn-in batches, ...
VARIANTS = [(0, 20, 0, 0), (0, 50, 0, 0), (1, 20, 0, 0), (1, 50, 0, 0), (0, 20, 1, 0), (0, 50, 1, 0), (1, 20, 1, 0),
            (1, 50, 1, 0)]
VARIANTS += [(f, n, e, 1) for f, n, e, _ in VARIANTS]     # + the same with the local baseline
VARIANT_NAMES = [f"{'drift' if f == 0 else 'paper'}_N{n}_{'acc' if e == 0 else 'inc'}{'_loc' if m else ''}"
                 for f, n, e, m in VARIANTS]


@njit(cache=True)
def _kernel(ids_s, g_s, pidx, T, mu, sig, scale, N, lam, kappa, zclip, warm, form, errmode, norm,
            out_score, bz, blast, bprof, bstat):
    n = len(ids_s)
    nb = 0
    i = 0
    while i < n:
        j = i
        while j < n and ids_s[j] == ids_s[i]:
            j += 1
        p = pidx[i]
        if p >= 0:
            Tp, m, s, sc = T[p], mu[p], sig[p], scale[p]
            cap = GAP_CAP * Tp
            cnt, k = 0, 0
            sw, sg = 0.0, 0.0
            A, x, xprev, yprev = 0.0, 0.0, 0.0, 0.0
            S, P = 0.0, 1.0e6
            cp, cn, stat = 0.0, 0.0, 0.0
            nloc, mw, m2, me, ve, vb = 0, 0.0, 0.0, 0.0, 0.0, 0.0
            for q in range(i + 1, j):
                g = g_s[q]
                if g != g:
                    g = Tp
                if g > cap:
                    g = cap
                cnt += 1
                sw += g * (N - cnt + 1) / N
                sg += g
                out_score[q] = stat / sc
                if cnt == N:
                    if form == 0:
                        O = sw - Tp * (N + 1) / 2.0
                        A += O
                    else:
                        O = sw - (sg / N) * (N + 1) / 2.0
                        A += abs(O)
                    x += sg
                    if errmode == 0:
                        e = A - S * x
                    else:
                        e = (A - yprev) - S * (x - xprev)
                    kg = P * x / (lam + x * x * P)
                    S += kg * (A - S * x)
                    P = (P - kg * x * P) / lam
                    yprev, xprev = A, x
                    ok = k >= warm
                    z = 0.0
                    if ok and norm == 1:
                        if nloc < BURN:
                            nloc += 1
                            d = e - mw
                            mw += d / nloc
                            m2 += d * (e - mw)
                            if nloc == BURN:
                                me, ve = mw, m2 / (BURN - 1)
                                vb = ve
                            ok = False
                        else:
                            sd = max(np.sqrt(ve), SD_FLOOR * np.sqrt(vb), 1e-12)
                            z = (e - me) / sd
                            ec = min(max(e, me - WINSOR * sd), me + WINSOR * sd)
                            me += (1.0 - BETA) * (ec - me)
                            ve = BETA * ve + (1.0 - BETA) * (ec - me) ** 2
                    elif ok:
                        z = (e - m) / s
                    if ok:
                        bz[nb] = z
                        blast[nb] = q
                        bprof[nb] = p
                        bstat[nb] = 0.0
                        nb += 1
                        zc = min(max(z, -zclip), zclip)
                        cp = max(0.0, cp + zc - kappa)
                        cn = max(0.0, cn - zc - kappa)
                        stat = max(cp, cn)
                        bstat[nb - 1] = stat
                    out_score[q] = stat / sc
                    cnt, sw, sg = 0, 0.0, 0.0
                    k += 1
        i = j
    return nb


class SkewProfile:
    """Per-vehicle clock-skew calibration of the periodic IDs (T, median and MAD of the identification error)."""

    def __init__(self, variant: int = 0):
        self.variant = variant
        self.ids = np.zeros(0, np.int64)
        self.T = np.zeros(0)
        self.mu = np.zeros(0)
        self.sig = np.ones(0)
        self.scale = np.ones(0)
        self.n_batches = np.zeros(0, np.int64)
        self.scored = np.zeros(0, bool)

    @property
    def form_N_err(self):
        return VARIANTS[self.variant]

    def lookup(self, ids):
        if len(self.ids) == 0:
            return np.full(len(ids), -1, np.int64)
        pos = np.minimum(np.searchsorted(self.ids, ids), len(self.ids) - 1)
        ok = (self.ids[pos] == ids) & self.scored[pos]
        return np.where(ok, pos, -1)

    def to_dict(self):
        return {"variant": VARIANT_NAMES[self.variant], "ids": self.ids.tolist(), "T": self.T.tolist(),
                "mu": self.mu.tolist(), "sig": self.sig.tolist(), "scale": self.scale.tolist(), "n_batches": self.n_batches.tolist(),
                "scored": self.scored.tolist()}

    def summary(self):
        return {"variant": VARIANT_NAMES[self.variant], "periodic_ids": int(len(self.ids)),
                "scored_ids": int(self.scored.sum())}


def run_pass(F: dict, prof: SkewProfile, mu=None, sig=None, scale=None, with_stat=False):
    """One causal pass over a capture. Returns (frame scores float32 in recorded order, batch z, batch last-frame
    position in the ID-sorted order, batch profile index, sort order)."""
    form, N, err, norm = prof.form_N_err
    n = len(F["id"])
    order = np.argsort(F["id"], kind="stable")
    ids_s = np.ascontiguousarray(F["id"][order])
    g_s = np.ascontiguousarray(F["dt_id"][order].astype(np.float64))
    pidx = prof.lookup(ids_s)
    out = np.zeros(n, np.float32)
    nbmax = n // N + len(prof.ids) + 1
    bz, bl, bp = np.zeros(nbmax), np.zeros(nbmax, np.int64), np.zeros(nbmax, np.int64)
    mu = prof.mu if mu is None else mu
    sig = prof.sig if sig is None else sig
    scale = prof.scale if scale is None else scale
    bs = np.zeros(nbmax)
    if len(prof.ids) == 0:
        return (out, bz[:0], bl[:0], bp[:0], order) + ((bs[:0],) if with_stat else ())
    out_s = np.zeros(n, np.float32)
    nb = _kernel(ids_s, g_s, pidx, prof.T, mu, sig, scale, N, LAM, KAPPA, ZCLIP, WARMUP, form, err, norm, out_s, bz, bl, bp, bs)
    out[order] = out_s
    return (out, bz[:nb], bl[:nb], bp[:nb], order) + ((bs[:nb],) if with_stat else ())


class SkewBuilder:
    """Accumulates clean traffic of several captures: mean periods first (`add_periods`), then error statistics."""

    def __init__(self, l1_profile: Profile):
        P = l1_profile
        sel = np.flatnonzero(P.periodic)
        self.ids, self.p = P.ids[sel], P.p[sel]
        self.gsum = np.zeros(len(sel))
        self.gcnt = np.zeros(len(sel))
        self.z = [[] for _ in sel]
        self.st = [[] for _ in sel]

    def add_periods(self, F: dict, mask):
        """Mean period per periodic ID from the masked frames (gaps clipped at 3 x median)."""
        if len(self.ids) == 0:
            return self
        ids, g = F["id"][mask], F["dt_id"][mask].astype(np.float64)
        pos = np.minimum(np.searchsorted(self.ids, ids), len(self.ids) - 1)
        ok = (self.ids[pos] == ids) & np.isfinite(g)
        g = np.minimum(g[ok], GAP_CAP * self.p[pos[ok]])
        self.gsum += np.bincount(pos[ok], g, minlength=len(self.ids))
        self.gcnt += np.bincount(pos[ok], minlength=len(self.ids))
        return self

    def prof(self, variant: int) -> SkewProfile:
        S = SkewProfile(variant)
        S.ids = self.ids
        S.T = np.where(self.gcnt > 0, self.gsum / np.maximum(self.gcnt, 1), self.p)
        S.mu, S.sig, S.scale = np.zeros(len(self.ids)), np.ones(len(self.ids)), np.ones(len(self.ids))
        S.scored = np.ones(len(self.ids), bool)      # all periodic IDs run during the statistics pass
        S.n_batches = np.zeros(len(self.ids), np.int64)
        return S

    def add_errors(self, S: SkewProfile, F: dict, mask):
        """Run the filter (mu = 0, sig = 1) and keep the errors of the batches lying wholly in `mask`."""
        if len(self.ids) == 0:
            return self
        _, bz, bl, bp, order = run_pass(F, S, np.zeros(len(S.ids)), np.ones(len(S.ids)))
        N = S.form_N_err[1]
        cs = np.concatenate(([0], np.cumsum(mask[order].astype(np.int64))))
        full = cs[bl + 1] - cs[np.maximum(bl - N, 0)] == np.minimum(bl + 1, N + 1)
        for k in np.unique(bp[full]):
            self.z[int(k)].append(bz[full & (bp == k)])
        return self

    def add_stats(self, S: SkewProfile, F: dict, mask):
        """Second pass with the calibrated mu / sig: CUSUM state at the end of every batch lying wholly in `mask`."""
        if len(self.ids) == 0 or not S.scored.any():
            return self
        _, _, bl, bp, order, bs = run_pass(F, S, S.mu, S.sig, np.ones(len(S.ids)), with_stat=True)
        N = S.form_N_err[1]
        cs = np.concatenate(([0], np.cumsum(mask[order].astype(np.int64))))
        full = cs[bl + 1] - cs[np.maximum(bl - N, 0)] == np.minimum(bl + 1, N + 1)
        for k in np.unique(bp[full]):
            self.st[int(k)].append(bs[full & (bp == k)])
        return self

    def finish_scale(self, S: SkewProfile) -> SkewProfile:
        """Per-ID scale = SCALE_Q quantile of the clean CUSUM state (floor SCALE_FLOOR)."""
        for k in range(len(self.ids)):
            st = np.concatenate(self.st[k]) if self.st[k] else np.zeros(0)
            if len(st):
                S.scale[k] = max(float(np.quantile(st, SCALE_Q)), SCALE_FLOOR)
        return S

    def finish(self, S: SkewProfile) -> SkewProfile:
        for k in range(len(self.ids)):
            z = np.concatenate(self.z[k]) if self.z[k] else np.zeros(0)
            S.n_batches[k] = len(z)
            S.scored[k] = False
            if len(z) >= MIN_STAT_BATCHES:
                med = float(np.median(z))
                mad = 1.4826 * float(np.median(np.abs(z - med)))
                S.mu[k] = med
                S.sig[k] = max(mad, 0.1 * float(z.std()), 1e-12)
                S.scored[k] = True
        return S


class SkewLayer(CanRule):
    """L2a: clock-skew CUSUM score (higher = more attack-like). unit 'frame' or 'window'."""
    name = "can.l2a_skew"
    kind = "normal_model"
    layer_id = "L2a"
    why = "clock skew of this ID's transmitter changed (CUSUM on the RLS identification error)"

    def frame_raw(self, F) -> np.ndarray:
        return run_pass(F, self.profile)[0]
