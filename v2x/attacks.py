"""Misbehaviour injection on real V2X messages, following the VeReMi Extension taxonomy.

Purpose: real unlabeled BSMs (Tampa) are turned into labelled scenarios. Each attacker is one
sender; the rest of the split is genuine traffic. Labels are per message: label = attack id for
every message whose content was falsified (or created), 0 otherwise.
Inputs: unified table (v2x/schema.py), attacker sender ids, attack id, rng. Output: scenario table.

Physical description (G = the attacker's genuine messages, t_i time, p_i = (x_i, y_i), v_i speed,
h_i heading, u_i = (cos h_i, sin h_i), n_i = (-sin h_i, cos h_i)). An attacker controls only what it
transmits; it cannot change timestamps of messages already sent, cannot make its true motion
different, and sends from its own radio (so its ground-truth sender id stays the same; only the
pseudonym can be chosen freely).
 1 ConstPos        p_i' = P (fixed point taken from where other real vehicles were seen)
 2 ConstPosOffset  p_i' = p_i + d, d fixed, |d| ~ U(100, 300) m, random direction
 3 RandomPos       p_i' ~ U(bounding box of the traffic), fresh each message
 4 RandomPosOffset p_i' = p_i + r_i (cos a_i, sin a_i), r_i ~ U(50, 300) m, a_i ~ U(0, 2 pi)
 5 ConstSpeed      v_i' = c, c ~ U(15, 35) m/s, velocity = v_i' u_i, acl = 0
 6 ConstSpeedOffset v_i' = v_i + c, c ~ U(5, 15) m/s
 7 RandomSpeed     v_i' ~ U(0, 35) m/s fresh each message
 8 RandomSpeedOffset v_i' = v_i + U(0, 10) m/s
 9 EventualStop    from a message k (30-60 % of the life): p_i' = p_k, v' = 0, acl = 0, yaw = 0
                   (a genuine-looking vehicle that claims to have stopped; messages before k are
                   genuine and keep label 0)
10 Disruptive      kinematics of every message replaced by a random message of another vehicle
                   (overheard on air), own timestamp: consecutive messages jump between places
11 DataReplay      the kinematic sequence of ONE other vehicle is replayed in order, shifted to the
                   attacker's own timestamps (replay is exact: same values as the victim sent)
12 DelayedMessages state sent at t is the attacker's own state from t - D, D = 3 s (stale data);
                   the first messages (no stale state yet) are not sent
13 DoS             rate x2: extra messages at t_i + j*dt/2 carrying the true state extrapolated
                   with constant velocity: p = p_i + v_i u_i (t' - t_i)
14 DoSRandom       rate x4 with random position and random speed (as 3 + 7)
15 DoSDisruptive   rate x4 with disruptive content (as 10)
16 GridSybil       5 ghost pseudonyms driving with the attacker in a grid: ghost at p_i + f u_i +
                   l n_i with (f, l) in {(15,0), (-15,0), (0,3.5), (15,3.5), (-15,3.5)} m, same
                   speed / heading as the attacker; each ghost transmits at the attacker's rate
                   (total rate x6, as in the data)
17 DataReplaySybil the attacker replays other vehicles' sequences (as 11) and changes pseudonym
                   whenever the replayed victim changes (every 50 messages)
18 DoSRandomSybil  rate x2, random position and speed, fresh pseudonym drawn from 100 per message
19 DoSDisruptiveSybil rate x2, disruptive content, pseudonym drawn from 100 per message
The rate factors follow the measured message rates of the VeReMi Extension data (reports/WP5_S1.md).
"Sudden appearance" needs the receiver position (unknown for Tampa RSUs); not injected in S1.
References: Kamel et al., VeReMi Extension (ICC 2020); van der Heijden et al., VeReMi (2018).
"""
import numpy as np
import pandas as pd

from common.config import SEED
from v2x.schema import CLASS_NAMES

K = ["x", "y", "speed", "vx", "vy", "heading", "acl", "yaw_rate"]
V_MAX = 35.0
DELAY_S = 3.0
GRID = [(15, 0), (-15, 0), (0, 3.5), (15, 3.5), (-15, 3.5)]
DOS_RATE = {13: 2, 14: 4, 15: 4, 18: 2, 19: 2}
N_PSEUDO = 100
REPLAY_BLOCK = 50
ATTACK_IDS = list(range(1, 20))


def _unit(g):
    h = g["heading"].to_numpy(float)
    bad = ~np.isfinite(h)
    if bad.any():
        h = h.copy()
        h[bad] = np.arctan2(g["vy"].to_numpy(float), g["vx"].to_numpy(float))[bad]
    return np.cos(h), np.sin(h)


def _set_speed(g, s):
    ux, uy = _unit(g)
    g["speed"] = s
    g["vx"], g["vy"] = s * ux, s * uy
    g["acl"] = np.where(np.isfinite(g["acl"]), g["acl"], np.nan)
    return g


def _pos_offset(g, r, a):
    g["x"] = g["x"].to_numpy() + r * np.cos(a)
    g["y"] = g["y"].to_numpy() + r * np.sin(a)
    return g


def _random_pos(g, ctx, rng):
    g["x"] = rng.uniform(*ctx["xr"], len(g))
    g["y"] = rng.uniform(*ctx["yr"], len(g))
    return g


def _disruptive(g, ctx, rng):
    pool = ctx["pool"]
    pick = pool.iloc[rng.randint(0, len(pool), len(g))]
    for c in K:
        g[c] = pick[c].to_numpy()
    return g


def _replay(g, ctx, rng, victim=None):
    """Kinematics of one victim sequence, in order, onto g's timestamps."""
    seqs = ctx["victims"]
    n = len(g)
    if victim is None:
        long_enough = [i for i, s in enumerate(seqs) if len(s) >= n]
        i = long_enough[rng.randint(len(long_enough))] if long_enough else int(np.argmax([len(s) for s in seqs]))
        victim = seqs[i]
    idx = np.arange(n) % len(victim)
    for c in K:
        g[c] = victim[c].to_numpy()[idx]
    return g


def _dos_expand(g, k):
    """k-1 extra messages between consecutive ones, state extrapolated at constant velocity."""
    t = g["t"].to_numpy()
    dt = float(np.median(np.diff(t))) if len(t) > 1 else 0.1
    parts = [g]
    for j in range(1, k):
        e = g.copy()
        d = j * dt / k
        e["t"] = t + d
        e["x"] = g["x"].to_numpy() + g["vx"].to_numpy() * d
        e["y"] = g["y"].to_numpy() + g["vy"].to_numpy() * d
        e["msg_id"] = g["msg_id"].to_numpy() + f"+dos{j}"
        parts.append(e)
    return pd.concat(parts).sort_values("t", kind="stable")


def _attack_one(g, aid, ctx, rng):
    """g: genuine rows of one attacker sorted by t. Returns attacked rows; adds 'falsified' bool."""
    g = g.copy()
    g["falsified"] = True
    n = len(g)
    if aid == 1:
        P = ctx["points"][rng.randint(len(ctx["points"]))]
        g["x"], g["y"] = P[0], P[1]
    elif aid == 2:
        r, a = rng.uniform(100, 300), rng.uniform(0, 2 * np.pi)
        g = _pos_offset(g, r, a)
    elif aid == 3:
        g = _random_pos(g, ctx, rng)
    elif aid == 4:
        g = _pos_offset(g, rng.uniform(50, 300, n), rng.uniform(0, 2 * np.pi, n))
    elif aid == 5:
        g = _set_speed(g, np.full(n, rng.uniform(15, 35)))
        g["acl"] = 0.0
    elif aid == 6:
        g = _set_speed(g, g["speed"].to_numpy() + rng.uniform(5, 15))
    elif aid == 7:
        g = _set_speed(g, rng.uniform(0, V_MAX, n))
    elif aid == 8:
        g = _set_speed(g, g["speed"].to_numpy() + rng.uniform(0, 10, n))
    elif aid == 9:
        k = int(n * rng.uniform(0.3, 0.6))
        g["falsified"] = np.arange(n) >= k
        s = g.iloc[k:].index
        px, py = g["x"].iloc[k], g["y"].iloc[k]
        g.loc[s, "x"], g.loc[s, "y"] = px, py
        for c in ("speed", "vx", "vy", "acl", "yaw_rate"):
            g.loc[s, c] = 0.0
    elif aid in (10, 15, 19):
        if aid != 10:
            g = _dos_expand(g, DOS_RATE[aid])
        g = _disruptive(g, ctx, rng)
        if aid == 19:
            g["pseudo"] = [f"{g['sender'].iloc[0]}_p{i}" for i in rng.randint(0, N_PSEUDO, len(g))]
    elif aid in (11, 17):
        if aid == 11:
            g = _replay(g, ctx, rng)
        else:
            pieces = []
            for b, lo in enumerate(range(0, n, REPLAY_BLOCK)):
                p = _replay(g.iloc[lo:lo + REPLAY_BLOCK].copy(), ctx, rng)
                p["pseudo"] = f"{g['sender'].iloc[0]}_s{b}"
                pieces.append(p)
            g = pd.concat(pieces)
    elif aid == 12:
        t = g["t"].to_numpy()
        src = np.searchsorted(t, t - DELAY_S, side="right") - 1
        ok = src >= 0
        stale = g.iloc[src[ok]]
        g = g.iloc[np.where(ok)[0]].copy()
        for c in K:
            g[c] = stale[c].to_numpy()
    elif aid == 13:
        g = _dos_expand(g, DOS_RATE[13])
    elif aid in (14, 18):
        g = _dos_expand(g, DOS_RATE[aid])
        g = _random_pos(g, ctx, rng)
        g = _set_speed(g, rng.uniform(0, V_MAX, len(g)))
        if aid == 18:
            g["pseudo"] = [f"{g['sender'].iloc[0]}_p{i}" for i in rng.randint(0, N_PSEUDO, len(g))]
    elif aid == 16:
        ux, uy = _unit(g)
        ghosts = []
        for i, (f, l) in enumerate(GRID):
            e = g.copy()
            e["x"] = g["x"].to_numpy() + f * ux - l * uy
            e["y"] = g["y"].to_numpy() + f * uy + l * ux
            e["pseudo"] = f"{g['sender'].iloc[0]}_g{i}"
            e["msg_id"] = g["msg_id"].to_numpy() + f"+g{i}"
            ghosts.append(e)
        g = pd.concat([g] + ghosts)
    else:
        raise ValueError(aid)
    return g


def build_scenario(df: pd.DataFrame, vehicles, aid: int, seed: int = SEED, frac: float = 0.5,
                   min_msgs: int = 50):
    """Scenario from the vehicles of ONE split: a random `frac` of the eligible vehicles
    (>= min_msgs messages) become attackers of type `aid`; the others stay genuine and also
    provide the replay / disruptive pool (so nothing leaks between splits).
    Returns (scenario table sorted by (track, t), list of attacker sender ids)."""
    if aid not in CLASS_NAMES or aid == 0:
        raise ValueError("attack id must be 1..19")
    rng = np.random.RandomState(seed + 1000 * aid)
    d = df[df["sender"].isin(set(map(str, vehicles)))].sort_values(["sender", "t"], kind="stable")
    cnt = d.groupby("sender").size()
    eligible = sorted(cnt.index[cnt >= min_msgs])
    n_att = max(1, int(round(frac * len(eligible))))
    attackers = sorted(rng.choice(eligible, n_att, replace=False).tolist())
    keep = d[~d["sender"].isin(attackers)]
    victims_ids = sorted(keep["sender"].unique())
    if not victims_ids:
        raise ValueError("no genuine vehicles left for the replay pool")
    ctx = {"pool": keep, "victims": [keep[keep["sender"] == s] for s in victims_ids],
           "xr": (d["x"].min(), d["x"].max()), "yr": (d["y"].min(), d["y"].max()),
           "points": keep[["x", "y"]].to_numpy()}
    out = [keep]
    for s in attackers:
        g0 = d[d["sender"] == s]
        g = _attack_one(g0, aid, ctx, rng)
        if "falsified" in g:
            fals = g.pop("falsified").to_numpy().astype(bool)
        g["label"] = np.where(fals, aid, 0)
        g["attack"] = np.where(fals, CLASS_NAMES[aid], "Genuine")
        g["injected"] = fals
        if aid in (16, 17, 18, 19):
            g["track"] = g["sender"] + "/" + g["pseudo"]
        # keep one-to-one: a track of a sender never reuses a msg_id
        out.append(g)
    sc = pd.concat(out).sort_values(["track", "t"], kind="stable").reset_index(drop=True)
    return sc, attackers
