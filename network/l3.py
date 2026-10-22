"""WP4 L3: normal-only flow models trained on BENIGN training flows only (no attack label is used for fitting).

Purpose: catch flows whose SHAPE is unusual for the service they go to, without any attack example. Three layers on the CICFlowMeter flow features
(network/flows.py, 76 columns, D23 names):
  net.l3_service  per-service profile: services = (protocol, destination port) with >= MIN_SVC benign train flows, the rest pooled by
                  (protocol, port class); per service robust location / scale (median, MAD) of the log-scaled features. Score modes:
                  rz_mean  mean over features of min(|z|, cap)^2          rz_top3  mean of the 3 largest min(|z|, cap)
                  maha     Mahalanobis distance with a shrunk covariance (per service)
                  hbos     histogram outlier score: per service and feature a quantile histogram of the benign values, score = mean over features of
                           -log P(bin | service) (Goldstein and Dengel 2012); catches rare discrete shapes (packet counts) that a distance misses
  net.l3_iforest  isolation forest (Liu et al. 2008) on all flows, no service key
  net.l3_ae       small autoencoder (Keras dense network, input = output), score = mean squared reconstruction error
Feature hygiene (no identity / topology, nothing that identifies the capture instead of the flow): IPs, Flow ID, timestamp and source port are not
features. Set "clean" additionally drops
  HOST_STACK   Init Fwd/Bwd Win Byts, Fwd Seg Size Min: fingerprints of the sender's TCP stack / OS (identify the machine, not the behaviour)
  TOOL_FLAGS   RST / URG / CWE / ECE flag counts, Fwd / Bwd URG flags: columns whose meaning differs between CICFlowMeter versions (D23 RST = ECE column)
  DUPLICATES   columns identical (or exactly proportional) to another kept column (set found on benign train, tools/WP4_S5_explore.py)
and constant columns are dropped at fit time. Set "all" keeps the 76 columns (ablation: what the host-stack columns add).
The destination port / protocol are used ONLY to group services (protocol semantics), never as numeric features.
Inputs: DataFrame with the feature columns and dst_port, protocol. Outputs: raw score (higher = more anomalous); per-flow feature attributions
(contributions) for explaining alarms. Layer contract: common/layer.py (calibration on benign validation, tie-safe 1% budget).
References: Liu, Ting, Zhou 2008 (isolation forest); Mirsky et al. 2018 (Kitsune, autoencoder ensemble for NIDS); Sharafaldin et al. 2018.
"""
import numpy as np
import pandas as pd
from scipy.linalg import solve_triangular
from sklearn.ensemble import IsolationForest

from common.config import SEED
from common.layer import Layer
from network.flows import FEATURES

HOST_STACK = ["Init Fwd Win Byts", "Init Bwd Win Byts", "Fwd Seg Size Min"]
TOOL_FLAGS = ["RST Flag Cnt", "URG Flag Cnt", "CWE Flag Count", "ECE Flag Cnt", "Fwd URG Flags", "Bwd URG Flags"]
# identical / proportional copies of kept columns (CICFlowMeter reports the same quantity twice); filled from the explore step
DUPLICATES = ["Fwd PSH Flags", "Subflow Fwd Pkts", "Subflow Fwd Byts", "Subflow Bwd Pkts", "Subflow Bwd Byts", "Fwd Seg Size Avg", "Bwd Seg Size Avg"]
MIN_SVC = 1000
MIN_GROUP = 200
CLIP = 8.0


def feature_set(name):
    if name == "all":
        return list(FEATURES)
    if name == "clean":
        drop = set(HOST_STACK) | set(TOOL_FLAGS) | set(DUPLICATES)
        return [f for f in FEATURES if f not in drop]
    raise ValueError(name)


def service_key(df):
    """protocol * 100000 + destination port (int64)."""
    return (pd.to_numeric(df["protocol"], errors="coerce").fillna(-1).astype("int64").to_numpy() * 100000
            + pd.to_numeric(df["dst_port"], errors="coerce").fillna(-1).astype("int64").to_numpy())


def bucket_key(pk):
    port, proto = pk % 100000, pk // 100000
    cls = np.where(port < 1024, 0, np.where(port < 49152, 1, 2))
    return 10_000_000 + proto * 10 + cls


class Prep:
    """signed log1p, NaN -> benign-train median, global standardisation (mean / std of the logged benign train values)."""

    def __init__(self, cols):
        self.cols = list(cols)

    @staticmethod
    def _log(x):
        return np.sign(x) * np.log1p(np.abs(x))

    def _x(self, df):
        return self._log(df[self.cols].to_numpy(np.float32))

    def fit(self, df):
        x = self._x(df)
        self.med = np.nanmedian(x, axis=0)
        x = np.where(np.isnan(x), self.med, x)
        self.mu, sd = x.mean(0), x.std(0)
        self.keep = sd > 1e-6                      # constant columns carry nothing
        self.sd = np.where(self.keep, sd, 1.0)
        self.names = [c for c, k in zip(self.cols, self.keep) if k]
        return self

    def transform(self, df, clip=CLIP):
        x = self._x(df)
        x = np.where(np.isnan(x), self.med, x)
        z = ((x - self.mu) / self.sd)[:, self.keep].astype(np.float32)
        return np.clip(z, -clip, clip) if clip else z


class Groups:
    """Service groups of the benign train flows: own group for (protocol, port) with >= MIN_SVC flows, else (protocol, port class) bucket if >= MIN_GROUP, else -1."""

    def fit(self, df):
        pk = service_key(df)
        u, c = np.unique(pk, return_counts=True)
        key = np.where(np.isin(pk, u[c >= MIN_SVC]), pk, bucket_key(pk))
        k, n = np.unique(key, return_counts=True)
        self.keys = np.array(sorted(set(k[n >= MIN_GROUP].tolist()) | {-1}), dtype="int64")
        return self

    def assign(self, df):
        pk = service_key(df)
        key = np.where(np.isin(pk, self.keys), pk, bucket_key(pk))
        return np.where(np.isin(key, self.keys), key, -1)


class ServiceNorm:
    """Per-service calibration of any raw score: score = -log10 of the fraction of that service's benign (held-out) train scores at least as large.
    Every service then spends the same share of the false-alarm budget; a rare service is no longer hidden behind the heavy tail of a busy one."""

    def fit(self, groups, df, raw):
        self.groups = groups
        g = groups.assign(df)
        self.sorted = {int(k): np.sort(raw[g == k]) for k in np.unique(g) if (g == k).sum() >= 100}
        self.sorted[-1] = np.sort(raw)
        return self

    def transform(self, df, raw):
        g = self.groups.assign(df)
        out = np.zeros(len(raw))
        for k in np.unique(g):
            m = g == k
            s = self.sorted.get(int(k), self.sorted[-1])
            n_above = len(s) - np.searchsorted(s, raw[m], side="left")
            out[m] = -np.log10((n_above + 0.5) / (len(s) + 1.0))
        return out


def _sub(df, n, seed=SEED):
    if len(df) <= n:
        return df
    return df.iloc[np.sort(np.random.RandomState(seed).choice(len(df), n, replace=False))]


class _L3(Layer):
    domain, kind, layer_id = "network", "normal_model", "L3"

    def __init__(self, feature_set_name="clean", n_fit=300_000, svc_norm=False):
        super().__init__()
        self.fs, self.n_fit, self.svc_norm = feature_set_name, n_fit, svc_norm
        self.prep = Prep(feature_set(feature_set_name))

    def _split(self, train):
        """(fit rows, held-out rows): the model is fitted on up to n_fit random benign train flows, the per-service normalisation uses up to 300k OTHER ones."""
        perm = np.random.RandomState(SEED).permutation(len(train))
        fit = train.iloc[np.sort(perm[:self.n_fit])]
        held = train.iloc[np.sort(perm[self.n_fit:self.n_fit + 300_000])] if len(train) > self.n_fit + 5000 else fit
        return fit, held

    def _fit_norm(self, train, held):
        if self.svc_norm:
            self.groups = Groups().fit(train)
            self.norm = ServiceNorm().fit(self.groups, held, self._raw(held))
        return self

    def raw_scores(self, samples):
        r = self._raw(samples)
        return self.norm.transform(samples, r) if self.svc_norm else r

    def reasons(self, samples, raw, alarm):
        return [f"{self.name}: the flow shape is far from what benign training flows look like (score {r:.3g})" for r in raw]


class ServiceProfile(_L3):
    name = "net.l3_service"

    def __init__(self, mode="rz_mean", floor=0.1, cap=10.0, shrink=0.2, bins=32, feature_set_name="clean", n_fit=None, svc_norm=False):
        super().__init__(feature_set_name, n_fit or 10**9, svc_norm)
        self.mode, self.floor, self.cap, self.shrink, self.bins = mode, floor, cap, shrink, bins

    def fit(self, train, val=None):
        self.prep.fit(_sub(train, 400_000))
        Z = self.prep.transform(train, clip=CLIP)
        pk = service_key(train)
        u, c = np.unique(pk, return_counts=True)
        own = u[c >= MIN_SVC]
        key = np.where(np.isin(pk, own), pk, bucket_key(pk))
        self.stats = {}
        for k in np.unique(key):
            m = key == k
            if m.sum() >= MIN_GROUP:
                self.stats[int(k)] = self._group(Z[m])
        self.stats[-1] = self._group(Z)
        self.gkeys = np.array(sorted(self.stats), dtype="int64")
        # the profile is fitted on all benign train flows (3 parameters per service and feature): the normalisation uses a 300k sample of the same flows
        return self._fit_norm(train, _sub(train, 300_000, SEED + 1))

    def _group(self, Z):
        med = np.median(Z, axis=0)
        mad = 1.4826 * np.median(np.abs(Z - med), axis=0)
        g = {"n": len(Z), "med": med, "scale": np.maximum(mad, self.floor)}
        if self.mode == "hbos":
            edges, nl = [], []
            for j in range(Z.shape[1]):
                e = np.unique(np.quantile(Z[:, j], np.linspace(0, 1, self.bins + 1)[1:-1]))
                c = np.bincount(np.searchsorted(e, Z[:, j], side="right"), minlength=len(e) + 1).astype(float)
                p = (c + 0.5) / (c.sum() + 0.5 * len(c))
                edges.append(e)
                nl.append(-np.log(p))
            g["edges"], g["nl"] = edges, nl
            g["base"] = np.array([(np.exp(-nl[j]) * nl[j]).sum() for j in range(Z.shape[1])])   # expected term under the benign histogram (entropy)
        if self.mode == "maha":
            S = np.cov(Z.T)
            S = (1 - self.shrink) * S + self.shrink * np.diag(np.diag(S)) + (self.floor ** 2) * np.eye(S.shape[0])
            g["mu"], g["chol"] = Z.mean(0), np.linalg.cholesky(S)
        return g

    def _groups(self, df):
        pk = service_key(df)
        key = np.where(np.isin(pk, self.gkeys), pk, bucket_key(pk))
        return np.where(np.isin(key, self.gkeys), key, -1)

    def _score(self, Z, g, want_contrib):
        if self.mode == "hbos":
            T = np.empty(Z.shape, dtype=np.float32)
            for j in range(Z.shape[1]):
                T[:, j] = g["nl"][j][np.searchsorted(g["edges"][j], Z[:, j], side="right")]
            return T.mean(1), (T - g["base"]) if want_contrib else None
        if self.mode == "maha":
            D = Z - g["mu"]
            w = solve_triangular(g["chol"], D.T, lower=True)              # whitened residual
            d2 = (w ** 2).sum(0)
            if not want_contrib:
                return np.sqrt(d2 / Z.shape[1]), None
            a = solve_triangular(g["chol"].T, w, lower=False)             # Sigma^-1 (x - mu)
            return np.sqrt(d2 / Z.shape[1]), (D * a.T)
        z = np.minimum(np.abs((Z - g["med"]) / g["scale"]), self.cap)
        if self.mode == "rz_mean":
            return (z ** 2).mean(1), z ** 2
        top = np.sort(z, axis=1)[:, -3:].mean(1)
        return top, z

    def _run(self, df, want_contrib=False):
        Z = self.prep.transform(df, clip=None)
        grp = self._groups(df)
        out = np.zeros(len(df))
        con = np.zeros(Z.shape, dtype=np.float32) if want_contrib else None
        for k in np.unique(grp):
            m = grp == k
            s, c = self._score(Z[m], self.stats[int(k)], want_contrib)
            out[m] = s
            if want_contrib:
                con[m] = c
        return out, con

    def _raw(self, samples):
        return self._run(samples)[0]

    def contributions(self, samples):
        """(n, d) matrix of per-feature contributions to the score and the feature names."""
        return self._run(samples, True)[1], self.prep.names


class IsoForest(_L3):
    name = "net.l3_iforest"

    def __init__(self, max_samples=256, max_features=1.0, n_estimators=200, feature_set_name="clean", n_fit=300_000, svc_norm=False):
        super().__init__(feature_set_name, n_fit, svc_norm)
        self.max_samples, self.max_features, self.n_estimators = max_samples, max_features, n_estimators

    def fit(self, train, val=None):
        tr, held = self._split(train)
        self.prep.fit(tr)
        self.model = IsolationForest(n_estimators=self.n_estimators, max_samples=self.max_samples, max_features=self.max_features,
                                     random_state=SEED, n_jobs=4).fit(self.prep.transform(tr))
        return self._fit_norm(train, held)

    def _raw(self, samples):
        Z = self.prep.transform(samples)
        return np.concatenate([-self.model.score_samples(Z[i:i + 200_000]) for i in range(0, len(Z), 200_000)])

    def contributions(self, samples, max_n=300):
        """Occlusion attribution: score drop when one feature is replaced by its benign median (0 after standardisation). Up to max_n flows."""
        Z = self.prep.transform(samples)[:max_n]
        n, d = Z.shape
        base = -self.model.score_samples(Z)
        out = np.zeros((n, d), dtype=np.float32)
        med0 = (self.prep.med[self.prep.keep] - self.prep.mu[self.prep.keep]) / self.prep.sd[self.prep.keep]
        for j in range(d):
            Zj = Z.copy()
            Zj[:, j] = med0[j]
            out[:, j] = base + self.model.score_samples(Zj)
        return out, self.prep.names


class AutoEncoder(_L3):
    """Dense autoencoder (Keras, CPU; the installed TensorFlow 2.10 has no GPU libraries). Trained with MSE on benign train flows only;
    the first version used sklearn MLPRegressor (identical architecture, 27 min per fit on the shared CPU, results/WP4/logs/s5_dev_pass1_sklearn_ae.log)."""
    name = "net.l3_ae"

    def __init__(self, hidden=(32, 12, 32), epochs=60, batch=1024, feature_set_name="clean", n_fit=300_000, svc_norm=False):
        super().__init__(feature_set_name, n_fit, svc_norm)
        self.hidden, self.epochs, self.batch = tuple(hidden), epochs, batch

    def fit(self, train, val=None):
        import tensorflow as tf
        tf.keras.utils.set_random_seed(SEED)
        tr, held = self._split(train)
        self.prep.fit(tr)
        Z = self.prep.transform(tr)
        d = Z.shape[1]
        layers = [tf.keras.layers.Input((d,))] + [tf.keras.layers.Dense(h, activation="relu") for h in self.hidden] + [tf.keras.layers.Dense(d)]
        self.model = tf.keras.Sequential(layers)
        self.model.compile(optimizer=tf.keras.optimizers.Adam(1e-3), loss="mse")
        cb = tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=5, min_delta=1e-5, restore_best_weights=True)
        h = self.model.fit(Z, Z, batch_size=self.batch, epochs=self.epochs, validation_split=0.1, shuffle=True, callbacks=[cb], verbose=0)
        self.epochs_run = len(h.history["loss"])
        return self._fit_norm(train, held)

    def _raw(self, samples):
        return self.contributions(samples)[0].mean(1)

    def contributions(self, samples):
        Z = self.prep.transform(samples)
        err = np.concatenate([(self.model.predict(Z[i:i + 65536], batch_size=65536, verbose=0) - Z[i:i + 65536]) ** 2 for i in range(0, len(Z), 65536)])
        return err.astype(np.float32), self.prep.names
