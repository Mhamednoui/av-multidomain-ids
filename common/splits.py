"""Group-aware split helpers: splits are lists of group ids (drive, session, capture), never rows.

Inputs: group ids. Outputs: dict of id lists; JSON save / load (results/<WP>/splits.json).
Reference: RULES.md section 5.1, ARCHITECTURE.md section 4.
"""
import json
from pathlib import Path

import numpy as np

from common.config import SEED


def group_split(groups, fractions=(0.6, 0.2, 0.2), names=("train", "val", "test"), seed=SEED) -> dict:
    """Shuffle unique groups, cut by fractions. Every group lands in exactly one part."""
    ids = sorted(set(map(str, groups)))
    if len(ids) < len(names):
        raise ValueError("fewer groups than parts")
    rng = np.random.RandomState(seed)
    rng.shuffle(ids)
    cuts = np.round(np.cumsum(fractions)[:-1] * len(ids)).astype(int)
    parts = np.split(np.array(ids, dtype=object), cuts)
    out = {n: sorted(p.tolist()) for n, p in zip(names, parts)}
    if any(len(v) == 0 for v in out.values()):
        raise ValueError("a part is empty: too few groups for these fractions")
    check_disjoint(out)
    return out


def group_halves(groups, seed=SEED):
    """Two disjoint group-id lists of (nearly) equal size, for combiner / fusion validation halves."""
    ids = sorted(set(map(str, groups)))
    if len(ids) < 2:
        raise ValueError("need at least 2 groups")
    rng = np.random.RandomState(seed)
    rng.shuffle(ids)
    h = len(ids) // 2
    return sorted(ids[:h]), sorted(ids[h:])


def check_disjoint(split: dict):
    seen = {}
    for part, ids in split.items():
        for g in ids:
            if g in seen:
                raise ValueError(f"group {g!r} in both {seen[g]} and {part}")
            seen[g] = part


def mask(groups, ids):
    """Boolean mask of the rows whose group is in `ids`."""
    s = set(map(str, ids))
    return np.array([str(g) in s for g in groups], dtype=bool)


def save_splits(split: dict, path):
    check_disjoint(split)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps({k: list(map(str, v)) for k, v in split.items()}, indent=1))


def load_splits(path) -> dict:
    d = json.loads(Path(path).read_text())
    check_disjoint(d)
    return d
