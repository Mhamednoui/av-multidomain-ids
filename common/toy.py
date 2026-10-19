"""Synthetic 3-layer toy domain used by the tests and the S2 report example.

Streams (groups) of samples with 3 hidden attack types; each layer sees a noisy view that is
informative for one or two attack types. Not a dataset: it only exercises the contracts.
Outputs: dict group -> DataFrame (t, f1, f2, f3, y, attack_type), and three Layer subclasses.
"""
import numpy as np
import pandas as pd

from common.layer import Layer
from common.evaluate import EvalSet, score_groups

ATTACKS = ("alpha", "beta", "gamma")


def make_streams(n_groups=6, n=600, seed=0, prefix="g"):
    rng = np.random.RandomState(seed)
    out = {}
    for g in range(n_groups):
        y = np.zeros(n, dtype=int); at = np.array(["normal"] * n, dtype=object)
        for k, a in enumerate(ATTACKS):               # one burst of each attack per stream
            s = 100 + 150 * k + rng.randint(0, 30)
            y[s:s + 40] = 1; at[s:s + 40] = a
        f = rng.normal(0, 1, (n, 3))
        f[at == "alpha", 0] += 3.0; f[at == "alpha", 1] += 1.0
        f[at == "beta", 1] += 3.0
        f[at == "gamma", 2] += 2.5; f[at == "gamma", 0] += 0.8
        out[f"{prefix}{g}"] = pd.DataFrame({"t": np.arange(n, dtype=float), "f1": f[:, 0], "f2": f[:, 1],
                                            "f3": f[:, 2], "y": y, "attack_type": at,
                                            "sample_id": [f"{prefix}{g}:{i}" for i in range(n)]})
    return out


class ToyLayer(Layer):
    domain = "toy"

    def __init__(self, name, col, layer_id, kind="rule"):
        super().__init__()
        self.name, self.col, self.layer_id, self.kind = name, col, layer_id, kind

    def raw_scores(self, samples):
        return samples[self.col].to_numpy()


def toy_layers():
    return [ToyLayer("toy.f1", "f1", "L1"), ToyLayer("toy.f2", "f2", "L2a", "physics"),
            ToyLayer("toy.f3", "f3", "L3", "normal_model")]


def build_evalset(layers, streams) -> EvalSet:
    df = pd.concat(list(streams.values()), ignore_index=True)
    ev = {l.name: score_groups(l, streams) for l in layers}
    groups = np.concatenate([[g] * len(d) for g, d in streams.items()])
    return EvalSet(evidence=ev, y=df["y"].to_numpy(), attack_type=df["attack_type"].to_numpy(),
                   group=groups, t=df["t"].to_numpy())


def toy_run(seed=0):
    """Calibrate layers on normal validation rows, return (val EvalSet, test EvalSet)."""
    val_s = make_streams(6, seed=seed + 1, prefix="v")
    test_s = make_streams(4, seed=seed + 2, prefix="t")
    layers = toy_layers()
    val_all = pd.concat(list(val_s.values()), ignore_index=True)
    for l in layers:
        l.calibrate(val_all[val_all.y == 0])
    return build_evalset(layers, val_s), build_evalset(layers, test_s)
