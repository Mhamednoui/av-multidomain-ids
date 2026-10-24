"""WP3 S9 builder: S4-style tile / L1 tables of WORLD-FIXED persistent phantom episodes (the S6 episodes epw_*, seeds [97, drive]) so that
L1 and L2a can be scored on them (S6 built only the L2c / L2d statistics).
A world-fixed episode is a phantom box that stays at one place in the world (parked-car-like): its placement is moved with the OXTS ego-motion
each scan (lidar.background_build.world_params). Same rng consumption as lidar.background_build.drive_episodes(world=True), checked by the
equality of the injected-return counts (n_inj) with the S6 tables.
Inputs: drive id, ring table, calibration, segmentation parameters. Outputs: (scans DataFrame with the L1 statistics, tile table)."""
import numpy as np
import pandas as pd

from lidar import ego
from lidar import geometry as G
from lidar import phantom as P
from lidar.background_build import world_params
from lidar.data import group_id, load, scan_files
from lidar.raycast import eval_params
from lidar.s4_build import EP_KINDS, EP_LEN, segmented


def drive_episodes_world(d, table, calib, prm, n_ep=3):
    files, pose = scan_files(d), ego.poses(d)
    rng = np.random.default_rng([97, int(d)])
    scans, tls = [], []
    for mode, band in EP_KINDS:
        for j in range(n_ep):
            p = eval_params(rng, band)
            s0 = int(rng.integers(1, max(2, len(files) - EP_LEN)))
            kind = f"epW_{mode}_{band}"
            q = None
            for k in range(s0, min(len(files), s0 + EP_LEN)):
                pts = load(files[k])
                rays = P.prepare(pts, table)
                pk = p if q is None else world_params(q, pose[s0], pose[k])
                att, n, qk, idx = P.phantom(pts, rays, pk, rng, mode, calib)
                if q is None:
                    q = qk
                _, tl, m = segmented(att, idx, table, prm)
                sid = f"{group_id(d, files[k])}|{kind}|{j}"
                tl.insert(0, "scan", sid)
                tls.append(tl)
                scans.append(dict(drive=d, idx=k, scan=sid, attack=kind, ep=j, step=k - s0 + 1, n_inj_s9=int(n),
                                  **{kk: v for kk, v in m.items() if kk != "l1"},
                                  **{f"l1_{nn}": v for nn, v in zip(G.STAT_NAMES, m["l1"])}))
    return pd.DataFrame(scans), pd.concat(tls, ignore_index=True)
