"""WP6 S3: per-domain 1 Hz tick series, the common format the system fusion and the composite builder read.

A domain pack is a dict:
  domain       "gps" | "can" | "network" | "v2x" | "lidar" | "cross_kitti" | "cross_comma"
  layer_names  names of the domain's layers (cross: its witness edges)
  layer_thr    the layers' own thresholds on their calibrated scores (array, same order)
  dom_thr      the domain's own combined threshold (1% budget, set by the domain owner)
  series       list of dicts: group (split unit), name, kind ("clean" | "attack"), family ("none" for clean), score (n,) float32 = domain
               combined score of the tick, layers (n, m) float32, label (n,) bool = attack active in that tick, fam (n,) object (attack family
               per tick, "" when none), blame (n,) object or None (cross only: blamed domain, "undecided" or None), onset (tick index or -1)
A tick is one second of the system clock; a domain with several samples per second (LiDAR scans, V2X messages, network flows) contributes
the per-layer maximum of the samples of that second (tick_max); seconds without a sample have score 0 (no evidence).
Reference: notes/WP6_crossdomain.md "S3 start"; ARCHITECTURE.md sections 2-4.
"""
import numpy as np


def tick_max(k, values, n):
    """k: tick index per sample (int, 0..n-1), values: (N,) or (N, m) -> (n,) or (n, m) maximum per tick, 0 where no sample."""
    v = np.asarray(values, np.float32)
    shape = (n,) + v.shape[1:]
    out = np.zeros(shape, np.float32)
    k = np.asarray(k, np.int64)
    ok = (k >= 0) & (k < n)
    np.maximum.at(out, k[ok], v[ok])
    return out


def tick_any(k, flags, n):
    out = np.zeros(n, bool)
    k = np.asarray(k, np.int64)
    ok = (k >= 0) & (k < n) & np.asarray(flags, bool)
    out[k[ok]] = True
    return out


def tick_family(k, fam, n):
    """Most frequent non-empty family per tick ('' when none)."""
    out = np.full(n, "", object)
    k = np.asarray(k, np.int64)
    fam = np.asarray(fam, object)
    m = (fam != "") & (k >= 0) & (k < n)
    if not m.any():
        return out
    kk, ff = k[m], fam[m]
    order = np.lexsort((ff.astype(str), kk))
    kk, ff = kk[order], ff[order]
    best = {}
    i = 0
    while i < len(kk):
        j = i
        while j < len(kk) and kk[j] == kk[i]:
            j += 1
        vals, cnt = np.unique(ff[i:j].astype(str), return_counts=True)
        best[kk[i]] = vals[int(np.argmax(cnt))]
        i = j
    for a, b in best.items():
        out[a] = b
    return out


def series(group, name, kind, family, score, layers, label, fam=None, blame=None):
    score = np.asarray(score, np.float32)
    label = np.asarray(label, bool)
    n = len(score)
    if fam is None:
        fam = np.where(label, family, "").astype(object)
    on = np.flatnonzero(label)
    return {"group": str(group), "name": str(name), "kind": kind, "family": family, "score": score,
            "layers": np.asarray(layers, np.float32).reshape(n, -1), "label": label, "fam": np.asarray(fam, object),
            "blame": blame, "onset": int(on[0]) if len(on) else -1}


def hold_minutes(minute_idx, values, labels, fams, t0_min, t1_min):
    """Network: per-minute values -> per-second ticks over [t0_min, t1_min] minutes; the value of a closed minute m is held during minute
    m + 1 (Evidence final when its minute closes). Returns (ticks values (n, m), label (n,), fam (n,)) with n = 60 * (t1_min - t0_min + 1)."""
    nmin = t1_min - t0_min + 1
    V = np.zeros((nmin,) + np.asarray(values).shape[1:], np.float32)
    L = np.zeros(nmin, bool)
    F = np.full(nmin, "", object)
    j = np.asarray(minute_idx, np.int64) - t0_min + 1              # shown one minute later
    ok = (j >= 0) & (j < nmin)
    V[j[ok]] = np.asarray(values, np.float32)[ok]
    L[j[ok]] = np.asarray(labels, bool)[ok]
    F[j[ok]] = np.asarray(fams, object)[ok]
    return np.repeat(V, 60, axis=0), np.repeat(L, 60), np.repeat(F, 60)
