"""WP4 network domain: the deployable flow-stream detector of M1-NET (Evidence interface of ARCHITECTURE.md section 2).

Purpose: turn a stream of CICFlowMeter-style flow records (with addresses and start times) into one Evidence per flow: per-layer Evidence and one combined Evidence
(domain="network", layer="combined", name="network.combined"). Two stacks:
  H  zero-shot, topology-free: net.tcp_flags (L1), net.scan, net.trw, net.bruteforce (L2a). No learned destination table, no address identity feature; addresses only GROUP flows.
  O  on-network: H + net.dos_rate (online per-destination baseline learned on the target network's warm-up) + net.l3_service + net.l3_ae (refit on the benign warm-up). Needs a warm-up.
Optional layers (net.slow, net.beacon, topology allow-lists, supervised net.l4_xgb) are NOT part of the frozen domain; see reports/M1_NET.md.
Inputs: raw flow DataFrame (columns in RAW_COLUMNS: ts = datetime64 or epoch seconds, src_ip, dst_ip, dst_port, protocol and the CICFlowMeter columns named in network/flows.py;
the 60 clean features are needed only for stack O). `prepare()` makes the stream table (minute, src_id, dst_id, ..., sorted by time) the layers work on.
Outputs: `score_stream(flows)` -> (combined: list[Evidence], per_layer: dict layer name -> list[Evidence]); Evidence.t = flow start (s), score in [0, 1], alarm at the 1% budget of the benign
validation data, reason = behaviour sentence of the firing layers, details = {method, layer_scores, final}, sample_id = row position in the call.
Window semantics (NOT sample-causal): L2a scores a flow by the value of its (key, minute) cell and net.trw by the peak of the walk in its 5-minute bin, so the Evidence of a flow is final only
when its window has closed; `details["final"]` is True when every window containing the flow ended before the last minute of the buffer. Pass a buffer that covers the last >= 5 minutes.
Persistence: save(folder) / load(folder) (pickle of fitted layers + combiner; the Keras autoencoder is stored as weights). Fitted objects are specific to the network they were fitted on
(stack H: D10 = CICIDS2017 lab; stack O: refit on each target network).
References: Jung et al. 2004 (TRW); Sharafaldin et al. 2018 (data); codes_v3 common/combiner.py; ARCHITECTURE.md sections 2-4.
"""
import json
import os
import pickle

import numpy as np
import pandas as pd

from common import combiner as cb
from common.combiner import DomainCombiner
from common.config import BUDGET_DOMAIN
from common.evidence import Evidence
from common.metrics import budget_threshold
from network import l1, l2a, l3

RAW_COLUMNS = ["ts", "src_ip", "dst_ip", "dst_port", "protocol", "Flow Duration", "Tot Fwd Pkts", "Tot Bwd Pkts", "TotLen Fwd Pkts", "TotLen Bwd Pkts",
               "FIN Flag Cnt", "SYN Flag Cnt", "RST Flag Cnt", "PSH Flag Cnt", "ACK Flag Cnt", "URG Flag Cnt", "ECE Flag Cnt"]
STACKS = {"H": ["net.tcp_flags", "net.scan", "net.trw", "net.bruteforce"],
          "O": ["net.tcp_flags", "net.scan", "net.trw", "net.bruteforce", "net.dos_rate", "net.l3_service", "net.l3_ae"]}
WINDOWS = {"net.scan": 1, "net.trw": 5, "net.bruteforce": 1, "net.dos_rate": 1}      # minutes (chosen on D10 validation in S3)
EXPLAIN = {
    "net.tcp_flags": "TCP flag combination (for this packet count) that benign traffic almost never shows (probe or malformed flow)",
    "net.scan": "one source touched an unusual number of distinct ports or hosts within a minute (port / host scan)",
    "net.trw": "one source keeps failing first contacts to new (host, port) pairs (threshold random walk: scanner)",
    "net.bruteforce": "one source opened far more sessions to the same service than benign sources do (login guessing)",
    "net.dos_rate": "flows per minute to one destination far above that destination's learned baseline (flood)",
    "net.l3_service": "flow shape is unusual for the service it goes to (per-service profile of benign flows)",
    "net.l3_ae": "flow shape is poorly reconstructed by an autoencoder trained on benign flows",
}


class _Layers:
    """Builds the layer objects of a stack."""

    @staticmethod
    def make(stack, l3_params=None):
        out = [l1.TcpFlags()] + [c(W=WINDOWS[c.name]) for c in (l2a.Scan, l2a.Trw, l2a.BruteForce)]
        if stack == "O":
            out.append(l2a.DosRate(W=WINDOWS["net.dos_rate"]))
            p = l3_params or {}
            out.append(l3.ServiceProfile(feature_set_name="clean", **p.get("service", {})))
            out.append(l3.AutoEncoder(feature_set_name="clean", **p.get("ae", {})))
        return out


def _col(name):
    return "s_" + name


class NetworkDomain:
    def __init__(self, stack="H", method="max", budget=BUDGET_DOMAIN, l3_params=None):
        assert stack in STACKS
        self.stack, self.method, self.budget, self.l3_params = stack, method, budget, l3_params
        self.layers = _Layers.make(stack, l3_params)
        self.comb = None
        self.ip_ids = {}

    # ------------------------------------------------------------------ stream table
    def _ids(self, ips):
        ids = np.empty(len(ips), "int64")
        for i, ip in enumerate(ips):
            ids[i] = self.ip_ids.setdefault(ip, len(self.ip_ids))
        return ids

    def prepare(self, flows):
        """Raw flows -> stream table sorted by time: minute, t, src_id, dst_id, row (+ all input columns). Addresses become dense ids (kept in the domain so that
        the per-destination baseline of net.dos_rate sees the same id for the same address in fit and in scoring)."""
        f = flows.copy()
        ts = f["ts"]
        t = (ts.astype("int64") / 1e9) if np.issubdtype(ts.dtype, np.datetime64) else ts.astype(float)
        f["t"] = np.asarray(t, float)
        f["minute"] = (f["t"] // 60).astype("int64")
        f["src_id"] = self._ids(f["src_ip"].astype(str).to_numpy())
        f["dst_id"] = self._ids(f["dst_ip"].astype(str).to_numpy())
        f["row"] = np.arange(len(f))
        f["sample_id"] = f["row"].astype(str)
        for c in ("dst_port", "protocol"):
            f[c] = pd.to_numeric(f[c], errors="coerce").fillna(-1).astype("int64")
        return f.sort_values(["t", "row"], kind="stable").reset_index(drop=True)

    # ------------------------------------------------------------------ fitting
    def fit(self, train, val, set_combiner=True):
        """train / val: PREPARED benign streams (warm-up and calibration; no attack label anywhere). Fits every layer on `train`, calibrates it on `val`
        (tie-safe 1% budget). The combined threshold is 1% of the benign `val` combined scores with `self.method` (a learned combiner needs labelled validation attacks:
        use `set_combiner` with an entry chosen elsewhere)."""
        for L in self.layers:
            L.fit(train)
            L.calibrate(val, self.budget)
        if set_combiner:
            X = self._cal_matrix(val)
            s = cb._combine(self.method, X, None)
            self.comb = self._combiner(self.method, None, float(budget_threshold(s, self.budget)))
        return self

    def _combiner(self, method, model, threshold):
        C = DomainCombiner(method=method, budget=self.budget)
        C.layer_names, C.model, C.threshold = sorted(L.name for L in self.layers), model, float(threshold)
        return C

    def set_combiner(self, method, threshold, model=None):
        """Install a combiner chosen elsewhere (e.g. on labelled validation data): method in noisy_or / max / logistic."""
        self.method = method
        self.comb = self._combiner(method, model, threshold)
        return self

    # ------------------------------------------------------------------ scoring
    def _layer_by_name(self):
        return {L.name: L for L in self.layers}

    def raw_matrix(self, stream):
        """dict layer name -> raw score array (stream layers compute their window features on the whole table)."""
        out = {}
        for L in self.layers:
            out[L.name] = np.asarray(L.stream_scores(stream) if hasattr(L, "stream_scores") else L.raw_scores(stream), float)
        return out

    def _cal_matrix(self, stream, raw=None):
        raw = raw or self.raw_matrix(stream)
        by = self._layer_by_name()
        names = sorted(by)
        return np.column_stack([by[n].calibrator.transform(raw[n]) for n in names])

    def score_arrays(self, stream):
        """(combined score, combined alarm, calibrated layer matrix [columns = sorted layer names])."""
        X = self._cal_matrix(stream)
        s = cb._combine(self.comb.method, X, self.comb.model)
        return s, s >= self.comb.threshold, X

    def final_mask(self, stream):
        """True where every window containing the flow has closed before the last minute of the buffer."""
        w = max(WINDOWS[L.name] for L in self.layers if L.name in WINDOWS)
        last = int(stream["minute"].max())
        end = (last // w) * w
        return stream["minute"].to_numpy() < end

    def score_stream(self, flows):
        """Raw flows -> (combined Evidence list, per-layer Evidence dict), in time order of the stream table. Prepares the stream first."""
        stream = self.prepare(flows)
        return self.score_prepared(stream)

    def score_prepared(self, stream):
        raw = self.raw_matrix(stream)
        by = self._layer_by_name()
        names = sorted(by)
        X = np.column_stack([by[n].calibrator.transform(raw[n]) for n in names])
        s = cb._combine(self.comb.method, X, self.comb.model)
        final = self.final_mask(stream)
        t, ids = stream["t"].to_numpy(float), stream["sample_id"].to_numpy()
        per = {}
        for j, n in enumerate(names):
            L = by[n]
            alarm = X[:, j] >= L.threshold
            per[n] = [Evidence(domain="network", layer=L.layer_id, name=n, t=float(t[i]), score=float(X[i, j]), alarm=bool(alarm[i]),
                               reason=("%s." % EXPLAIN.get(n, n)) if alarm[i] else "", details={"raw": float(raw[n][i])}, sample_id=str(ids[i]))
                      for i in range(len(t))]
        out = []
        for i in range(len(t)):
            alarm = bool(s[i] >= self.comb.threshold)
            reason = ""
            if alarm:
                fired = sorted([(X[i, j], n) for j, n in enumerate(names) if X[i, j] >= by[n].threshold], reverse=True)
                if fired:
                    reason = "Network alarm: " + "; ".join(f"{EXPLAIN.get(n, n)} (layer {n}, score {sc:.3f})" for sc, n in fired[:3]) + "."
                else:
                    reason = "Network alarm: no single layer fired, the evidence of several layers adds up."
            out.append(Evidence(domain="network", layer="combined", name="network.combined", t=float(t[i]), score=float(s[i]), alarm=alarm, reason=reason,
                                details={"method": self.comb.method, "layer_scores": {n: float(X[i, j]) for j, n in enumerate(names)}, "final": bool(final[i])},
                                sample_id=str(ids[i])))
        return out, per

    # ------------------------------------------------------------------ persistence
    def save(self, folder):
        os.makedirs(folder, exist_ok=True)
        aes = [L for L in self.layers if isinstance(L, l3.AutoEncoder)]
        weights = [(L, L.model) for L in aes]
        for L in aes:
            L._weights = L.model.get_weights()
            L.model = None
        try:
            with open(os.path.join(folder, "domain.pkl"), "wb") as f:
                pickle.dump(self, f)
        finally:
            for L, m in weights:
                L.model = m
                del L._weights
        info = {"stack": self.stack, "method": self.comb.method, "combined_threshold": self.comb.threshold, "budget": self.budget,
                "layers": {L.name: {"layer_id": L.layer_id, "threshold": float(L.threshold), "W": getattr(L, "W", None)} for L in self.layers}}
        with open(os.path.join(folder, "domain.json"), "w") as f:
            json.dump(info, f, indent=1)

    @staticmethod
    def load(folder):
        with open(os.path.join(folder, "domain.pkl"), "rb") as f:
            d = pickle.load(f)
        for L in d.layers:
            if isinstance(L, l3.AutoEncoder) and getattr(L, "model", 1) is None:
                import tensorflow as tf
                dim = len(L.prep.names)
                m = tf.keras.Sequential([tf.keras.layers.Input((dim,))] + [tf.keras.layers.Dense(h, activation="relu") for h in L.hidden] + [tf.keras.layers.Dense(dim)])
                m.set_weights(L._weights)
                L.model = m
                del L._weights
        return d
