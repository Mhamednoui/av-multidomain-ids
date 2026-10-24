"""WP3 S5 attacked / clean tile tables with the see-through counts (lidar.occlusion).

Attacks: the nine S4 attacks (same seeds [83, drive, scan index], so the attacked scans are identical to the S4 ones and the S4
L2a tables can be joined by scan id) plus four best-case attacker phantoms `fl_{replace,budget}_{near,far}` (a return on every ray
through the silhouette, no dropout; seeds [97, drive, scan index]) that test the physics statement of lidar.occlusion.
Episodes: the four S4 kinds (seeds [89, drive]) plus fl_replace near / far (seeds [99, drive]).
"""
import numpy as np
import pandas as pd

from lidar import occlusion as O
from lidar import phantom as P
from lidar import s4_build as B
from lidar import segment as S
from lidar.data import group_id, load, scan_files
from lidar.raycast import eval_params

ATTACKS = B.ATTACKS + ["fl_replace_near", "fl_replace_far", "fl_budget_near", "fl_budget_far"]
EP_FULL = [("replace", "near"), ("replace", "far")]


def tiles_of(att, idx, table, prm, rank):
    tab, lab, _ = S.segment(att, table, prm, return_labels=True)
    inj = None
    if idx is not None and len(idx):
        inj = np.zeros(len(att), bool)
        inj[idx] = True
    k = table.assign(att)["k"]
    tl = O.tile_table(att, lab, k, rank, inj)
    meta = {"n_obj": len(tab), "n_pts": len(att), "n_inj": 0 if idx is None else int(len(idx))}
    return tl, meta


def full_cases(pts, rng, table, calib):
    fc = O.FullCalib.of(calib)
    rays = P.prepare(pts, table)
    for band in ("near", "far"):
        p = eval_params(rng, band)
        for mode in ("replace", "budget"):
            att, n, q, idx = P.phantom(pts, rays, p, rng, mode, fc)
            yield f"fl_{mode}_{band}", att, idx


def _add(tls, scans, tl, meta, sid, **kw):
    tl.insert(0, "scan", sid)
    tls.append(tl)
    scans.append(dict(scan=sid, **meta, **kw))


def drive_attacks(d, table, calib, prm, stride=3):
    rank = O.elevation_rank(table)
    files = scan_files(d)
    tls, scans = [], []
    for i in range(1, len(files), stride):
        pts = load(files[i])
        g = group_id(d, files[i])
        cases = list(B.attack_cases(pts, np.random.default_rng([83, int(d), i]), table, calib))
        cases += list(full_cases(pts, np.random.default_rng([97, int(d), i]), table, calib))
        for name, att, idx in cases:
            tl, m = tiles_of(att, idx, table, prm, rank)
            _add(tls, scans, tl, m, f"{g}|{name}", drive=d, idx=i, base=g, attack=name)
    return pd.concat(tls, ignore_index=True), pd.DataFrame(scans)


def drive_clean(d, table, prm):
    rank = O.elevation_rank(table)
    tls, scans = [], []
    for i, f in enumerate(scan_files(d)):
        pts = load(f)
        tl, m = tiles_of(pts, None, table, prm, rank)
        _add(tls, scans, tl, m, group_id(d, f), drive=d, idx=i, attack="clean")
    return pd.concat(tls, ignore_index=True), pd.DataFrame(scans)


def drive_episodes(d, table, calib, prm, n_ep=3):
    """Persistent phantom episodes (EP_LEN consecutive scans, placement fixed): the S4 kinds with the S4 seeds, plus full-fill replace."""
    rank = O.elevation_rank(table)
    files = scan_files(d)
    tls, scans = [], []
    rng = np.random.default_rng([89, int(d)])
    kinds = [(m, b, calib, "ep") for m, b in B.EP_KINDS]
    for mode, band, cal, tag in kinds:
        _episodes(d, files, table, cal, prm, rank, rng, mode, band, f"{tag}_{mode}_{band}", n_ep, tls, scans)
    rng = np.random.default_rng([99, int(d)])
    for mode, band in EP_FULL:
        _episodes(d, files, table, O.FullCalib.of(calib), prm, rank, rng, mode, band, f"epfl_{mode}_{band}", n_ep, tls, scans)
    return pd.concat(tls, ignore_index=True), pd.DataFrame(scans)


def _episodes(d, files, table, cal, prm, rank, rng, mode, band, kind, n_ep, tls, scans):
    for j in range(n_ep):
        p = eval_params(rng, band)
        s0 = int(rng.integers(1, max(2, len(files) - B.EP_LEN)))
        for k in range(s0, min(len(files), s0 + B.EP_LEN)):
            pts = load(files[k])
            rays = P.prepare(pts, table)
            att, n, q, idx = P.phantom(pts, rays, p, rng, mode, cal)
            tl, m = tiles_of(att, idx, table, prm, rank)
            _add(tls, scans, tl, m, f"{group_id(d, files[k])}|{kind}|{j}", drive=d, idx=k, attack=kind, ep=j, step=k - s0 + 1)
