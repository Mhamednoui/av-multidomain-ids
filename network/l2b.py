"""WP4 L2b: beaconing (command-and-control periodicity) over a flow stream.

Purpose: a bot that phones home does so at (almost) regular intervals. Per (source, destination, port, protocol) group the layer tests whether the
start times of its connections are periodic. IPs only GROUP flows (no address identity, no list of known hosts, no whitelist of NTP / DNS / update
services): the benign distribution of every regularity statistic is LEARNED from benign TRAIN groups, so a service that is periodic in benign traffic
is simply not unusual, and an alarm needs a group more regular than the benign budget allows.
Inputs: a flow STREAM (stage tables of tools/WP4_S3_prep.py): minute (int64), src_id, dst_id, dst_port, protocol. Only service-directed flows
(dst_port < 32768) are used (reversed / reply flows are not connections initiated by the group's source).
Resolution: D10 start times are whole minutes. The group's series is therefore the set of ACTIVE minutes (with flow counts). Over the trailing
WIN = 64 minutes the statistics need >= N_MIN active minutes (minimum number of connection minutes before scoring). The resolvable period range is
[2 min, ~WIN/4 min]: a period below 2 min cannot be separated from continuous activity by phase (Nyquist at 1 sample / minute); sub-minute periods only
show as a constant number of flows per minute ("rate" statistic). See tools/WP4_S4_limit.py for the measured limit.
Statistics per (group, active minute) cell, over the active minutes of the trailing window (all oriented so that larger = more periodic):
  cv   -(std / mean) of the gaps between consecutive active minutes
  mad  -(MAD / median) of the gaps (robust to a few missed or doubled beats)
  tol  fraction of gaps within max(1, 0.25 * median) of the median gap (jitter-tolerant period test; +-1 min = the resolution)
  acf  peak of the autocorrelation of the active-minute indicator at lags 2..WIN/2 (+-1 minute tolerance), divided by the number of active minutes
  rate -(CV) of the flows-per-minute counts when the group is active in >= 80% of the window minutes (sub-minute metronome)
cv / mad / tol / acf are only defined when the median gap is >= 2 minutes (continuous activity is not a beacon); rate only when it is not.
Score of a statistic = benign tail probability of its value, -log10((#benign cells at least as periodic + 1) / (N + 1)); layer score = max over the
statistics; flows inherit the value of their cell, flows of groups below N_MIN active minutes score 0.
References: McPherson et al. / Hu et al. 2016 (BAYWATCH: beacon detection by periodicity), Bartos et al. 2016, Sharafaldin et al. 2018 (CICIDS2017 Ares botnet).
"""
import numpy as np
import pandas as pd

from network.l2a import EPHEMERAL, SHIFT, TailTable, _Stream, gid

WIN = 64
N_MIN = 6
CHUNK = 40_000
STATS = ("cv", "mad", "tol", "acf", "rate")
PHASE = ("cv", "mad", "tol", "acf")     # statistics that use the phase of the connections; "rate" (sub-minute metronome) is a separate diagnostic layer
BIG = 10_000
MIN_PORT_CELLS = 200


def service_mask(df):
    return df["dst_port"].to_numpy() < EPHEMERAL


def build_cells(df, win=WIN):
    """Unique (key, minute) cells of the service-directed flows: dict with key, minute, count, comb (sorted int64) and the flow -> cell map (-1 for other flows)."""
    svc = service_mask(df)
    key = gid(df["src_id"].to_numpy(), df["dst_id"].to_numpy(), df["dst_port"].to_numpy(), df["protocol"].to_numpy())
    m = df["minute"].to_numpy().astype("int64")
    m0 = int(m.min())
    comb = (key.astype("int64") << SHIFT) | (m - m0)
    assert (m - m0).max() + win < (1 << SHIFT)
    uc, inv, cnt = np.unique(comb[svc], return_inverse=True, return_counts=True)
    fcell = np.full(len(df), -1, dtype="int64")
    fcell[svc] = inv
    return {"comb": uc, "count": cnt.astype(float), "key": uc >> SHIFT, "off": uc & ((1 << SHIFT) - 1), "fcell": fcell, "m0": m0}


def _window_matrix(c, lo, hi, win=WIN):
    """Rows lo:hi of the cells: bool matrix X[r, j] = group active j minutes before the cell's minute, and the counts matrix C."""
    comb = c["comb"]
    cur = comb[lo:hi]
    X = np.zeros((hi - lo, win), dtype=bool)
    C = np.zeros((hi - lo, win), dtype=np.float32)
    for j in range(win):
        q = cur - j
        i = np.searchsorted(comb, q)
        i = np.clip(i, 0, len(comb) - 1)
        hit = (comb[i] == q) & ((cur & ((1 << SHIFT) - 1)) >= j)
        X[:, j] = hit
        C[:, j] = np.where(hit, c["count"][i], 0)
    return X, C


def _masked_sorted(v, valid):
    """Sort each row with invalid entries pushed to +inf; returns sorted values and the number of valid entries per row."""
    w = np.where(valid, v, np.inf)
    w.sort(axis=1)
    return w, valid.sum(1)


def _row_pick(w, idx):
    idx = np.clip(idx, 0, w.shape[1] - 1)
    return w[np.arange(len(w)), idx]


def chunk_stats(X, C, n_min=N_MIN):
    """The five periodicity statistics (NaN where undefined) and the median gap for one chunk of window matrices."""
    n, win = X.shape
    nact = X.sum(1)
    j = np.arange(win)
    pos = np.where(X, j, BIG)
    pos.sort(axis=1)
    pos = pos.astype(np.float64)
    gv = pos[:, 1:] < BIG
    g = pos[:, 1:] - pos[:, :-1]
    ng = gv.sum(1)
    gs, _ = _masked_sorted(g, gv)
    med = np.where(ng > 0, 0.5 * (_row_pick(gs, (ng - 1) // 2) + _row_pick(gs, ng // 2)), np.nan)
    gm = np.where(gv, g, 0.0)
    mean = gm.sum(1) / np.maximum(ng, 1)
    std = np.sqrt(np.maximum((np.where(gv, (g - mean[:, None]) ** 2, 0.0)).sum(1) / np.maximum(ng, 1), 0.0))
    dev = np.where(gv, np.abs(g - med[:, None]), np.inf)
    ds = np.sort(dev, axis=1)
    mad = np.where(ng > 0, 0.5 * (_row_pick(ds, (ng - 1) // 2) + _row_pick(ds, ng // 2)), np.nan)
    tol = np.maximum(1.0, 0.25 * med)
    tolf = (gv & (np.abs(g - med[:, None]) <= tol[:, None])).sum(1) / np.maximum(ng, 1)
    ok = (nact >= n_min)
    beac = ok & (med >= 2)
    out = {k: np.full(n, np.nan) for k in STATS}
    out["cv"][beac] = -(std / np.maximum(mean, 1e-9))[beac]
    out["mad"][beac] = -(mad / np.maximum(med, 1e-9))[beac]
    out["tol"][beac] = tolf[beac]
    # autocorrelation peak with +-1 minute tolerance, lags 2..win/2
    Xf = X.astype(np.float32)
    ac = {}
    for L in range(1, win // 2 + 2):
        ac[L] = (Xf[:, : win - L] * Xf[:, L:]).sum(1)
    pk = np.zeros(n)
    for L in range(3, win // 2 + 1):
        pk = np.maximum(pk, np.maximum(ac[L - 1], np.maximum(ac[L], ac[L + 1])))
    out["acf"][beac] = (pk / np.maximum(nact, 1))[beac]
    # sub-minute metronome: active in most minutes of the window span, constant flows per minute
    span = np.where(nact > 0, pos[:, :].max(1, initial=0, where=pos < BIG) + 1, 1)
    frac = nact / np.maximum(span, 1)
    cnt_mean = C.sum(1) / np.maximum(nact, 1)
    cnt_std = np.sqrt(np.maximum((np.where(X, (C - cnt_mean[:, None]) ** 2, 0.0)).sum(1) / np.maximum(nact, 1), 0.0))
    rate_ok = ok & (med < 2) & (frac >= 0.8) & (cnt_mean >= 2)
    out["rate"][rate_ok] = -(cnt_std / np.maximum(cnt_mean, 1e-9))[rate_ok]
    out["_med"] = med
    out["_nact"] = nact
    return out


def cell_stats(c, win=WIN, n_min=N_MIN):
    n = len(c["comb"])
    res = {k: np.full(n, np.nan) for k in STATS + ("_med", "_nact")}
    for lo in range(0, n, CHUNK):
        hi = min(n, lo + CHUNK)
        X, C = _window_matrix(c, lo, hi, win)
        s = chunk_stats(X, C, n_min)
        for k in res:
            res[k][lo:hi] = s[k]
    return res


class Beacon(_Stream):
    """Periodicity of connection start times per (source, destination, port, protocol); see the module docstring."""
    name = "net.beacon"
    key_cols = ("src_id", "dst_id", "dst_port", "protocol")
    targets = ("Bot",)

    def __init__(self, W=1, win=WIN, n_min=N_MIN, port_cond=False):
        super().__init__(W=W)
        self.win, self.n_min, self.port_cond = win, n_min, port_cond
        self.tables = {}

    def cells(self, df):
        """Pair-window unit: (group, block of WIN minutes)."""
        return gid(*[df[c].to_numpy() for c in self.key_cols], (df["minute"].to_numpy() // self.win).astype("int64"))

    def stats(self, df):
        c = build_cells(df, self.win)
        s = cell_stats(c, self.win, self.n_min)
        return c, s

    def feats(self, df, same_network=True):
        c, s = self.stats(df)
        f = {"_port": df["dst_port"].to_numpy().astype("int64")}
        fc = c["fcell"]
        for k in STATS + ("_med", "_nact"):
            v = np.full(len(df), np.nan)
            v[fc >= 0] = s[k][fc[fc >= 0]]
            f[k] = v
        return f

    def _bucket(self, port):
        """Own benign table for frequent service ports (>= MIN_PORT_CELLS benign cells), one pooled table (-1) for the rest; port_cond=False: one table."""
        if not self.port_cond:
            return np.full(len(port), -1, dtype="int64")
        return np.where(np.isin(port, self.ports), port, -1)

    def fit_stream(self, benign):
        c, s = self.stats(benign)
        fc = c["fcell"]
        port_c = np.zeros(len(c["comb"]), dtype="int64")
        port_c[fc[fc >= 0]] = benign["dst_port"].to_numpy().astype("int64")[fc >= 0]
        defined = ~np.isnan(s["cv"]) | ~np.isnan(s["rate"])
        vc = pd.Series(port_c[defined]).value_counts()
        self.ports = vc.index[vc >= MIN_PORT_CELLS].to_numpy()
        b = self._bucket(port_c)
        self.tables = {}
        for k in STATS:
            ok = ~np.isnan(s[k])
            for q in np.unique(b[ok]):
                self.tables[(k, int(q))] = TailTable(s[k][ok & (b == q)])
            if (k, -1) not in self.tables:
                self.tables[(k, -1)] = TailTable(s[k][ok])
        return self

    def stat_scores(self, f):
        out = {}
        b = self._bucket(f["_port"])
        for k in STATS:
            v = f[k]
            sc = np.zeros(len(v))
            for q in np.unique(b):
                m = ~np.isnan(v) & (b == q)
                if m.any():
                    sc[m] = self.tables.get((k, int(q)), self.tables[(k, -1)]).score(v[m])
            out[k] = sc
        return out

    def combine(self, f):
        sc = self.stat_scores(f)
        return np.max(np.vstack([sc[k] for k in PHASE]), axis=0)

    def fit(self, train, val=None):
        return self.fit_stream(train)


class BeaconStat(Beacon):
    """One statistic alone (ablation); its score column is filled by the caller from Beacon.stat_scores."""

    def __init__(self, stat, **kw):
        super().__init__(**kw)
        self.stat = stat
        self.name = f"net.beacon.{stat}"
        self.score_col = f"s_{self.name}"

    def fit(self, train, val=None):
        return self


def all_layers(**kw):
    return [Beacon(**kw)]
