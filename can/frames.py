"""Unified CAN frame format of v3 (WP2 S1).

One frame table = one capture = one pandas DataFrame, rows in RECORDED order (never re-sorted):
  t        float64  seconds since the first frame of the capture
  id       int32    arbitration ID
  dlc      int8     number of data bytes
  b0..b7   int16    data bytes, -1 where the byte does not exist (beyond the DLC)
  label    int8     1 = injected frame, 0 = normal
  attack   category "normal" or the attack name (ROAD masquerade: "<family>_masquerade")
  capture  category capture / file id
  vehicle  category vehicle name; "<set>:known" style only where the vehicle is not known per file
Inputs: raw hex strings or arrays. Outputs: DataFrames and helpers. No dataset specifics here.
"""
import numpy as np
import pandas as pd

BYTE_COLS = [f"b{i}" for i in range(8)]
COLUMNS = ["t", "id", "dlc"] + BYTE_COLS + ["label", "attack", "capture", "vehicle"]


_HEXVAL = np.full(256, 255, dtype=np.uint8)
for _i, _c in enumerate("0123456789abcdef"):
    _HEXVAL[ord(_c)] = _i
    _HEXVAL[ord(_c.upper())] = _i


def hex_to_bytes(payloads) -> tuple:
    """Hex payload strings (no separators) -> (dlc int8 array, B int16 array (n, 8), -1 beyond DLC).
    Trailing whitespace (a tab occurs in D11) is dropped. Odd length, > 8 bytes, a non-hex
    character or whitespace in the middle raise ValueError. Vectorised (fixed-width bytes)."""
    arr = np.asarray(list(payloads) if not isinstance(payloads, (pd.Series, np.ndarray)) else payloads,
                     dtype=object).astype("S18")
    M = np.frombuffer(arr.tobytes(), dtype=np.uint8).reshape(len(arr), 18).copy()
    ws = np.isin(M, (9, 10, 13, 32))
    M[ws] = 0
    nz = M != 0
    n = nz.sum(axis=1)
    last = np.where(nz.any(axis=1), 18 - np.argmax(nz[:, ::-1], axis=1), 0)
    if (last != n).any():
        raise ValueError("whitespace inside a payload")
    if (n % 2).any():
        raise ValueError("odd-length hex payload")
    if (n > 16).any():
        raise ValueError("payload longer than 8 bytes")
    V = _HEXVAL[M[:, :16]]
    if ((V == 255) & nz[:, :16]).any():
        raise ValueError("non-hex character in payload")
    B = (V[:, 0::2].astype(np.int16) << 4) | V[:, 1::2].astype(np.int16)
    dlc = (n // 2).astype(np.int8)
    B[np.arange(8)[None, :] >= dlc[:, None]] = -1
    return dlc, B


def bytes_to_hex(dlc, B) -> np.ndarray:
    """Inverse of hex_to_bytes: upper-case hex string per frame (numpy 'U16' array, vectorised)."""
    B = np.asarray(B)
    dlc = np.asarray(dlc)
    Bc = np.where(B < 0, 0, B).astype(np.uint8)
    digits = np.frombuffer(b"0123456789ABCDEF", dtype=np.uint8)
    M = np.empty((len(Bc), 16), dtype=np.uint8)
    M[:, 0::2] = digits[Bc >> 4]
    M[:, 1::2] = digits[Bc & 15]
    M[np.repeat(np.arange(8)[None, :] >= dlc[:, None], 2, axis=1)] = 0
    return np.ascontiguousarray(M).view("S16").ravel().astype("U16")


def make_frame(t, ids, dlc, B, label, attack, capture, vehicle) -> pd.DataFrame:
    """Assemble a frame table. attack / capture / vehicle may be scalars or per-frame arrays."""
    n = len(t)
    df = pd.DataFrame({"t": np.asarray(t, dtype=np.float64), "id": np.asarray(ids, dtype=np.int32),
                       "dlc": np.asarray(dlc, dtype=np.int8)})
    B = np.asarray(B, dtype=np.int16)
    for i, c in enumerate(BYTE_COLS):
        df[c] = B[:, i]
    df["label"] = np.asarray(label, dtype=np.int8)
    for name, v in (("attack", attack), ("capture", capture), ("vehicle", vehicle)):
        arr = np.full(n, v, dtype=object) if np.isscalar(v) else np.asarray(v, dtype=object)
        df[name] = pd.Categorical(arr)
    return df


def validate_frame(df: pd.DataFrame) -> dict:
    """Check the format contract; raise ValueError on a violation, return small stats."""
    if list(df.columns) != COLUMNS:
        raise ValueError(f"columns {list(df.columns)}")
    if len(df) == 0:
        raise ValueError("empty capture")
    if not np.isfinite(df["t"].to_numpy()).all():
        raise ValueError("non-finite t")
    B = df[BYTE_COLS].to_numpy()
    dlc = df["dlc"].to_numpy()
    if dlc.min() < 0 or dlc.max() > 8:
        raise ValueError("dlc outside 0..8")
    exists = np.arange(8)[None, :] < dlc[:, None]
    if ((B >= 0) != exists).any():
        raise ValueError("byte present beyond DLC or absent within DLC")
    if B.max() > 255:
        raise ValueError("byte > 255")
    if not set(np.unique(df["label"].to_numpy())) <= {0, 1}:
        raise ValueError("label not in {0,1}")
    if ((df["attack"].astype(str) == "normal").to_numpy() != (df["label"].to_numpy() == 0)).any():
        raise ValueError("attack name and label disagree")
    if df["id"].min() < 0:
        raise ValueError("negative id")
    return {"frames": len(df), "injected": int(df["label"].sum()),
            "negative_dt": int((np.diff(df["t"].to_numpy()) < 0).sum())}


def dt_clipped(t) -> np.ndarray:
    """Inter-frame gap with negative values (timestamp rounding inversions) clipped to 0.
    First element is NaN. Use this instead of re-sorting when the recorded order must stay."""
    d = np.diff(np.asarray(t, dtype=np.float64), prepend=np.nan)
    return np.where(d < 0, 0.0, d)
