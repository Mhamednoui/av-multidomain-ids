"""Group splits for V2X (WP5 S1): never by message.

VeReMi (D12): the combined CSV has no simulation / run id and no receiver id. Findings (see
reports/WP5_S1.md): one 24 h timeline (sendTime 240..86400 s), every sender is one vehicle with
one class and a short life (median ~110 s), sender ids grow with departure time (Spearman 1.0).
So separate runs cannot be recovered; the best available grouping is a TIME BLOCK: senders are
assigned to a block of `block_s` seconds by their first message; a sender whose messages cross
the block end is dropped (guard), so no sender in one block is ever on air at the same time as a
sender of the next block. Blocks are shuffled into train / val / test (60/20/20, fixed seed).
Residual leakage risk: same road network and same day-time traffic pattern in all parts, and
attackers of all classes are interleaved in the same traffic as genuine senders.

Tampa (D14): split by vehicle id (60/20/20). The id is the J2735 temporary id; it may rotate, so
one physical car can appear under two ids (cannot be checked: no VIN); the leakage risk is small.
"""
import numpy as np
import pandas as pd

from common.config import SEED
from common.splits import group_split

BLOCK_S = 1800.0


def veremi_time_block_split(df: pd.DataFrame, block_s: float = BLOCK_S, seed: int = SEED):
    """Returns (split {train,val,test: [sender ids]}, info dict). Dropped senders listed in info."""
    life = df.groupby("sender")["t"].agg(["min", "max"])
    b0 = np.floor(life["min"] / block_s).astype(int)
    b1 = np.floor(life["max"] / block_s).astype(int)
    keep = b0 == b1
    blocks = group_split([str(b) for b in sorted(set(b0[keep]))], seed=seed)
    part_of_block = {b: p for p, bs in blocks.items() for b in bs}
    split = {p: [] for p in blocks}
    for s in life.index[keep]:
        split[part_of_block[str(b0[s])]].append(str(s))
    split = {p: sorted(v) for p, v in split.items()}
    info = {"block_s": block_s, "n_blocks": int(b0[keep].nunique()),
            "blocks": blocks, "n_senders": int(len(life)),
            "n_dropped_straddling": int((~keep).sum()),
            "dropped_senders": sorted(map(str, life.index[~keep]))}
    return split, info


def tampa_vehicle_split(df: pd.DataFrame, seed: int = SEED) -> dict:
    return group_split(df["sender"].unique(), seed=seed)


def rows_of(df: pd.DataFrame, ids, col: str = "sender") -> pd.DataFrame:
    return df[df[col].isin(set(map(str, ids)))]


# ---------------------------------------------------------------------------------------------------------------
# Tampa v2 (WP5 S1b): the public sample has 40 passages of 38 physical vehicles in 13 bursts, so a fixed time grid would drop
# the biggest vehicle. Blocks = EPISODES: maximal groups of passages whose lives, extended by GUARD_S on both sides, overlap or
# touch. Cuts lie only where no passage is alive on either side, with a 2 x GUARD_S silence between any two parts.
GUARD_S = 30.0


def tampa_episodes(df: pd.DataFrame, guard: float = GUARD_S, vehicle_of: dict = None) -> pd.Series:
    """Episode index (0..) of every sender (passage) of df, from the sender lives extended by `guard` s.
    vehicle_of (passage -> physical vehicle): episodes that contain passages of the same physical vehicle are merged into one block,
    so no physical vehicle is ever on two sides of the split."""
    life = df.groupby("sender")["t"].agg(["min", "max"]).sort_values("min")
    ep, cur, k = {}, -np.inf, -1
    for s, r in life.iterrows():
        if r["min"] - guard > cur + guard:       # silence longer than 2 x guard: new episode
            k += 1
        ep[s] = max(k, 0)
        cur = max(cur, r["max"])
    ep = pd.Series(ep)
    if vehicle_of:
        parent = {e: e for e in ep.unique()}

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        first = {}
        for s, e in ep.items():
            v = vehicle_of.get(s)
            if v is None:
                continue
            if v in first:
                parent[find(e)] = find(first[v])
            else:
                first[v] = e
        roots = {r: i for i, r in enumerate(sorted({find(e) for e in ep.unique()}))}
        ep = ep.map(lambda e: roots[find(e)])
    return ep


def tampa_time_block_split(df: pd.DataFrame, seed: int = SEED, guard: float = GUARD_S, vehicle_of: dict = None):
    """Returns (split {train,val,test: [sender ids]}, info). Episodes are shuffled 60/20/20 with the seed."""
    ep = tampa_episodes(df, guard, vehicle_of)
    blocks = group_split([str(b) for b in sorted(ep.unique())], seed=seed)
    part_of = {b: p for p, bs in blocks.items() for b in bs}
    split = {p: [] for p in blocks}
    for s, e in ep.items():
        split[part_of[str(e)]].append(str(s))
    split = {p: sorted(v) for p, v in split.items()}
    return split, {"guard_s": guard, "n_episodes": int(ep.nunique()), "episodes": blocks, "seed": seed,
                   "episode_of_sender": {str(k): int(v) for k, v in ep.items()}}


def min_gap_between_parts(df: pd.DataFrame, split: dict) -> dict:
    """Smallest time distance (s) between the life of a sender of one part and the life of a sender of another part
    (negative = they are alive at the same time)."""
    life = df.groupby("sender")["t"].agg(["min", "max"])
    out = {}
    for a, b in (("train", "val"), ("train", "test"), ("val", "test")):
        la, lb = life.loc[split[a]], life.loc[split[b]]
        best = np.inf
        for s0, s1 in zip(la["min"].to_numpy(), la["max"].to_numpy()):
            gap = np.maximum(lb["min"].to_numpy() - s1, s0 - lb["max"].to_numpy())
            best = min(best, float(gap.min()))
        out[f"{a}-{b}"] = best
    return out
