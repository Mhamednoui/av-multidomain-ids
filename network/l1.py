"""WP4 L1: network rule layers learned from BENIGN training flows (flow level, CICFlowMeter tables of network/flows.py).

Purpose: cheap, explainable checks that need no attack data.
  net.allow_pair     (src, dst, port/proto) novelty with back-off to (dst, port/proto) and port/proto  (host/service allow-list)
  net.allow_service  (dst, port/proto) novelty, no source identity (what a real, never-seen attacker address cannot hide)
  net.proto_port     P(protocol | port) learned + hard limits: port 0 (RFC 6335 s6), protocol outside the learned set,
                     TCP header 20..60 B per packet (RFC 9293 s3.1), UDP header >= 8 B (RFC 768), IPv4 packet <= 65535 B (RFC 791),
                     min <= max length, no negative duration, at least one forward packet
  net.tcp_flags      rarity of the TCP flag combination given packet count / reply seen (null, XMAS-like, SYN+FIN ...), plus hard rule:
                     a single-packet flow cannot carry two of SYN / FIN / RST (RFC 9293 s3.5, s3.10)
  net.flow_rate      packets / bytes per second of the flow (zero-duration flows with many packets rank highest)
Inputs: DataFrames with the columns of the cached tables (src_ip, dst_ip, dst_port, protocol, flag counts, packet counts, header
lengths, durations). Missing IPs (most of D23): the allow-list layers need them and raise.
Outputs: raw scores (higher = more attack-like); calibration / threshold / Evidence from common.layer.Layer.
References: Witten and Bell 1991 (back-off smoothing); Sharafaldin et al. 2018 (CICIDS2017 flows); RFCs as cited above.
Notes: the CICFlowMeter flag columns are 0/1 presence flags in D10 (several are known tool artefacts), so flag combinations are scored
by their benign frequency, not by per-packet RFC logic, except for the single-packet case.
"""
import numpy as np
import pandas as pd

from common.layer import Layer

KNOWN_PROTOS = (0, 1, 6, 17)
FLAGS = ["SYN Flag Cnt", "FIN Flag Cnt", "RST Flag Cnt", "ACK Flag Cnt", "PSH Flag Cnt", "URG Flag Cnt", "ECE Flag Cnt"]


def _h(df, cols):
    return pd.util.hash_pandas_object(df[cols], index=False).to_numpy()


class _Counts:
    """Frequency table over hashed key columns (vectorised lookup, 0 for unseen keys)."""

    def __init__(self, df, cols):
        self.cols = cols
        self.keys, self.cnt = np.unique(_h(df, cols), return_counts=True)

    def get(self, df):
        h = _h(df, self.cols)
        i = np.clip(np.searchsorted(self.keys, h), 0, len(self.keys) - 1)
        return np.where(self.keys[i] == h, self.cnt[i], 0).astype(float)


def pk(df):
    """port/protocol key: protocol * 100000 + destination port."""
    return (pd.to_numeric(df["protocol"], errors="coerce").fillna(-1).astype("int64") * 100000
            + pd.to_numeric(df["dst_port"], errors="coerce").fillna(-1).astype("int64"))


def _need_ips(df):
    if "src_ip" not in df.columns or df["src_ip"].isna().all():
        raise ValueError("allow-list layers need src_ip / dst_ip (D23: only Tuesday 20-02 has them)")


class _AllowBase(Layer):
    domain, kind, layer_id = "network", "rule", "L1"
    use_src = True
    min_support = 10000        # an address is a "known host" if it appears in >= this many benign train flows
    rare_port = 1000            # port/proto seen in fewer benign train flows is pooled into its class bucket (random high ports are normal)

    def __init__(self, rare_port=None):
        super().__init__()
        self.known = None
        if rare_port is not None:
            self.rare_port = rare_port

    def _keys(self, df):
        p = pk(df).to_numpy()
        port, proto = p % 100000, p // 100000
        cls = np.where(port < 1024, 0, np.where(port < 49152, 1, 2))
        p = np.where(np.isin(p, self.freq_pk), p, 10_000_000 + proto * 10 + cls)
        k = pd.DataFrame({"pk": p})
        ips = lambda c: df[c].astype(str).where(df[c].astype(str).isin(self.known), "OTHER").to_numpy()
        k["dst"] = ips("dst_ip")
        if self.use_src:
            k["src"] = ips("src_ip")
        return k

    def fit(self, train, val=None):
        _need_ips(train)
        both = pd.concat([train["src_ip"].astype(str), train["dst_ip"].astype(str)]).value_counts()
        self.known = set(both[both >= self.min_support].index)
        u, c = np.unique(pk(train).to_numpy(), return_counts=True)
        self.freq_pk = u[c >= self.rare_port]
        k = self._keys(train)
        self.n = float(len(k))
        self.c_pk, self.n_pk = _Counts(k, ["pk"]), k["pk"].nunique()
        self.c_dp = _Counts(k, ["dst", "pk"])
        self.c_3 = _Counts(k, ["src", "dst", "pk"]) if self.use_src else None
        return self

    def raw_scores(self, samples):
        _need_ips(samples)
        k = self._keys(samples)
        p1 = (self.c_pk.get(k) + 0.5) / (self.n + 0.5 * (self.n_pk + 1))
        p = (self.c_dp.get(k) + p1) / (self.n + 1.0)
        if self.use_src:
            p = (self.c_3.get(k) + p) / (self.n + 1.0)
        return -np.log10(p)

    def reasons(self, samples, raw, alarm):
        s = samples
        what = "(source, destination, port)" if self.use_src else "(destination, port)"
        return [f"{what} combination {a}->{b}:{int(p)} is rare or never seen in benign training traffic"
                for a, b, p in zip(s["src_ip"], s["dst_ip"], s["dst_port"])]


class AllowPair(_AllowBase):
    name = "net.allow_pair"
    use_src = True


class AllowService(_AllowBase):
    name = "net.allow_service"
    use_src = False


def hard_violations(df, known_protos=KNOWN_PROTOS):
    """Count of impossible / reserved-value violations per flow (limits cited in the module docstring)."""
    proto = pd.to_numeric(df["protocol"], errors="coerce").to_numpy()
    port = pd.to_numeric(df["dst_port"], errors="coerce").to_numpy()
    nf, nb = df["Tot Fwd Pkts"].to_numpy(float), df["Tot Bwd Pkts"].to_numpy(float)
    hf, hb = df["Fwd Header Len"].to_numpy(float), df["Bwd Header Len"].to_numpy(float)
    tcp, udp = proto == 6, proto == 17
    v = np.zeros(len(df))
    v += ((tcp | udp) & (port == 0))                                          # RFC 6335 s6: port 0 is reserved
    v += ~np.isin(proto, known_protos)
    v += tcp & ((hf < 20 * nf) | (hf > 60 * nf) | ((nb > 0) & ((hb < 20 * nb) | (hb > 60 * nb))))   # RFC 9293 s3.1
    v += udp & ((hf < 8 * nf) | ((nb > 0) & (hb < 8 * nb)))                   # RFC 768
    v += (df["Pkt Len Max"].to_numpy(float) > 65535) | (df["TotLen Fwd Pkts"].to_numpy(float) > 65535 * np.maximum(nf, 1))   # RFC 791
    v += df["Fwd Pkt Len Min"].to_numpy(float) > df["Fwd Pkt Len Max"].to_numpy(float)
    v += df["Flow Duration"].to_numpy(float) < 0
    v += nf < 1
    return v


class ProtoPort(Layer):
    domain, kind, layer_id, name = "network", "rule", "L1", "net.proto_port"

    def fit(self, train, val=None):
        d = pd.DataFrame({"port": pd.to_numeric(train["dst_port"], errors="coerce").fillna(-1).astype("int64").to_numpy(),
                          "proto": pd.to_numeric(train["protocol"], errors="coerce").fillna(-1).astype("int64").to_numpy()})
        d["cls"] = self._cls(d["port"])
        self.c_pp, self.c_p = _Counts(d, ["port", "proto"]), _Counts(d, ["port"])
        self.c_cp, self.c_c = _Counts(d, ["cls", "proto"]), _Counts(d, ["cls"])
        self.protos = tuple(sorted(set(d["proto"]) | {6, 17}))
        return self

    @staticmethod
    def _cls(p):
        return np.where(p < 1024, 0, np.where(p < 49152, 1, 2))

    def soft(self, df):
        d = pd.DataFrame({"port": pd.to_numeric(df["dst_port"], errors="coerce").fillna(-1).astype("int64").to_numpy(),
                          "proto": pd.to_numeric(df["protocol"], errors="coerce").fillna(-1).astype("int64").to_numpy()})
        d["cls"] = self._cls(d["port"])
        q = (self.c_cp.get(d) + 0.5) / (self.c_c.get(d) + 1.5)
        p = (self.c_pp.get(d) + 2.0 * q) / (self.c_p.get(d) + 2.0)
        return -np.log10(p)

    def raw_scores(self, samples):
        return self.soft(samples) + 5.0 * hard_violations(samples, self.protos)

    def reasons(self, samples, raw, alarm):
        return [f"protocol {int(p)} on port {int(q)} (or an impossible header/length value) is rare or never seen in benign traffic"
                for p, q in zip(samples["protocol"], samples["dst_port"])]


def flag_combo(df):
    c = np.zeros(len(df), dtype=np.int64)
    for i, f in enumerate(FLAGS):
        c += (df[f].to_numpy(float) > 0).astype(np.int64) << i
    return c


class TcpFlags(Layer):
    domain, kind, layer_id, name = "network", "rule", "L1", "net.tcp_flags"

    def _keys(self, df):
        n = (df["Tot Fwd Pkts"] + df["Tot Bwd Pkts"]).to_numpy(float)
        b = np.digitize(n, [2, 3, 6])
        return pd.DataFrame({"combo": flag_combo(df), "b": b, "rep": (df["Tot Bwd Pkts"].to_numpy(float) > 0).astype(int)})

    def fit(self, train, val=None):
        t = train[pd.to_numeric(train["protocol"], errors="coerce") == 6]
        k = self._keys(t)
        self.n = float(len(k))
        self.c_c, self.c_j = _Counts(k, ["combo"]), _Counts(k, ["combo", "b", "rep"])
        return self

    def raw_scores(self, samples):
        tcp = (pd.to_numeric(samples["protocol"], errors="coerce") == 6).to_numpy()
        k = self._keys(samples)
        pc = (self.c_c.get(k) + 0.5) / (self.n + 64.0)
        p = (self.c_j.get(k) + pc) / (self.n + 1.0)
        n = (samples["Tot Fwd Pkts"] + samples["Tot Bwd Pkts"]).to_numpy(float)
        two = sum((samples[f].to_numpy(float) > 0).astype(int) for f in ("SYN Flag Cnt", "FIN Flag Cnt", "RST Flag Cnt")) >= 2
        viol = (n == 1) & two                                                     # RFC 9293 s3.5 / s3.10
        return np.where(tcp, -np.log10(p) + 5.0 * viol, 0.0)

    def reasons(self, samples, raw, alarm):
        return ["TCP flag combination (with this packet count) is rare or never seen in benign traffic, or a single packet carries SYN/FIN/RST together"
                for _ in range(len(samples))]


class FlowRate(Layer):
    domain, kind, layer_id, name = "network", "rule", "L1", "net.flow_rate"

    def raw_scores(self, samples):
        n = (samples["Tot Fwd Pkts"] + samples["Tot Bwd Pkts"]).to_numpy(float)
        byt = (samples["TotLen Fwd Pkts"] + samples["TotLen Bwd Pkts"]).to_numpy(float)
        dur = np.maximum(samples["Flow Duration"].to_numpy(float), 1.0) / 1e6      # microseconds -> s, floor 1 us
        pps = np.log10(np.maximum(n, 1) / dur)
        bps = np.log10(np.maximum(byt, 1) / dur)
        return np.where(n >= 2, np.maximum(pps, bps - 2.0), 0.0)

    def reasons(self, samples, raw, alarm):
        return ["packets / bytes per second of this flow are far above anything seen in benign traffic (or many packets in zero duration)"
                for _ in range(len(samples))]


def all_layers():
    return [AllowPair(), AllowService(), ProtoPort(), TcpFlags(), FlowRate()]
