"""WP2 S4: DBC parsing and signal decoding for ROAD (no cantools).

Purpose: turn the 8 payload bytes of a frame into the physical-layer signals of anonymized.dbc (Motorola @0 and Intel @1,
unsigned / signed, factor 1, offset 0 in this DBC) so the signal-physics layer (can/l2b_signals.py) can run causally on
raw frames. Checked against the decoded `signal_extractions/*.csv` of ROAD (tools/WP2_S4_decode_check.py).
Inputs: DBC text, payload array (n x 8 uint8) and the frame IDs. Outputs: per ID, a float64 matrix n_id x n_signals.
References: Verma et al. 2022 (ROAD); Verma et al. (CAN-D) for the anonymized DBC.
"""
import re
from pathlib import Path

import numpy as np

from common.config import DATA_EXTRA

DBC = DATA_EXTRA / "road" / "road" / "signal_extractions" / "DBC" / "anonymized.dbc"
_BO = re.compile(r"^BO_\s+(\d+)\s+(\S+):\s+(\d+)")
_SG = re.compile(r"^\s*SG_\s+(\S+)\s*:\s*(\d+)\|(\d+)@([01])([+-])\s*\(([^,]+),([^)]+)\)")


class Sig:
    __slots__ = ("name", "start", "length", "intel", "signed", "factor", "offset", "shift")

    def __init__(self, name, start, length, intel, signed, factor, offset):
        self.name, self.start, self.length = name, start, length
        self.intel, self.signed, self.factor, self.offset = intel, signed, factor, offset
        # position of the signal's LSB in the 64-bit word (Motorola: big-endian word, Intel: little-endian word)
        if intel:
            self.shift = start
        else:
            s = 8 * (start // 8) + (7 - start % 8)          # index of the MSB in the big-endian bit string
            self.shift = 64 - s - length

    def decode(self, B) -> np.ndarray:
        """B: n x 8 uint8 -> float64 values (raw * factor + offset)."""
        if self.intel:
            w = np.zeros(len(B), np.uint64)
            for i in range(8):
                w |= B[:, i].astype(np.uint64) << np.uint64(8 * i)
        else:
            w = np.zeros(len(B), np.uint64)
            for i in range(8):
                w |= B[:, i].astype(np.uint64) << np.uint64(8 * (7 - i))
        v = ((w >> np.uint64(self.shift)) & np.uint64((1 << self.length) - 1)).astype(np.int64)
        if self.signed:
            v = np.where(v >= (1 << (self.length - 1)), v - (1 << self.length), v)
        return v * self.factor + self.offset


def parse_dbc(path: Path = DBC) -> dict:
    """{can id (int): [Sig, ...]} in the order of the DBC (Unknown_0, Unknown_1, ...)."""
    out, cur = {}, None
    for line in open(path):
        m = _BO.match(line)
        if m:
            cur = int(m.group(1))
            out[cur] = []
            continue
        m = _SG.match(line)
        if m and cur is not None:
            out[cur].append(Sig(m.group(1), int(m.group(2)), int(m.group(3)), m.group(4) == "1", m.group(5) == "-",
                                float(m.group(6)), float(m.group(7))))
    return out


def decode_all(ids, B, dbc: dict) -> dict:
    """{id: (row indices of this ID in the capture, n x n_signals float64)} for every ID of the DBC present."""
    ids = np.asarray(ids)
    out = {}
    for i, sigs in dbc.items():
        rows = np.flatnonzero(ids == i)
        if len(rows) == 0 or not sigs:
            continue
        Bi = B[rows]
        out[i] = (rows, np.stack([s.decode(Bi) for s in sigs], axis=1))
    return out
