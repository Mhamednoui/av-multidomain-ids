"""WP6 S3: composite "drives" for the system evaluation (no dataset has all five domains on one vehicle).

A composite is one vehicle block (family K: one KITTI run with its GPS domain and cross-domain series and LiDAR scans of the same drive;
family C: one comma 120 s window with its cross-domain series) plus same-length segments of the other domains' own streams
(ROAD CAN, D10 host view, VeReMi ego view), all from the same split. Clean composites: every segment clean. Attack composites: exactly
one domain attacked (vehicle-block families come from the vehicle block itself; the others from a recorded / injected attack series with
the onset placed uniformly in the first half of the composite). Construction and rationale: notes/WP6_crossdomain.md "S3 start".
Inputs: tick-series packs of fusion/streams.py. Output: list of composite dicts:
  family, attacked (domain whose stream carries the attack: gps / lidar / can / network / v2x, or "cross" for attacks only the motion
  witnesses see), vehicle (group of the vehicle block), n, onset (tick or -1), label (n,) bool = attack active,
  parts: domain -> {score (n,), layers (n, m), dom_alarm (n,), layer_alarm (n, m), blame (n,) or None, present (n,)}
"""
import numpy as np

K_DOMAINS = ["gps", "lidar", "can", "network", "v2x", "cross"]
C_DOMAINS = ["can", "network", "v2x", "cross"]
GPS_FAMILIES = ["drift", "accel_drift", "doppler_spoof", "meaconing"]
K_VEHICLE_FAMILIES = GPS_FAMILIES + ["lidar_scale", "lidar_bias", "lidar_yaw", "can_scale", "can_offset", "can_freeze"]
C_VEHICLE_FAMILIES = GPS_FAMILIES + ["can_scale", "can_offset", "can_freeze"]
COORDINATED = {"K": ["gps_can"], "C": ["gnss_can", "can_bus"]}
V2_COMPARISON = {"GhostCluster"}            # box cloud: physically impossible on a single-return sensor; v2-comparison row only


def vehicle_attacked(fam):
    return "gps" if fam in GPS_FAMILIES else "cross"


def _alarms(s, pack):
    n, m = s["layers"].shape
    dom = s["dom_alarm"] if "dom_alarm" in s else s["score"] >= pack["dom_thr"]
    lay = s["layer_alarm"] if "layer_alarm" in s else (s["layers"] >= np.asarray(pack["layer_thr"])[None, :])
    return np.asarray(dom, bool), np.asarray(lay, bool).reshape(n, m)


def segment(s, pack, start, n):
    """n ticks of series s from `start` (padded with absent ticks)."""
    L = len(s["score"])
    a, b = max(start, 0), min(start + n, L)
    m = s["layers"].shape[1]
    dom, lay = _alarms(s, pack)
    out = {"score": np.zeros(n, np.float32), "layers": np.zeros((n, m), np.float32), "dom_alarm": np.zeros(n, bool),
           "layer_alarm": np.zeros((n, m), bool), "present": np.zeros(n, bool), "label": np.zeros(n, bool),
           "blame": None if s.get("blame") is None else np.full(n, None, object), "src": s["name"]}
    if b > a:
        o = a - start
        k = b - a
        out["score"][o:o + k] = s["score"][a:b]
        out["layers"][o:o + k] = s["layers"][a:b]
        out["dom_alarm"][o:o + k] = dom[a:b]
        out["layer_alarm"][o:o + k] = lay[a:b]
        out["present"][o:o + k] = True
        out["label"][o:o + k] = s["label"][a:b]
        if out["blame"] is not None:
            out["blame"][o:o + k] = s["blame"][a:b]
    return out


def onsets(s, family):
    f = np.asarray(s["fam"], object) == family
    return np.flatnonzero(f & ~np.r_[False, f[:-1]])


class Builder:
    """packs: domain -> pack (domain names of the composite; "cross" -> cross_kitti / cross_comma pack); groups: domain -> allowed group ids
    (a validation half) or None (all)."""

    def __init__(self, fam, packs, groups=None, seed=0):
        self.fam, self.packs = fam, packs
        self.domains = K_DOMAINS if fam == "K" else C_DOMAINS
        self.rng = np.random.default_rng(seed)
        ok = lambda d, s: groups is None or groups.get(d) is None or s["group"] in groups[d]
        self.series = {d: [s for s in packs[d]["series"] if ok(d, s)] for d in self.domains}
        self.clean = {d: [s for s in self.series[d] if s["kind"] == "clean"] for d in self.domains}
        cr = {s["name"]: s for s in self.series["cross"]}
        self.blocks = []                                   # (family, gps series or None, cross series, group)
        if fam == "K":
            gp = {s["name"]: s for s in self.series["gps"]}
            for name, c in cr.items():
                d, ph, a = name.split("/")
                g = gp.get(name) or gp.get(f"{d}/{ph}/r0")
                if g is None:
                    continue
                self.blocks.append((c["family"], g, c, c["group"]))
        else:
            for name, c in cr.items():
                self.blocks.append((c["family"], None, c, c["group"]))

    # ---- pieces ---------------------------------------------------------------------------------
    def _vehicle(self, blk):
        fam, g, c, grp = blk
        n = len(c["score"])
        parts = {"cross": segment(c, self.packs["cross"], 0, n)}
        lab = c["label"].copy()
        if g is not None:
            ia, ib = np.intersect1d(np.round(g["t"], 3), np.round(c["t"], 3), return_indices=True)[1:]
            gs = segment(g, self.packs["gps"], 0, len(g["score"]))          # GPS run aligned to the cross grid by time
            gseg = {"blame": None, "src": g["name"]}
            for k in ("score", "layers", "dom_alarm", "layer_alarm", "present", "label"):
                v = gs[k]
                gseg[k] = np.zeros((n,) + v.shape[1:], v.dtype)
                gseg[k][ib] = v[ia]
            parts["gps"] = gseg
            if fam in GPS_FAMILIES or fam == "gps_can":
                lab = lab | gseg["label"]
        return parts, n, lab

    def _clean_segment(self, d, n, group=None):
        pool = self.clean[d] if group is None else [s for s in self.clean[d] if s["group"] == group] or self.clean[d]
        long = [s for s in pool if len(s["score"]) >= n]
        if long:
            s = long[self.rng.integers(len(long))]
            start = int(self.rng.integers(0, len(s["score"]) - n + 1))
        else:
            s = pool[self.rng.integers(len(pool))]
            start = 0
        return segment(s, self.packs[d], start, n)

    def _fill(self, parts, n, vehicle_group, skip=()):
        for d in self.domains:
            if d in parts or d in skip:
                continue
            parts[d] = self._clean_segment(d, n, vehicle_group if d == "lidar" else None)
        return parts

    # ---- composites -----------------------------------------------------------------------------
    def clean_composites(self, k):
        blocks = [b for b in self.blocks if b[0] == "none"]
        out = []
        for _ in range(k):
            blk = blocks[self.rng.integers(len(blocks))]
            parts, n, lab = self._vehicle(blk)
            out.append({"family": "none", "attacked": None, "vehicle": blk[3], "n": n, "onset": -1, "label": np.zeros(n, bool),
                        "parts": self._fill(parts, n, blk[3])})
        return out

    def vehicle_attacks(self, family, k):
        blocks = [b for b in self.blocks if b[0] == family]
        out = []
        if not blocks:
            return out
        for _ in range(k):
            blk = blocks[self.rng.integers(len(blocks))]
            parts, n, lab = self._vehicle(blk)
            on = np.flatnonzero(lab)
            out.append({"family": family, "attacked": vehicle_attacked(family) if family not in COORDINATED[self.fam] else "gps+can",
                        "vehicle": blk[3], "n": n, "onset": int(on[0]) if len(on) else -1, "label": lab, "parts": self._fill(parts, n, blk[3])})
        return out

    def domain_families(self, d):
        fams = set()
        for s in self.series[d]:
            if s["kind"] == "attack":
                fams |= {f for f in set(s["fam"]) if f}
        return sorted(fams)

    def domain_attacks(self, d, family, k):
        cands = [(s, o) for s in self.series[d] if s["kind"] == "attack" for o in onsets(s, family)]
        clean_blocks = [b for b in self.blocks if b[0] == "none"]
        out = []
        if not cands:
            return out
        for _ in range(k):
            blk = clean_blocks[self.rng.integers(len(clean_blocks))]
            parts, n, _ = self._vehicle(blk)
            s, o = cands[self.rng.integers(len(cands))]
            u = int(self.rng.integers(0, max(1, n // 2)))
            start = int(o) - u
            if start < 0:
                u, start = int(o), 0
            seg = segment(s, self.packs[d], start, n)
            parts[d] = seg
            out.append({"family": family, "attacked": d, "vehicle": blk[3], "n": n, "onset": u, "label": seg["label"] & (np.arange(n) >= u),
                        "parts": self._fill(parts, n, blk[3])})
        return out
