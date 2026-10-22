"""WP4 L2a: host time-window logic over a flow stream (port scan, TRW, brute force, DoS rate, slow / half-open connections).

Purpose: count what attacks must do (probe many ports / hosts, retry logins, flood one destination, hold connections open)
instead of recognising the shape of a single flow.
Reply flows: CICFlowMeter often reports a flow in the reverse direction (server as "source", client ephemeral port as "destination"); scan and
TRW therefore count only service-directed flows (destination port < 32768), otherwise busy servers look like scanners.
Topology-free rule: the address columns (src_id, dst_id) are used only to GROUP flows (per source, per source-destination pair, per
destination). No list of known hosts, no address constant, no "this IP is the attacker". The only learned per-destination object is the
benign rate baseline of net.dos_rate (a profile learned on the protected network itself; destinations never seen in training fall back to a
pooled baseline, and `same_network=False` disables the lookup when the model is moved to another network).
Inputs: a DataFrame = one flow STREAM, sorted by time (the stage tables of tools/WP4_S3_prep.py): columns minute (int64, minutes), src_id,
dst_id, dst_port, protocol, 'Flow Duration' (us), 'Tot Fwd Pkts', 'Tot Bwd Pkts', 'TotLen Fwd Pkts', 'TotLen Bwd Pkts', row (order inside a minute).
Outputs: per-flow raw score = value of the flow's (key, minute) cell (alarm at the end of the window); higher = more attack-like.
Stream layers: features need the whole stream (a subsample would lose the multiplicity), so raw_scores() reads a precomputed column
`score_col` if the table has it, and otherwise computes the stream itself. Sliding windows: trailing W minutes including the own minute.
References: Jung, Paxson, Berger, Balakrishnan 2004 (threshold random walk, IEEE S&P); Weaver et al. 2004; Sharafaldin et al. 2018 (data).
Notes: D10 timestamps have one-minute resolution, so W is in whole minutes. TRW uses TUMBLING windows (the walk restarts every W minutes).
"""
import numpy as np
import pandas as pd

from common.layer import Layer

SHIFT = 24                    # key = kid << SHIFT | minute offset (offsets < 2**24 minutes)
DUR_STALL_US = 5_000_000      # stalled connection: >= 5 s ...
RATE_STALL = 2.0              # ... and <= 2 packets / s
PAD_BYTES = 6                 # CICFlowMeter counts the Ethernet minimum-frame padding of a bare RST / ACK (6 B) as payload: <= 6 B = no payload
EPHEMERAL = 32768             # destination ports >= this are ephemeral (IANA 49152, Linux 32768): such flows are reversed / reply flows, not probes
TRW_TH0, TRW_TH1 = 0.8, 0.2   # benign / scanner probability of a successful first contact (Jung et al. 2004)
TRW_STEP = float(np.log((1 - TRW_TH1) / (1 - TRW_TH0)))    # ln 4: a failure adds, a success subtracts
TRW_CLASSIC = float(np.log(0.99 / 0.01))                   # classic decision threshold for alpha = 0.01, beta = 0.99


def gid(*cols):
    """Dense int64 group id of the combination of the given arrays."""
    df = pd.DataFrame({str(i): np.asarray(c) for i, c in enumerate(cols)})
    return df.groupby(list(df.columns), sort=False).ngroup().to_numpy().astype("int64")


def trailing(kid, minute, W, iid=None, w=None, mask=None):
    """Per flow: number of flows (iid None; weight w per flow if given) or of distinct items iid of its key kid in the trailing W minutes (own minute included).
    Interval-union events + cumulative sum, no loop over flows."""
    kid = np.asarray(kid, dtype="int64")
    m = np.asarray(minute, dtype="int64")
    m = m - m.min()
    assert m.max() + W < (1 << SHIFT)
    if iid is None:
        w = np.ones(len(kid)) if w is None else np.asarray(w, dtype=float)
        ek = np.concatenate([kid, kid])
        em = np.concatenate([m, m + W])
        ed = np.concatenate([w, -w])
    else:
        a = pd.DataFrame({"k": kid, "i": np.asarray(iid, dtype="int64"), "m": m})
        if mask is not None:
            a = a[np.asarray(mask)]
        a = a.drop_duplicates()
        o = np.lexsort((a["m"].to_numpy(), a["i"].to_numpy(), a["k"].to_numpy()))
        k, i, mm = a["k"].to_numpy()[o], a["i"].to_numpy()[o], a["m"].to_numpy()[o]
        same = np.r_[False, (k[1:] == k[:-1]) & (i[1:] == i[:-1])]
        prev = np.r_[0, mm[:-1]]
        start = np.where(same & (mm < prev + W), prev + W, mm)    # part of [mm, mm+W-1] not already covered by the previous appearance
        ek = np.concatenate([k, k])
        em = np.concatenate([start, mm + W])
        ed = np.concatenate([np.ones(len(k)), -np.ones(len(k))])
    qk = (kid << SHIFT) | m
    key = np.concatenate([(ek << SHIFT) | em, qk])
    d = np.concatenate([ed, np.zeros(len(qk))])
    uk, inv = np.unique(key, return_inverse=True)
    s = np.bincount(inv, weights=d, minlength=len(uk))
    cs = np.cumsum(s)
    kk = uk >> SHIFT
    st = np.r_[True, kk[1:] != kk[:-1]]
    seg = np.cumsum(st) - 1
    base = (cs - s)[st]
    val = cs - base[seg]
    return val[np.searchsorted(uk, qk)]


class TailTable:
    """Benign tail probability of a count: score = -log10((#cells >= v + 1) / (N + 1)); built from benign cells."""

    def __init__(self, values):
        self.v = np.sort(np.asarray(values, dtype=float))
        self.n = len(self.v)

    def score(self, x):
        ge = self.n - np.searchsorted(self.v, np.asarray(x, dtype=float), side="left")
        return -np.log10((ge + 1.0) / (self.n + 1.0))


def unique_cells(cell, *vals):
    _, i = np.unique(cell, return_index=True)
    return [np.asarray(v)[i] for v in vals]


def first_contact_failed(df):
    """TRW outcome of a flow: failure = no reply packet at all, or a TCP flow of exactly one packet each way without payload
    (a SYN answered by a bare RST: refused; payload <= 6 B per direction = Ethernet padding). Rule uses packet / byte counts only (RST / ECE flag columns differ between CICIDS2017 and 2018)."""
    fwd, bwd = df["Tot Fwd Pkts"].to_numpy(float), df["Tot Bwd Pkts"].to_numpy(float)
    pay = (df["TotLen Fwd Pkts"].to_numpy(float) > PAD_BYTES) | (df["TotLen Bwd Pkts"].to_numpy(float) > PAD_BYTES)
    tcp = df["protocol"].to_numpy() == 6
    return (bwd == 0) | (tcp & (fwd == 1) & (bwd == 1) & ~pay)


class _Stream(Layer):
    domain, kind, layer_id = "network", "rule", "L2a"
    key_cols = ("src_id",)
    targets = ()

    def __init__(self, W=1):
        super().__init__()
        self.W = W
        self.score_col = f"s_{self.name}"

    # --- to override
    def feats(self, df, same_network=True):
        """dict name -> per-flow array (value of the cell)."""
        raise NotImplementedError

    def fit_stream(self, benign):
        """Learn from the benign-only stream."""
        raise NotImplementedError

    def combine(self, f):
        raise NotImplementedError

    # --- common
    def stream_scores(self, df, same_network=True):
        return self.combine(self.feats(df, same_network))

    def raw_scores(self, samples):
        if self.score_col in samples.columns:
            return samples[self.score_col].to_numpy(float)
        return self.stream_scores(samples)

    def cells(self, df):
        """Dense id of the window cell (key, time) of every flow (window unit of the evaluation)."""
        return gid(*[df[c].to_numpy() for c in self.key_cols], df["minute"].to_numpy())

    def reasons(self, samples, raw, alarm):
        return [f"{self.name}: window statistic {r:.3g} above the benign 1% budget threshold" for r in raw]


class Scan(_Stream):
    """Distinct destination ports per (source, destination) and distinct destination hosts per source in the trailing window."""
    name = "net.scan"
    key_cols = ("src_id",)
    targets = ("PortScan",)

    def feats(self, df, same_network=True):
        m = df["minute"].to_numpy()
        port = df["dst_port"].to_numpy().astype("int64") + df["protocol"].to_numpy().astype("int64") * 70000
        k_pair = gid(df["src_id"].to_numpy(), df["dst_id"].to_numpy())
        svc = df["dst_port"].to_numpy() < EPHEMERAL
        return {"ports": trailing(k_pair, m, self.W, port, mask=svc),
                "hosts": trailing(df["src_id"].to_numpy(), m, self.W, df["dst_id"].to_numpy(), mask=svc)}

    def fit_stream(self, benign):
        f = self.feats(benign)
        cell = gid(benign["src_id"].to_numpy(), benign["dst_id"].to_numpy(), benign["minute"].to_numpy())
        self.t_ports = TailTable(unique_cells(cell, f["ports"])[0])
        cell2 = gid(benign["src_id"].to_numpy(), benign["minute"].to_numpy())
        self.t_hosts = TailTable(unique_cells(cell2, f["hosts"])[0])
        return self

    def combine(self, f):
        return np.maximum(self.t_ports.score(f["ports"]), self.t_hosts.score(f["hosts"]))

    def fit(self, train, val=None):
        return self.fit_stream(train)


class Trw(_Stream):
    """Threshold random walk (Jung et al. 2004) per source and tumbling window of W minutes, first contacts to distinct
    (destination, port); failure +ln4, success -ln4; score = peak of the walk (>= 0)."""
    name = "net.trw"
    key_cols = ("src_id", "bin")
    targets = ("PortScan",)

    def feats(self, df, same_network=True):
        b = (df["minute"].to_numpy() // self.W).astype("int64")
        src = df["src_id"].to_numpy()
        g = gid(src, b)
        contact = gid(src, df["dst_id"].to_numpy(), df["dst_port"].to_numpy(), df["protocol"].to_numpy(), b)
        order = np.lexsort((df["row"].to_numpy(), df["minute"].to_numpy(), g))    # group, minute, file order
        go, co = g[order], contact[order]
        # first contact = first flow of a (src,dst,port,bin) contact, in file order inside the group
        seen = pd.Series(co).duplicated().to_numpy()
        svc = ((df["dst_port"].to_numpy() < EPHEMERAL) & (df["protocol"].to_numpy() == 6))[order]    # TCP connection attempts only (Jung 2004)
        step = np.where(seen | ~svc, 0.0, np.where(first_contact_failed(df)[order], TRW_STEP, -TRW_STEP))
        s = pd.Series(step)
        walk = s.groupby(go).cumsum()
        peak = np.maximum(walk.groupby(go).transform("max").to_numpy(), 0.0)
        out = np.empty(len(df))
        out[order] = peak
        return {"peak": out}

    def fit_stream(self, benign):
        return self

    def combine(self, f):
        return f["peak"]

    def cells(self, df):
        return gid(df["src_id"].to_numpy(), (df["minute"].to_numpy() // self.W).astype("int64"))

    def fit(self, train, val=None):
        return self


class BruteForce(_Stream):
    """Repeated sessions from one source to one service: flows per (source, destination, port) in the trailing window, scored as
    log10(count / the benign 99.9th-percentile count of that port) (frequent ports have their own reference, the others share one).
    A ratio, not a tail probability: a p-value saturates at 1/N, which favours ports with many benign cells."""
    name = "net.bruteforce"
    key_cols = ("src_id", "dst_id", "dst_port")
    targets = ("FTP-Patator", "SSH-Patator", "Web-BruteForce")
    min_cells = 100

    def feats(self, df, same_network=True):
        k = gid(df["src_id"].to_numpy(), df["dst_id"].to_numpy(), df["dst_port"].to_numpy(), df["protocol"].to_numpy())
        return {"n": trailing(k, df["minute"].to_numpy(), self.W)}

    def _bucket(self, df):
        p = df["dst_port"].to_numpy().astype("int64")
        return np.where(np.isin(p, self.ports), p, -1)

    def fit_stream(self, benign):
        f = self.feats(benign)["n"]
        cell = self.cells(benign)
        p = benign["dst_port"].to_numpy().astype("int64")
        n_c, p_c = unique_cells(cell, f, p)
        vc = pd.Series(p_c).value_counts()
        self.ports = vc.index[vc >= self.min_cells].to_numpy()
        b = np.where(np.isin(p_c, self.ports), p_c, -1)
        self.ref = {int(q): max(float(np.quantile(n_c[b == q], 0.999)), 1.0) for q in np.unique(b)}
        if -1 not in self.ref:
            self.ref[-1] = max(float(np.quantile(n_c, 0.999)), 1.0)
        return self

    def combine(self, f):
        raise RuntimeError("use stream_scores")

    def stream_scores(self, df, same_network=True):
        n = self.feats(df)["n"]
        b = self._bucket(df)
        out = np.zeros(len(df))
        for q in np.unique(b):
            m = b == q
            out[m] = np.log10(np.maximum(n[m], 1.0) / self.ref[int(q)])
        return out

    def fit(self, train, val=None):
        return self.fit_stream(train)


class DosRate(_Stream):
    """Flows per destination in the trailing window as a multiple of that destination's own benign per-minute rate
    (median over its active benign training minutes; < 20 active minutes or unseen destination -> pooled 90th percentile of the baselines)."""
    name = "net.dos_rate"
    key_cols = ("dst_id",)
    targets = ("DoS-Hulk", "DoS-GoldenEye", "DDoS-LOIC-HTTP")
    min_active = 20

    def feats(self, df, same_network=True):
        n = trailing(df["dst_id"].to_numpy(), df["minute"].to_numpy(), self.W)
        base = np.full(len(df), self.pooled)
        if same_network:
            i = np.searchsorted(self.ids, df["dst_id"].to_numpy())
            i = np.clip(i, 0, len(self.ids) - 1)
            hit = self.ids[i] == df["dst_id"].to_numpy()
            base = np.where(hit, self.base[i], base)
        return {"rate": n / self.W, "base": base, "n": n}

    def fit_stream(self, benign):
        g = benign.groupby(["dst_id", "minute"]).size().reset_index(name="c")
        a = g.groupby("dst_id")["c"].agg(["median", "size"])
        a = a[a["size"] >= self.min_active]
        self.ids = a.index.to_numpy()
        self.base = a["median"].to_numpy(float)
        self.pooled = float(np.quantile(self.base, 0.9)) if len(self.base) else 1.0
        return self

    def combine(self, f):
        return np.log((f["rate"] + 1.0) / (f["base"] + 1.0))

    def fit(self, train, val=None):
        return self.fit_stream(train)


class Slow(_Stream):
    """Half-open (no reply) and stalled (>= 5 s, <= 2 packets / s) TCP flows per destination in the trailing window; benign tail probability."""
    name = "net.slow"
    key_cols = ("dst_id",)
    targets = ("DoS-Slowloris", "DoS-SlowHTTPTest")

    def _kinds(self, df):
        fwd, bwd = df["Tot Fwd Pkts"].to_numpy(float), df["Tot Bwd Pkts"].to_numpy(float)
        dur = df["Flow Duration"].to_numpy(float)
        tcp = df["protocol"].to_numpy() == 6
        half = tcp & (bwd == 0)
        stall = tcp & (dur >= DUR_STALL_US) & ((fwd + bwd) / np.maximum(dur / 1e6, 1e-6) <= RATE_STALL)
        return half, stall

    def feats(self, df, same_network=True):
        half, stall = self._kinds(df)
        k, m = df["dst_id"].to_numpy(), df["minute"].to_numpy()
        return {"half": trailing(k, m, self.W, w=half.astype(float)), "stall": trailing(k, m, self.W, w=stall.astype(float))}

    def fit_stream(self, benign):
        f = self.feats(benign)
        cell = self.cells(benign)
        self.t_half = TailTable(unique_cells(cell, f["half"])[0])
        self.t_stall = TailTable(unique_cells(cell, f["stall"])[0])
        return self

    def combine(self, f):
        return np.maximum(self.t_half.score(f["half"]), self.t_stall.score(f["stall"]))

    def fit(self, train, val=None):
        return self.fit_stream(train)


def all_layers(W=None):
    """W: dict layer name -> window minutes (default 1)."""
    W = W or {}
    cls = [Scan, Trw, BruteForce, DosRate, Slow]
    return [c(W=W.get(c.name, 1)) for c in cls]
