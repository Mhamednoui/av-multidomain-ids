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
