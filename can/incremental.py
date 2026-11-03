"""Incremental (constant cost per window) scoring of the FROZEN v3 CAN domain (WP8 v3.1 S5).

Purpose: the v3 CanRunner re-scores the whole prefix of a capture every second, so the cost of a window grows with the capture (0.14 s -> 2.3 s).
IncrementalCan produces the SAME Evidence (CanDomain.score_capture on the whole capture) with a bounded state, so the cost of a window depends on the
frames of that window only. It is an engineering change: no model, threshold or rule differs from can/domain.py (which stays untouched, as does v3).
State carried between windows (all bounded):
  L1   last timestamp per arbitration ID (gap to the previous frame of the ID) and the frames of the trailing second (bus load, flood)
  L3   the last held value of each of the 138 continuous signals and the 4 discrete ones (0.05 s sample-and-hold grid), the last 20 raw grid rows (lags of the
       ridge predictors), the last 21 running CUSUM sums (sum of the last 20 steps = 1 s) and the last 20 reverse-light rows; the running sums are
       continued with the same float64 cumulative additions as the batch code (bit-identical differences)
  per second: max grid score and culprit signal of the seconds not yet emitted
How: frames of the open second are buffered; when the first frame of the next second arrives (running-max clock), the grid steps strictly before that time are
final (no frame with a time <= the step can still arrive), they are scored in one small block, the window raw scores are formed and the existing
CanDomain.calibrated / combiner / reasons code turns them into Evidence. flush() emits the last (partial) window like the batch code.
Inputs: feed(t, ids, dlc, B) arrays in recorded order, or push(t, id, dlc, payload8) one frame. Outputs: list of (combined Evidence, {layer name: Evidence}) per
completed window, pop_motion() for the wheel-speed MotionEstimates (same values as CanDomain.motion_estimates).
Equality with the batch code: tests/v31/test_can_incremental.py and tools/WP8_S5_can.py (0 mismatches, max |diff| reported).
References: can/domain.py, can/stack_core.py (window_raws), can/l3_predictors.py, notes/WP8_v31.md rule S5 C1-C2.
"""
import numpy as np

from can import l1 as L
from can import l3_predictors as P
from can import signals as S
from can.domain import RULES, WHEELS, WHEEL_UNIT_MPS, SPEED_SIGMA_MIN, SPEED_SIGMA_REL, layer_raws
from can.stack_core import CAT, DBC, DISC
from common.motion import MotionEstimate

TAIL_S = 1.0          # trailing window of the bus-load / flood rules (s)
NLAG = max(P.LAGS)    # raw grid rows kept for the lags (20)


class _Buf:
    """Growing arrays of the open second (amortised O(1) append)."""

    def __init__(self, cap=2048):
        self.n = 0
        self.t = np.empty(cap)
        self.tm = np.empty(cap)
        self.id = np.empty(cap, np.int64)
        self.dlc = np.empty(cap, np.int64)
        self.B = np.empty((cap, 8), np.uint8)

    def _grow(self, need):
        c = max(2 * len(self.t), need)
        self.t, self.tm = np.resize(self.t, c), np.resize(self.tm, c)
        self.id, self.dlc = np.resize(self.id, c), np.resize(self.dlc, c)
        self.B = np.resize(self.B, (c, 8))

    def add(self, t, tm, i, d, B):
        m = len(t)
        if self.n + m > len(self.t):
            self._grow(self.n + m)
        s = slice(self.n, self.n + m)
        self.t[s], self.tm[s], self.id[s], self.dlc[s], self.B[s] = t, tm, i, d, B
        self.n += m

    def take(self):
        n = self.n
        out = (self.t[:n].copy(), self.tm[:n].copy(), self.id[:n].copy(), self.dlc[:n].copy(), self.B[:n].copy())
        self.n = 0
        return out


class IncrementalCan:
    def __init__(self, dom, name="capture", explain=True):
        self.dom, self.explain = dom, explain
        m, r, _ = dom.cfg["l3c"]
        self.mdl = dom.models.l3c[m]
        self.rmin = r
        self.use = self.mdl.r2 >= r
        self.l3d = dom.models.l3d
        self.prof = dom.models.profile
        self.ncont = len(CAT.cont)
        # signal -> (id, [(k, column)]) maps for the hold step
        self.cont_by_id, self.disc_by_id = {}, {}
        for (i, k), c in CAT.cont_ix.items():
            self.cont_by_id.setdefault(i, []).append((k, c))
        for c, (i, k) in enumerate(DISC):
            self.disc_by_id.setdefault(i, []).append((k, c))
        self.reset(name)

    def reset(self, name="capture"):
        self.name = name
        self.buf = _Buf()
        self.tm_max = -np.inf
        self.sec = None                       # integer second of the open window
        self.g0 = None
        self.delta = None
        self.k_next = 0                       # next grid step to score
        self.nsteps_total = 0
        self.carry_c = np.full(self.ncont, np.nan)
        self.carry_d = np.full(len(DISC), np.nan)
        self.prevG = np.zeros((0, self.ncont), np.float32)
        self.prevGd = np.zeros((0, len(DISC)), np.float32)
        self.cs_tail = np.zeros((1, self.ncont))      # cs[a..N]; cs[0] = 0
        self.cs_a = 0                                 # index of the first row of cs_tail
        self.sec_scores = {}                          # sec -> [max l3c f32, max l3d f32, best w64, best col]
        self.last_t = {}                              # id -> last raw t
        self.tail = None                              # trailing-second frames (tm, id, dlc, dt_id, bits)
        self.motion = []
        self.wv = np.nan                              # held wheel-speed value (m/s)
        self.me_next = None                           # next MotionEstimate end time
        self.tm0 = None
        self.n_frames = 0

    # ------------------------------------------------------------------ input
    def push(self, t, i, dlc, b):
        return self.feed(np.array([t], float), np.array([i]), np.array([dlc]), np.asarray(b, np.uint8)[None, :])

    def feed(self, t, ids, dlc, B):
        t = np.asarray(t, float)
        if not len(t):
            return []
        ids, dlc, B = np.asarray(ids, np.int64), np.asarray(dlc, np.int64), np.asarray(B, np.uint8)
        tm = np.maximum.accumulate(np.r_[self.tm_max, t])[1:]
        self.tm_max = float(tm[-1])
        if self.tm0 is None:
            self.tm0 = float(t[0])
            self.g0 = self.tm0 + 1.0
            self.delta = (self.g0 + P.GRID_DT) - self.g0
        self.n_frames += len(t)
        sec = np.floor(tm).astype(np.int64)
        cut = np.flatnonzero(np.diff(sec)) + 1
        bounds = np.r_[0, cut, len(t)]
        out = []
        for a, b in zip(bounds[:-1], bounds[1:]):
            s = int(sec[a])
            if self.sec is not None and s != self.sec:
                out.extend(self._close(float(tm[a])))
            self.sec = s
            self.buf.add(t[a:b], tm[a:b], ids[a:b], dlc[a:b], B[a:b])
        return out

    def flush(self):
        """Emit the open (partial) window and the remaining MotionEstimates, like the batch code on a whole capture."""
        if self.buf.n == 0:
            return []
        return self._close(self.tm_max, final=True)

    def pop_motion(self):
        out, self.motion = self.motion, []
        return out

    # ------------------------------------------------------------------ one window
    def _close(self, tm_next, final=False):
        t, tm, ids, dlc, B = self.buf.take()
        sec = int(np.floor(tm[0]))
        dec = S.decode_all(ids, B, DBC)
        raw1 = self._l1(t, tm, ids, dlc)
        self._l3_steps(tm, dec, tm_next, final)
        self._motion(tm, dec, tm_next, final)
        sc = self.sec_scores.get(sec)
        for k in [k for k in self.sec_scores if k <= sec]:
            if k != sec:
                del self.sec_scores[k]
        if sc is None:
            self.sec_scores.pop(sec, None)
            self._update_carry(tm, dec)
            return []
        del self.sec_scores[sec]
        self._update_carry(tm, dec)
        tab = {"sec": np.array([sec]), "w_end": np.array([float(tm[-1])]), "ok": np.array([True])}
        tab.update({k: np.array([v], np.float32) for k, v in raw1.items()})
        m = self.dom.cfg["l3c"][0]
        tab[f"l3c_{m}@{self.rmin}"] = np.array([sc[0]], np.float32)
        tab["l3d"] = np.array([sc[1]], np.float32)
        reasons = None
        if self.explain:
            cal = self.dom.calibrated(tab)["L3c"]
            if cal[0] >= self.dom.layer_thresholds["L3c"]:
                j = sc[3]
                reasons = {0: f"{CAT.cont[j][0]:#x}.{CAT.cont[j][1]}"}
            else:
                reasons = {}
        comb, per = self.dom.evidence_from_table(tab, sample_prefix=self.name + "/", reasons=reasons)
        return [(comb[0], {l: per[l][0] for l in per})]

    # ---- L1 -----------------------------------------------------------------------------------
    def _l1(self, t, tm, ids, dlc):
        n = len(t)
        # gap to the previous frame of the same ID (raw t, clipped at 0; NaN for the first frame of an ID)
        order = np.argsort(ids, kind="stable")
        ids_s, t_s = ids[order], t[order]
        first = np.r_[True, ids_s[1:] != ids_s[:-1]]
        prev = np.r_[np.nan, t_s[:-1]]
        for j in np.flatnonzero(first):
            prev[j] = self.last_t.get(int(ids_s[j]), np.nan)
        d = t_s - prev
        d = np.where(d < 0, 0.0, d)
        last = np.r_[first[1:], True]
        for j in np.flatnonzero(last):
            self.last_t[int(ids_s[j])] = float(t_s[j])
        dt_id = np.empty(n, np.float32)
        dt_id[order] = d
        bits = (L.OVERHEAD_BITS + 8 * dlc).astype(np.int64)
        # trailing second: previous frames with tm > sec - 1 plus this window
        if self.tail is None:
            tmb, idb, dlb, dtb, bib = tm, ids, dlc, dt_id, bits
        else:
            tmb = np.r_[self.tail[0], tm]
            idb = np.r_[self.tail[1], ids]
            dlb = np.r_[self.tail[2], dlc]
            dtb = np.r_[self.tail[3], dt_id]
            bib = np.r_[self.tail[4], bits]
        lo = np.searchsorted(tmb, tmb - TAIL_S, side="right").astype(np.int32)
        cs = np.concatenate(([0], np.cumsum(bib)))
        load = ((cs[1:] - cs[lo]) / 1000.0).astype(np.float32)
        F = {"id": idb, "dlc": dlb.astype(np.int16), "dt_id": dtb, "lo": lo, "load": load}
        keep = int(np.floor(tm[0])) - TAIL_S
        sl = slice(len(tmb) - n, None)
        k = self.dom.cfg["l1_variant"]
        prof = self.prof
        old = prof.variant
        out = {}
        for c in L.RULE_CLASSES:
            if c is L.PeriodPerId:
                prof.set_variant(k)
                out[f"l1_{c.name}#{k}"] = float(np.max(c(prof).frame_raw(F)[sl].astype(np.float32)))
            else:
                out[f"l1_{c.name}"] = float(np.max(c(prof).frame_raw(F)[sl].astype(np.float32)))
        prof.set_variant(old)
        m = tmb > keep
        self.tail = (tmb[m], idb[m], dlb[m], dtb[m], bib[m])
        return out

    # ---- L3 -----------------------------------------------------------------------------------
    def _held(self, dec, tm, g, by_id, carry):
        out = np.empty((len(g), len(carry)), np.float32)
        out[:] = carry[None, :].astype(np.float32)
        for i, cols in by_id.items():
            if i not in dec:
                continue
            rows, V = dec[i]
            tmr = tm[rows]
            pos = np.searchsorted(tmr, g, side="right") - 1
            ok = pos >= 0
            for k, c in cols:
                v = np.where(ok, V[np.maximum(pos, 0), k], carry[c])
                out[:, c] = v
        return out

    def _l3_steps(self, tm, dec, tm_next, final):
        if self.g0 is None:
            return
        if final:
            k_end = max(int(np.ceil((tm_next - self.g0) / P.GRID_DT)), 0)
            if k_end <= self.k_next:
                return
            ks = np.arange(self.k_next, k_end)
        else:
            if tm_next <= self.g0:
                return
            est = int(np.ceil((tm_next - self.g0) / self.delta)) + 2
            ks = np.arange(self.k_next, max(est, self.k_next))
            g = self.g0 + ks * self.delta
            ks = ks[g < tm_next]
            if not len(ks):
                return
        g = self.g0 + ks * self.delta
        Gc = self._held(dec, tm, g, self.cont_by_id, self.carry_c)
        Gd = self._held(dec, tm, g, self.disc_by_id, self.carry_d)
        m = len(ks)
        # L3c: residuals with the lag rows of the previous steps
        aug = np.vstack([self.prevG, Gc])
        z = P.z_matrix(self.mdl, aug)[len(self.prevG):]
        T = np.maximum(z - P.CUSUM_K, 0.0)
        cs_new = np.cumsum(np.vstack([self.cs_tail[-1:], T]), axis=0, dtype=np.float64)[1:]
        full = np.vstack([self.cs_tail, cs_new])
        idx = self.k_next + 1 + np.arange(m)                       # cs indices of the new steps
        w = full[idx - self.cs_a] - full[np.maximum(idx - P.L3D_WIN, 0) - self.cs_a]
        keep_from = max(len(full) - (P.L3D_WIN + 1), 0)
        self.cs_a += keep_from
        self.cs_tail = full[keep_from:]
        gs3 = w.astype(np.float32)[:, self.use].max(1)
        w64 = np.where(self.use[None, :], w, -1.0)
        # L3d
        augd = np.vstack([self.prevGd, Gd])
        s3d = P.l3d_scores(self.l3d, augd)[len(self.prevGd):]
        self.prevG = aug[-NLAG:]
        self.prevGd = augd[-P.L3D_WIN:]
        gsec = np.floor(self.g0 + P.GRID_DT * ks).astype(np.int64)
        for s in np.unique(gsec):
            sel = np.flatnonzero(gsec == s)
            blk = w64[sel]
            flat = int(np.argmax(blk))
            best, col = float(blk.flat[flat]), flat % blk.shape[1]
            cur = self.sec_scores.get(int(s))
            if cur is None:
                self.sec_scores[int(s)] = [gs3[sel].max(), s3d[sel].max(), best, col]
            else:
                cur[0], cur[1] = max(cur[0], gs3[sel].max()), max(cur[1], s3d[sel].max())
                if best > cur[2]:
                    cur[2], cur[3] = best, col
        self.k_next += m

    def _update_carry(self, tm, dec):
        for i, cols in self.cont_by_id.items():
            if i in dec:
                V = dec[i][1][-1]
                for k, c in cols:
                    self.carry_c[c] = V[k]
        for i, cols in self.disc_by_id.items():
            if i in dec:
                V = dec[i][1][-1]
                for k, c in cols:
                    self.carry_d[c] = V[k]

    # ---- ego motion ---------------------------------------------------------------------------
    def _motion(self, tm, dec, tm_next, final):
        wid = WHEELS[0][0]
        if self.me_next is None:
            self.me_next = np.ceil(self.tm0) + 1.0
        if wid in dec:
            rr, V = dec[wid]
            tw = tm[rr]
            v = np.mean([V[:, k] for _, k in WHEELS], axis=0) * WHEEL_UNIT_MPS
        else:
            tw, v = np.zeros(0), np.zeros(0)
        limit = tm_next + 1e-9 if final else tm_next
        while self.me_next < limit if final else self.me_next < tm_next:
            e = self.me_next
            p = np.searchsorted(tw, e, side="right") - 1
            val = float(v[p]) if p >= 0 else self.wv
            if np.isfinite(val):
                self.motion.append(MotionEstimate(t=float(e), source="can", speed=val, yaw_rate=None, displacement=None,
                                                  sigma=float(max(SPEED_SIGMA_MIN, SPEED_SIGMA_REL * val))))
            self.me_next += 1.0
        if len(v):
            self.wv = float(v[-1])
