"""WP5 S3b: misbehaviour injection on real V2AIX CAMs (VeReMi taxonomy, v2x/attacks.py reused) plus three receiver-aware variants.

Purpose: V2AIX has no labelled attacks, so genuine real CAMs of one environment (Mobile or Stationary) and one split (train / val / test recordings only; never mixed) are turned
into labelled scenarios. Attackers = a random 50% of the senders with >= MIN_MSGS messages; every other sender stays genuine and provides the replay / disruptive pool, so the pool
is real overheard traffic of the same split. Random-position box = traffic box of the attacker's own recording +- BOX_MARGIN_M (an attacker spoofs positions in the neighbourhood
of what the receiver sees); ConstPos point = a position where another sender of the same recording was heard (global pool if none).
Physical description of types 1-19: see v2x/attacks.py (an attacker controls only the content of what it transmits, not its own physics or clock). Specifics of real CAMs:
  - the CAM interval is irregular (median ~0.35 s, 0.1-1 s): the VeReMi rate factors (DoS x2 / x4, Sybil x6) are kept as message multipliers of the genuine stream; extra messages
    sit half / quarter intervals after a genuine one with the state extrapolated at constant velocity;
  - the generation time t of a sender is known only up to a constant (sender clock offset); injected rows keep their own latency, recv_s = t + latency, so reception order
    and the relative latency age_s stay consistent. 12 DelayedMessages keeps the VeReMi form (stale state under a fresh stamp, D = 3 s: the first 3 s of the attacker are not sent).
Extra types (labels outside the VeReMi map; not validated by schema.validate):
  12b DelayedBurst    from 30-60% of the attacker's life each message keeps its content and generation time but is received D = 3 s later (held in a buffer): age_s and recv_s += 3 s.
                      A CONSTANT delay of every message would be indistinguishable from a clock offset (relative latency is measured per sender), so only the step is visible.
  20 GhostNearReceiver  a ghost vehicle appears next to the receiver: a rigid copy of the attacker's own track (consistent kinematics) shifted so that its first message is
                      U(20, 150) m from the receiver, under a new pseudonym, starting >= 6 s into the recording (the receiver was already listening). The attacker keeps sending genuinely.
  21 FarPosOffset     rigid position shift |d| ~ U(5, 20) km in a random direction (a spoofed far position / relayed remote vehicle): a consistent track, visible only against the receiver.
Inputs: genuine table of one environment and split (v2x/v2aix.py columns incl. recv_s, rx_*), attack id, seed. Output: (scenario table sorted by (track, t), attacker ids).
References: Kamel et al., VeReMi Extension (ICC 2020); v2x/attacks.py.
"""
import numpy as np
import pandas as pd

from common.config import SEED
from v2x import attacks
from v2x.schema import CLASS_NAMES

MIN_MSGS = 20
BOX_MARGIN_M = 500.0
GHOST_MIN_START_S = 6.0
DELAY_S = attacks.DELAY_S
EXTRA_NAMES = {"12b": "DelayedBurst", "20": "GhostNearReceiver", "21": "FarPosOffset"}
EXTRA_LABEL = {"12b": 12, "20": 20, "21": 21}
ALL_TYPES = [str(i) for i in range(1, 20)] + ["12b", "20", "21"]


def type_name(code: str) -> str:
    return EXTRA_NAMES.get(code, CLASS_NAMES.get(int(code)) if code.isdigit() else code)


def _seed_of(code: str) -> int:
    return {"12b": 22, "20": 20, "21": 21}.get(code, int(code) if code.isdigit() else 0)


def _fill_heading(g):
    """Attacker rows with an unavailable heading (0.3% of CAMs, vx / vy are NaN then): carry the neighbouring heading, 0 if the sender has none, so every attack
    that uses the direction of travel (ghost grid, extrapolated DoS messages) stays finite. Genuine rows are left untouched."""
    g = g.copy()
    h = g["heading"].ffill().bfill().fillna(0.0).to_numpy(float)
    bad = ~np.isfinite(g["heading"].to_numpy(float)) | ~np.isfinite(g["vx"].to_numpy(float)) | ~np.isfinite(g["vy"].to_numpy(float))
    sp = g["speed"].to_numpy(float)
    g.loc[:, "heading"] = h
    g.loc[:, "vx"] = np.where(bad, sp * np.cos(h), g["vx"].to_numpy(float))
    g.loc[:, "vy"] = np.where(bad, sp * np.sin(h), g["vy"].to_numpy(float))
    return g


def _recording_box(d):
    b = d.groupby("recording").agg(x0=("x", "min"), x1=("x", "max"), y0=("y", "min"), y1=("y", "max"), r0=("recv_s", "min"))
    return b


def build_scenario(df: pd.DataFrame, code: str, seed: int = SEED, frac: float = 0.5, min_msgs: int = MIN_MSGS):
    """code in ALL_TYPES ('1'..'19', '12b', '20', '21'). Returns (scenario sorted by (track, t), attacker sender ids)."""
    code = str(code)
    if code not in ALL_TYPES:
        raise ValueError(code)
    d = df.sort_values(["sender", "t"], kind="stable").copy()
    d["lat_s"] = d["recv_s"] - d["t"]
    rng = np.random.RandomState(seed + 1000 * _seed_of(code))
    cnt = d.groupby("sender").size()
    eligible = sorted(cnt.index[cnt >= min_msgs])
    if not eligible:
        raise ValueError("no sender with enough messages")
    n_att = max(1, int(round(frac * len(eligible))))
    attackers = sorted(rng.choice(eligible, n_att, replace=False).tolist())
    keep = d[~d["sender"].isin(attackers)]
    if not len(keep):
        raise ValueError("no genuine sender left for the replay pool")
    victims = [keep[keep["sender"] == s] for s in sorted(keep["sender"].unique())]
    box = _recording_box(d)
    keep_xy = {r: g[["x", "y"]].to_numpy() for r, g in keep.groupby("recording")}
    all_xy = keep[["x", "y"]].to_numpy()
    out = [keep]
    for s in attackers:
        g0 = _fill_heading(d[d["sender"] == s])
        rec = g0["recording"].iloc[0]
        b = box.loc[rec]
        ctx = {"pool": keep, "victims": victims, "xr": (b["x0"] - BOX_MARGIN_M, b["x1"] + BOX_MARGIN_M), "yr": (b["y0"] - BOX_MARGIN_M, b["y1"] + BOX_MARGIN_M),
               "points": keep_xy.get(rec, all_xy)}
        if code == "12b":
            g = g0.copy()
            n = len(g)
            k = int(n * rng.uniform(0.3, 0.6))
            fals = np.arange(n) >= k
            g["age_s"] = g["age_s"].to_numpy(float) + np.where(fals, DELAY_S, 0.0)
            g["lat_s"] = g["lat_s"].to_numpy(float) + np.where(fals, DELAY_S, 0.0)
            parts = [(g, fals, 12)]
        elif code == "21":
            g = g0.copy()
            r, a = rng.uniform(5000, 20000), rng.uniform(0, 2 * np.pi)
            g["x"] = g["x"].to_numpy(float) + r * np.cos(a)
            g["y"] = g["y"].to_numpy(float) + r * np.sin(a)
            parts = [(g, np.ones(len(g), bool), 21)]
        elif code == "20":
            late = g0[g0["recv_s"] >= b["r0"] + GHOST_MIN_START_S]
            if len(late) < 5 or not np.isfinite(late[["rx_x", "rx_y"]].iloc[0].to_numpy(float)).all():
                continue
            gh = late.copy()
            r, a = rng.uniform(20, 150), rng.uniform(0, 2 * np.pi)
            tx = late["rx_x"].iloc[0] + r * np.cos(a) - late["x"].iloc[0]
            ty = late["rx_y"].iloc[0] + r * np.sin(a) - late["y"].iloc[0]
            gh["x"] = gh["x"].to_numpy(float) + tx
            gh["y"] = gh["y"].to_numpy(float) + ty
            gh["pseudo"] = f"{s}_gh"
            gh["msg_id"] = gh["msg_id"].to_numpy() + "+gh"
            gh["track"] = gh["sender"] + "/" + gh["pseudo"]
            parts = [(g0.copy(), np.zeros(len(g0), bool), 0), (gh, np.ones(len(gh), bool), 20)]
        else:
            aid = int(code)
            g = attacks._attack_one(g0, aid, ctx, rng)
            fals = g.pop("falsified").to_numpy().astype(bool)
            if aid in (16, 17, 18, 19):
                g["track"] = g["sender"] + "/" + g["pseudo"]
            parts = [(g, fals, aid)]
        for g, fals, lab in parts:
            if not len(g):
                continue
            g = g.copy()
            g["recv_s"] = g["t"].to_numpy(float) + g["lat_s"].to_numpy(float)     # 12b: lat_s already holds the +D step
            g["label"] = np.where(fals, lab, 0)
            g["attack"] = np.where(fals, type_name(code) if lab else "Genuine", "Genuine")
            g["injected"] = fals
            out.append(g)
    sc = pd.concat(out).sort_values(["track", "t"], kind="stable").reset_index(drop=True)
    return sc, attackers
