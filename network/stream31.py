"""WP8 S4 (v3.1) network: streaming "running" window statistics, Evidence at flow arrival (version flag: new module, v3 files untouched).

Purpose: the frozen v3 network domain scores a flow by the FINAL value of its window cell (net.scan / net.bruteforce: the whole minute; net.trw: the whole 5-minute bin), so a flow's Evidence exists only
after the window closed (66 s median, 242 s max at the system tick level, M3). Here every flow gets its Evidence when it ARRIVES, computed from the flows seen so far (arrival order = (ts, row)):
  net.scan        distinct service ports per (src, dst) and distinct service hosts per src among the flows of the last W ticks up to and including this flow
  net.bruteforce  flows per (src, dst, port, proto) in the last W ticks including this flow, scored as log10(count / benign 99.9th percentile of that port bucket) with the v3 reference
  net.trw         threshold random walk per (src, bin of B ticks), score = peak of the walk so far (v3: peak of the whole bin)
  net.tcp_flags   unchanged (per flow, stateless)
A tick is floor(ts / tick_s). D10 timestamps are whole minutes (attack files), so tick_s = 60 and W = 1 are exactly the v3 minute cells; in the LAST flow of a cell the running value equals the v3 cell value (test E2),
so "running" reveals the v3 statistic causally; flows before the threshold-crossing flow of a cell are not alarmed (the price of causality). Sub-minute ticks (10-30 s) need second-resolution timestamps: only D23
Tue-20-02 has them (H31), so tick_s = 60 is the only value validated in S4; the parameter exists for S7.
No new fitted parameter: the fitted v3 objects (tail tables of net.scan, port references of net.bruteforce, flag-combination counts of net.tcp_flags) are reused UNCHANGED from the frozen domain
(results/WP4/s7_domain); only the per-layer ECDF calibrators / 1% thresholds and the combined (max) threshold are re-fitted on the benign validation stream for the running score distribution.
Inputs: flow dicts (network.domain.RAW_COLUMNS) in nondecreasing ts, or a stream table (network.domain.NetworkDomain.prepare). Outputs: Evidence (domain="network", layer="combined", name="network.combined",
t = flow ts, score in [0, 1] = max of the calibrated layer scores, alarm at the 1% benign-validation budget, details {method, layer_scores, final: True}); per-layer Evidence optionally.
Cost: O(1) amortised per flow in the stateful layers (dicts + per-key tick counters); the only per-flow vector call is net.tcp_flags (one-row frame).
References: Jung, Paxson, Berger, Balakrishnan 2004 (TRW); codes_v3 network/l2a.py (v3 definitions); reports/M1_NET.md section 9.
"""
import copy
import pickle
from collections import OrderedDict

import numpy as np
import pandas as pd

from common import combiner as cb
from common.calibration import ECDFCalibrator
from common.config import BUDGET_DOMAIN
from common.evidence import Evidence
from common.metrics import budget_threshold
from network import l1, l2a
from network.domain import EXPLAIN, RAW_COLUMNS, NetworkDomain

LAYERS = ["net.bruteforce", "net.scan", "net.tcp_flags", "net.trw"]        # sorted: the column order of the v3 combiner
EPH = l2a.EPHEMERAL
PAD = l2a.PAD_BYTES
STEP = l2a.TRW_STEP


class RunningState:
    """Stateful part of the running statistics. push() returns (ports, hosts, n_brute, peak) of the arriving flow. Arrival order must be nondecreasing in tick."""

    def __init__(self, tick_s=60.0, w_scan=1, w_brute=1, trw_bin=5, sweep_every=200_000, carry=False):
        self.tick_s, self.w_scan, self.w_brute, self.trw_bin, self.sweep_every, self.carry = float(tick_s), int(w_scan), int(w_brute), int(trw_bin), sweep_every, bool(carry)
        self.reset()

    def reset(self):
        self.ports = {}           # (src, dst) -> [OrderedDict tick -> {item: count}, {item: n in window}]
        self.hosts = {}           # src -> same
        self.brute = {}           # (src, dst, port, proto) -> [OrderedDict tick -> count, total]
        self.bin = None           # current trw bin index
        self.walk = {}            # src -> [walk, peak]
        self.seen = set()         # contacts of the current bin
        self.last_q = None
        self.out_of_order = 0
        self.n = 0
        self.cur_q = None
        self.cur = ({}, {}, {}, {})       # carry: own-statistic peaks of the current tick, by key (ports, hosts, brute, trw)
        self.prev = ({}, {}, {}, {})      # ... of the previous tick

    # ------------------------------------------------------------------ distinct-item window
    @staticmethod
    def _evict_items(st, q, w):
        ticks, cnt = st
        lo = q - w + 1
        while ticks:
            t0 = next(iter(ticks))
            if t0 >= lo:
                break
            for it, c in ticks.pop(t0).items():
                cnt[it] -= c
                if cnt[it] == 0:
                    del cnt[it]

    def _distinct(self, table, key, item, q, w, add):
        st = table.get(key)
        if st is None:
            if not add:
                return 0
            st = table[key] = [OrderedDict(), {}]
        self._evict_items(st, q, w)
        if add:
            tk = st[0].setdefault(q, {})
            tk[item] = tk.get(item, 0) + 1
            st[1][item] = st[1].get(item, 0) + 1
        return len(st[1])

    def _count(self, key, q, w):
        st = self.brute.get(key)
        if st is None:
            st = self.brute[key] = [OrderedDict(), 0]
        ticks = st[0]
        lo = q - w + 1
        while ticks:
            t0 = next(iter(ticks))
            if t0 >= lo:
                break
            st[1] -= ticks.pop(t0)
        ticks[q] = ticks.get(q, 0) + 1
        st[1] += 1
        return st[1]

    def _sweep(self, q):
        for table, w in ((self.ports, self.w_scan), (self.hosts, self.w_scan)):
            for k in [k for k, st in table.items() if not st[0] or next(reversed(st[0])) < q - w + 1]:
                del table[k]
        lo = q - self.w_brute + 1
        for k in [k for k, st in self.brute.items() if not st[0] or next(reversed(st[0])) < lo]:
            del self.brute[k]

    # ------------------------------------------------------------------ one flow
    def push(self, q, src, dst, port, proto, fwd, bwd, lenf, lenb):
        q = int(q)
        if self.last_q is not None and q < self.last_q:
            self.out_of_order += 1
            q = self.last_q
        self.last_q = q
        self.n += 1
        if self.sweep_every and self.n % self.sweep_every == 0:
            self._sweep(q)
        svc = port < EPH
        item = port + proto * 70000
        n_ports = self._distinct(self.ports, (src, dst), item, q, self.w_scan, svc)
        n_hosts = self._distinct(self.hosts, src, dst, q, self.w_scan, svc)
        n_br = self._count((src, dst, port, proto), q, self.w_brute)
        b = q // self.trw_bin
        if b != self.bin:
            self.bin, self.walk, self.seen = b, {}, set()
        w = self.walk.get(src)
        if w is None:
            w = self.walk[src] = [0.0, 0.0]
        c = (src, dst, port, proto)
        if c not in self.seen:
            self.seen.add(c)
            if svc and proto == 6:
                failed = (bwd == 0) or (fwd == 1 and bwd == 1 and not (lenf > PAD or lenb > PAD))
                w[0] += STEP if failed else -STEP
                if w[0] > w[1]:
                    w[1] = w[0]
        if not self.carry:
            return n_ports, n_hosts, n_br, w[1]
        if q != self.cur_q:
            self.prev = self.cur if self.cur_q is not None and q == self.cur_q + 1 else ({}, {}, {}, {})
            self.cur, self.cur_q = ({}, {}, {}, {}), q
        own = (n_ports, n_hosts, n_br, w[1])
        keys = ((src, dst), src, c, src)
        out = []
        for j in range(4):
            cj = self.cur[j]
            if own[j] > cj.get(keys[j], -1.0):
                cj[keys[j]] = own[j]
            out.append(max(own[j], self.prev[j].get(keys[j], 0.0)))
        return tuple(out)


class Stream31:
    """Running-statistic network domain (stack H). Build with Stream31.from_frozen(NetworkDomain.load(...)), then calibrate(benign_val_table), then push(flow) / score_table(table)."""

    def __init__(self, scan, brute, tcp, tick_s=60.0, w_scan=1, w_brute=1, trw_bin=5, carry=False, budget=BUDGET_DOMAIN):
        self.scan, self.brute, self.tcp = scan, brute, tcp
        self.params = dict(tick_s=tick_s, w_scan=w_scan, w_brute=w_brute, trw_bin=trw_bin, carry=carry)
        self.state = RunningState(**self.params)
        self.budget = budget
        self.cal, self.thr, self.comb_thr = {}, {}, None
        self._ref = {int(k): float(v) for k, v in brute.ref.items()}
        self._ports = set(int(p) for p in brute.ports)
        self.ip_ids = {}

    @classmethod
    def from_frozen(cls, dom: NetworkDomain, **params):
        by = {L.name: L for L in dom.layers}
        tcp = copy.deepcopy(by["net.tcp_flags"])
        c = cls(copy.deepcopy(by["net.scan"]), copy.deepcopy(by["net.bruteforce"]), tcp, **params)
        c.cal["net.tcp_flags"], c.thr["net.tcp_flags"] = tcp.calibrator, tcp.threshold      # per-flow stateless layer: v3 calibration kept
        return c

    # ------------------------------------------------------------------ raw layer scores from the running counts
    def raw_scan(self, n_ports, n_hosts):
        return np.maximum(self.scan.t_ports.score(n_ports), self.scan.t_hosts.score(n_hosts))

    def raw_brute(self, n_br, port):
        port = np.asarray(port, dtype="int64")
        bucket = np.where(np.isin(port, list(self._ports)), port, -1)
        keys = np.array(sorted(self._ref), dtype="int64")
        refv = np.array([self._ref[int(k)] for k in keys])
        ref = refv[np.searchsorted(keys, bucket)]
        return np.log10(np.maximum(np.asarray(n_br, float), 1.0) / ref)

    def raw_tcp(self, df):
        return self.tcp.raw_scores(df)

    def raw_from(self, f, port, tcp_raw):
        return {"net.scan": self.raw_scan(f[0], f[1]), "net.bruteforce": self.raw_brute(f[2], port), "net.trw": np.asarray(f[3], float), "net.tcp_flags": np.asarray(tcp_raw, float)}

    # ------------------------------------------------------------------ batch path (same state code, loop over arrays)
    def running_counts(self, df, state=None):
        """df: stream table sorted by (t, row) with columns src_id, dst_id, dst_port, protocol, t, Tot Fwd/Bwd Pkts, TotLen Fwd/Bwd Pkts -> (n_ports, n_hosts, n_brute, peak) arrays."""
        st = state or RunningState(**self.params)
        q = np.floor(df["t"].to_numpy(float) / self.params["tick_s"]).astype("int64").tolist()
        cols = [df[c].to_numpy().tolist() for c in ("src_id", "dst_id", "dst_port", "protocol")]
        cols += [df[c].to_numpy(float).tolist() for c in ("Tot Fwd Pkts", "Tot Bwd Pkts", "TotLen Fwd Pkts", "TotLen Bwd Pkts")]
        out = np.empty((len(df), 4))
        push = st.push
        for i, (qi, s, d, p, pr, fw, bw, lf, lb) in enumerate(zip(q, *cols)):
            out[i] = push(qi, s, d, p, pr, fw, bw, lf, lb)
        self.state = st
        return out[:, 0], out[:, 1], out[:, 2], out[:, 3]

    def raw_table(self, df):
        f = self.running_counts(df)
        return self.raw_from(f, df["dst_port"].to_numpy(), self.raw_tcp(df))

    # ------------------------------------------------------------------ calibration (benign validation stream only)
    def calibrate(self, benign_val):
        raw = self.raw_table(benign_val)
        for n in ("net.scan", "net.bruteforce", "net.trw"):
            cal = ECDFCalibrator().fit(raw[n])
            self.cal[n] = cal
            self.thr[n] = budget_threshold(cal.transform(raw[n]), self.budget)
        X = self.matrix(raw)
        self.comb_thr = float(budget_threshold(X.max(axis=1), self.budget))
        return self

    def matrix(self, raw):
        return np.column_stack([self.cal[n].transform(raw[n]) for n in LAYERS])

    def score_table(self, df):
        """(combined score, alarm, calibrated matrix [LAYERS], raw dict) for a stream table (mixed or benign)."""
        raw = self.raw_table(df)
        X = self.matrix(raw)
        s = X.max(axis=1)
        return s, s >= self.comb_thr, X, raw

    # ------------------------------------------------------------------ streaming path: one flow at a time
    def reset(self):
        self.state = RunningState(**self.params)
        self.ip_ids = {}

    def push(self, flow, sample_id=None, per_layer=False):
        """flow: mapping with RAW_COLUMNS (ts as epoch seconds or datetime). Returns the combined Evidence (and the per-layer list when per_layer)."""
        ts = flow["ts"]
        t = float(pd.Timestamp(ts).value / 1e9) if not isinstance(ts, (int, float, np.integer, np.floating)) else float(ts)
        one = pd.DataFrame([{c: flow[c] for c in RAW_COLUMNS if c in flow}])
        for c in ("dst_port", "protocol"):
            one[c] = pd.to_numeric(one[c], errors="coerce").fillna(-1).astype("int64")
        q = int(np.floor(t / self.params["tick_s"]))
        f = self.state.push(q, flow["src_ip"], flow["dst_ip"], int(one["dst_port"].iloc[0]), int(one["protocol"].iloc[0]), float(flow["Tot Fwd Pkts"]), float(flow["Tot Bwd Pkts"]),
                            float(flow["TotLen Fwd Pkts"]), float(flow["TotLen Bwd Pkts"]))
        raw = self.raw_from([np.array([x]) for x in f], one["dst_port"].to_numpy(), self.raw_tcp(one))
        X = self.matrix(raw)[0]
        s = float(X.max())
        sid = str(self.state.n - 1 if sample_id is None else sample_id)
        alarm = s >= self.comb_thr
        reason = ""
        if alarm:
            fired = sorted([(X[j], n) for j, n in enumerate(LAYERS) if X[j] >= self.thr[n]], reverse=True)
            reason = ("Network alarm: " + "; ".join(f"{EXPLAIN.get(n, n)} (layer {n}, score {sc:.3f})" for sc, n in fired[:3]) + ".") if fired else "Network alarm: no single layer fired."
        ev = Evidence(domain="network", layer="combined", name="network.combined", t=t, score=s, alarm=bool(alarm), reason=reason,
                      details={"method": "max", "layer_scores": {n: float(X[j]) for j, n in enumerate(LAYERS)}, "final": True, "provisional_running": True}, sample_id=sid)
        if not per_layer:
            return ev
        per = [Evidence(domain="network", layer=("L1" if n == "net.tcp_flags" else "L2a"), name=n, t=t, score=float(X[j]), alarm=bool(X[j] >= self.thr[n]), reason="",
                        details={"raw": float(raw[n][0])}, sample_id=sid) for j, n in enumerate(LAYERS)]
        return ev, per

    # ------------------------------------------------------------------ persistence
    def save(self, path):
        st, self.state = self.state, None
        try:
            with open(path, "wb") as f:
                pickle.dump(self, f)
        finally:
            self.state = st

    @staticmethod
    def load(path):
        with open(path, "rb") as f:
            o = pickle.load(f)
        o.state = RunningState(**o.params)
        return o


# ====================================================================== independent reference (quadratic, tests only)
def reference_running(rows, tick_s=60.0, w_scan=1, w_brute=1, trw_bin=5, carry=False):
    """Direct definition of the running counts, O(n^2), written independently of RunningState. rows: list of (t, src, dst, port, proto, fwd, bwd, lenf, lenb) in arrival order.
    Returns a list of (n_ports, n_hosts, n_brute, peak)."""
    out = []
    qs = [int(np.floor(r[0] / tick_s)) for r in rows]
    for i, r in enumerate(rows):
        qi = qs[i]
        _, src, dst, port, proto, fwd, bwd, lf, lb = r
        ports, hosts, nb = set(), set(), 0
        for j in range(i + 1):
            qj = qs[j]
            _, s2, d2, p2, pr2, *_ = rows[j]
            if qj > qi - w_scan and s2 == src and p2 < EPH:
                if d2 == dst:
                    ports.add(p2 + pr2 * 70000)
                hosts.add(d2)
            if qj > qi - w_brute and (s2, d2, p2, pr2) == (src, dst, port, proto):
                nb += 1
        walk = peak = 0.0
        b = qi // trw_bin
        seen = set()
        for j in range(i + 1):
            if qs[j] // trw_bin != b or rows[j][1] != src:
                continue
            _, s2, d2, p2, pr2, f2, b2, lf2, lb2 = rows[j]
            c = (d2, p2, pr2)
            if c in seen:
                continue
            seen.add(c)
            if p2 < EPH and pr2 == 6:
                failed = (b2 == 0) or (f2 == 1 and b2 == 1 and not (lf2 > PAD or lb2 > PAD))
                walk += STEP if failed else -STEP
                peak = max(peak, walk)
        out.append((len(ports), len(hosts), nb, peak))
    if not carry:
        return out
    # carry: statistic = max(own, peak of the own statistic of the same key over the flows of the PREVIOUS tick)
    res = []
    for i, r in enumerate(rows):
        _, src, dst, port, proto = r[:5]
        keys = ((src, dst), src, (src, dst, port, proto), src)
        pk = lambda j, k: max([out[m][j] for m in range(i) if qs[m] == qs[i] - 1 and ((rows[m][1], rows[m][2]), rows[m][1], tuple(rows[m][1:5]), rows[m][1])[j] == k] or [0.0])
        res.append(tuple(max(out[i][j], pk(j, keys[j])) for j in range(4)))
    return res


# ====================================================================== minute-final emission (candidate F1 of the S4 round 2)
class Stream31Final(Stream31):
    """Tick-final emission: the v3 cell statistics with a trw bin of one tick, delivered when the cell's tick has closed (the first flow of a later tick arrives, or flush()). Flows are buffered
    for at most one tick, so the Evidence delay is the tick (60 s on D10) instead of the 5-minute bin plus the prefix re-score of the v3 runner; no whole-buffer re-score: the stateful part is the same
    O(1) RunningState, and the final value of a cell is the maximum of the running values of its flows (the running values are nondecreasing inside a tick)."""

    def __init__(self, scan, brute, tcp, tick_s=60.0, w_scan=1, w_brute=1, budget=BUDGET_DOMAIN):
        super().__init__(scan, brute, tcp, tick_s=tick_s, w_scan=w_scan, w_brute=w_brute, trw_bin=1, carry=False, budget=budget)
        self.buf = []

    @classmethod
    def from_frozen(cls, dom: NetworkDomain, **params):
        base = Stream31.from_frozen(dom, trw_bin=1)
        c = cls(base.scan, base.brute, base.tcp, **params)
        c.cal["net.tcp_flags"], c.thr["net.tcp_flags"] = base.cal["net.tcp_flags"], base.thr["net.tcp_flags"]
        return c

    # ------------------------------------------------------------------ batch path
    @staticmethod
    def _cell_max(vals, *key_cols):
        k = pd.DataFrame({str(i): np.asarray(c) for i, c in enumerate(key_cols)})
        return pd.Series(np.asarray(vals, float)).groupby([k[c] for c in k.columns]).transform("max").to_numpy()

    def final_counts(self, df):
        n_ports, n_hosts, n_br, peak = self.running_counts(df)
        q = np.floor(df["t"].to_numpy(float) / self.params["tick_s"]).astype("int64")
        s, d, p, pr = (df[c].to_numpy() for c in ("src_id", "dst_id", "dst_port", "protocol"))
        return (self._cell_max(n_ports, s, d, q), self._cell_max(n_hosts, s, q), self._cell_max(n_br, s, d, p, pr, q), self._cell_max(peak, s, q))

    def raw_table(self, df):
        return self.raw_from(self.final_counts(df), df["dst_port"].to_numpy(), self.raw_tcp(df))

    # ------------------------------------------------------------------ streaming path
    def reset(self):
        super().reset()
        self.buf = []

    def push(self, flow, sample_id=None, per_layer=False):
        t = float(pd.Timestamp(flow["ts"]).value / 1e9) if not isinstance(flow["ts"], (int, float, np.integer, np.floating)) else float(flow["ts"])
        q = int(np.floor(t / self.params["tick_s"]))
        out = self.flush() if self.buf and q > self.buf[-1]["q"] else []
        one = pd.DataFrame([{c: flow[c] for c in RAW_COLUMNS if c in flow}])
        for c in ("dst_port", "protocol"):
            one[c] = pd.to_numeric(one[c], errors="coerce").fillna(-1).astype("int64")
        port, proto = int(one["dst_port"].iloc[0]), int(one["protocol"].iloc[0])
        f = self.state.push(q, flow["src_ip"], flow["dst_ip"], port, proto, float(flow["Tot Fwd Pkts"]), float(flow["Tot Bwd Pkts"]), float(flow["TotLen Fwd Pkts"]), float(flow["TotLen Bwd Pkts"]))
        self.buf.append({"q": q, "t": t, "one": one, "f": f, "src": flow["src_ip"], "dst": flow["dst_ip"], "port": port, "proto": proto,
                         "sid": str(self.state.n - 1 if sample_id is None else sample_id)})
        return out

    def flush(self):
        """Emit the Evidence of the buffered tick (called by push on a tick change and at the end of the capture)."""
        b, self.buf = self.buf, []
        if not b:
            return []
        mx = [dict(), dict(), dict(), dict()]
        keys = lambda r: ((r["src"], r["dst"]), r["src"], (r["src"], r["dst"], r["port"], r["proto"]), r["src"])
        for r in b:
            for j, k in enumerate(keys(r)):
                if r["f"][j] > mx[j].get(k, -1.0):
                    mx[j][k] = r["f"][j]
        fin = [np.array([mx[j][keys(r)[j]] for r in b], float) for j in range(4)]
        one = pd.concat([r["one"] for r in b], ignore_index=True)
        raw = self.raw_from(fin, np.array([r["port"] for r in b]), self.raw_tcp(one))
        X = self.matrix(raw)
        s = X.max(axis=1)
        out = []
        for i, r in enumerate(b):
            alarm = bool(s[i] >= self.comb_thr)
            reason = ""
            if alarm:
                fired = sorted([(X[i, j], n) for j, n in enumerate(LAYERS) if X[i, j] >= self.thr[n]], reverse=True)
                reason = ("Network alarm: " + "; ".join(f"{EXPLAIN.get(n, n)} (layer {n}, score {sc:.3f})" for sc, n in fired[:3]) + ".") if fired else "Network alarm: no single layer fired."
            out.append(Evidence(domain="network", layer="combined", name="network.combined", t=r["t"], score=float(s[i]), alarm=alarm, reason=reason,
                                details={"method": "max", "layer_scores": {n: float(X[i, j]) for j, n in enumerate(LAYERS)}, "final": True, "emitted_at_tick_close": True}, sample_id=r["sid"]))
        return out
