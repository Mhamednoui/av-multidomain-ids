"""WP3 S6 feature builders: L2c / L2d statistics of clean scans, attacked scans and persistent episodes (one row per scan).

Clean scan i (i >= 1) is compared with clean scan i-1. Attacked scan (every 3rd scan, the S4 attack set, same rng seeds
[83, drive, i], lidar.s4_build.attack_cases) is compared with the CLEAN previous scan (onset). Episodes (S4 sensor-fixed kinds, seeds
[89, drive]; new world-fixed kinds, seeds [97, drive]) are compared with the previous scan of the same episode (attacked); step 1 with
the clean scan before it. World-fixed episode = a phantom that stays at one place in the world (parked-car-like): its box is moved
with the OXTS ego-motion each scan; sensor-fixed = the S4 persistent phantom (same sensor-frame placement every scan).
Output rows: scan id (same naming as S4), drive, idx, attack, ep, step, the statistics.
"""
import numpy as np
import pandas as pd

from lidar import background as B
from lidar import ego
from lidar import phantom as P
from lidar import track as T
from lidar.data import group_id, load, scan_files
from lidar.raycast import eval_params
from lidar.s4_build import EP_KINDS, EP_LEN, attack_cases


def pair_row(prev_pts, pp, cur_pts, pc, edges, prev_img=None, pred_cache=None):
    """Statistics of scan `cur_pts` given the previous scan. prev_img / pred_cache: reusable images of the previous scan."""
    raw = prev_img if prev_img is not None else B.Img(prev_pts, edges)
    pred = pred_cache if pred_cache is not None else B.Img(B.moved(prev_pts, pp, pc), edges)
    cur = B.Img(cur_pts, edges)
    row = B.miss_stats(cur, pred)
    row.update(T.track_stats(cur, pred, raw))
    row["disp"] = float(np.hypot(*(pc[:2] - pp[:2])))
    return row


def drive_clean(d, table):
    edges = B.ring_edges(table)
    files, pose = scan_files(d), ego.poses(d)
    rows, prev = [], None
    for i, f in enumerate(files):
        pts = load(f)
        if prev is not None:
            r = pair_row(prev, pose[i - 1], pts, pose[i], edges)
            r.update(scan=group_id(d, f), drive=d, idx=i, attack="clean")
            rows.append(r)
        prev = pts
    return pd.DataFrame(rows)


def drive_attacks(d, table, calib, stride=3):
    edges = B.ring_edges(table)
    files, pose = scan_files(d), ego.poses(d)
    rows = []
    for i in range(1, len(files), stride):
        pts = load(files[i])
        rng = np.random.default_rng([83, int(d), i])
        g = group_id(d, files[i])
        prev = load(files[i - 1])
        raw = B.Img(prev, edges)
        pred = B.Img(B.moved(prev, pose[i - 1], pose[i]), edges)
        for name, att, idx in attack_cases(pts, rng, table, calib):
            r = pair_row(prev, pose[i - 1], att, pose[i], edges, raw, pred)
            r.update(scan=f"{g}|{name}", drive=d, idx=i, attack=name)
            rows.append(r)
    return pd.DataFrame(rows)


def world_params(q, pose0, posek):
    """Box placement parameters (sensor frame of scan k) of a box that stays fixed in the world: q placed in the frame of pose0."""
    c = np.array([[q["range"] * np.cos(np.radians(q["az"])), q["range"] * np.sin(np.radians(q["az"]))],
                  [q["range"] * np.cos(np.radians(q["az"])) + np.cos(q["rot"]), q["range"] * np.sin(np.radians(q["az"])) + np.sin(q["rot"])]])
    c2 = ego.between(c, pose0, posek)
    p = dict(q)
    p["range"] = float(np.hypot(*c2[0]))
    p["az"] = float(np.degrees(np.arctan2(c2[0, 1], c2[0, 0])))
    v = c2[1] - c2[0]
    p["rot"] = float(np.arctan2(v[1], v[0]) % np.pi)
    return p


def drive_episodes(d, table, calib, n_ep=3, world=False):
    """Persistent phantom episodes of S4 (world=False, identical draws) or world-fixed ones (world=True, seeds [97, d])."""
    edges = B.ring_edges(table)
    files, pose = scan_files(d), ego.poses(d)
    rng = np.random.default_rng([97 if world else 89, int(d)])
    rows = []
    for mode, band in EP_KINDS:
        for j in range(n_ep):
            p = eval_params(rng, band)
            s0 = int(rng.integers(1, max(2, len(files) - EP_LEN)))
            kind = f"ep{'W' if world else ''}_{mode}_{band}"
            prev, q = load(files[s0 - 1]), None
            for k in range(s0, min(len(files), s0 + EP_LEN)):
                pts = load(files[k])
                rays = P.prepare(pts, table)
                pk = p if (not world or q is None) else world_params(q, pose[s0], pose[k])
                att, n, qk, idx = P.phantom(pts, rays, pk, rng, mode, calib)
                if q is None:
                    q = qk
                r = pair_row(prev, pose[k - 1], att, pose[k], edges)
                r.update(scan=f"{group_id(d, files[k])}|{kind}|{j}", drive=d, idx=k, attack=kind, ep=j, step=k - s0 + 1, n_inj=n)
                rows.append(r)
                prev = att
    return pd.DataFrame(rows)
