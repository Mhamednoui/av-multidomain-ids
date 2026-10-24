"""WP3 S4 attacked-scan object tables (evaluation attacks of the supervisor's S3 decision).

Attacks (name -> meaning), all drawn from rng seeds [83, drive, scan index] (episodes: [89, drive]):
  ph_replace_near / ph_replace_far   calibrated single-return ray-cast phantom filling the box (add == replace)
  ph_budget_near / ph_budget_far     the same limited to 50-400 injected returns
  PointDrop, IntensitySpoof          v2 attacks (no injected returns)
  cmp_boxcloud                       v2 box cloud, single-return enforced (comparison only, crude)
  cmp_mradd_near / cmp_mradd_far     calibrated phantom ADDED next to the real return (multi-return, physically impossible on a
                                     single-return sensor; comparison with the v2 / S2 numbers only)
Each attacked scan is segmented (lidar.segment, chosen variant) and stored as an object table (n >= NMIN_STORE points) with the
number of phantom points per object (ph_n), the main phantom object, L1 scan statistics. Clean scans: same table without ph_n.
"""
import numpy as np
import pandas as pd

from lidar import geometry as G
from lidar import phantom as P
from lidar import segment as S
from lidar import singlereturn as SR
from lidar.data import group_id, load, scan_files
from lidar.features import apply_attack, attack_params
from lidar.raycast import eval_params

NMIN_STORE = 10
KEEP = ["cx", "cy", "range", "az", "length", "width", "height", "z_bottom", "n_points", "az_span", "elev_span", "n_rings",
        "ring_min", "ring_max", "int_mean", "int_std", "carlike"]
ATTACKS = ["ph_replace_near", "ph_replace_far", "ph_budget_near", "ph_budget_far", "PointDrop", "IntensitySpoof",
           "cmp_boxcloud", "cmp_mradd_near", "cmp_mradd_far"]
EP_KINDS = [("replace", "near"), ("replace", "far"), ("budget", "near"), ("budget", "far")]
EP_LEN = 30


def compact(tab, ph_n=None):
    t = tab[tab.n_points >= NMIN_STORE][KEEP].astype(np.float32).copy()
    t["oid"] = tab.index[tab.n_points >= NMIN_STORE].to_numpy()
    if ph_n is not None:
        t["ph_n"] = ph_n[t["oid"].to_numpy()].astype(np.float32)
    return t.reset_index(drop=True)


AZ_TILE = 2.0          # deg
RING_GROUP = 8         # lasers per tile (8 x 0.4 deg = 3.2 deg)
R_CELL = 2.0           # m
TILE_MIN = 8


def tiles(pts, lab, k, inj=None):
    """Angular tiles inside the clusters: key = (cluster, 2 deg azimuth, group of 8 lasers, 2 m range cell). Table with the number of
    returns, mean range, mean intensity and (attacked scans) the number of injected returns per tile; tiles with >= TILE_MIN returns."""
    sel = np.flatnonzero(lab >= 0)
    cols = ["oid", "range", "n_points", "int_mean", "ph_n"]
    if len(sel) == 0:
        return pd.DataFrame(columns=cols, dtype=np.float32)
    az = np.degrees(np.arctan2(pts[sel, 1], pts[sel, 0]))
    rho = np.hypot(pts[sel, 0], pts[sel, 1])
    key = ((lab[sel].astype(np.int64) * 180 + np.clip(((az + 180.0) // AZ_TILE).astype(np.int64), 0, 179)) * 8
           + k[sel] // RING_GROUP) * 64 + np.clip((rho // R_CELL).astype(np.int64), 0, 63)
    uk, inv = np.unique(key, return_inverse=True)
    n = np.bincount(inv).astype(float)
    ph = np.bincount(inv, weights=inj[sel].astype(float)) if inj is not None else np.zeros(len(uk))
    t = pd.DataFrame({"oid": uk // (180 * 8 * 64), "range": np.bincount(inv, weights=rho) / n, "n_points": n,
                      "int_mean": np.bincount(inv, weights=pts[sel, 3].astype(float)) / n, "ph_n": ph})
    return t[t.n_points >= TILE_MIN].astype(np.float32).reset_index(drop=True)


def segmented(att, idx, table, prm):
    """(compact object table, tile table, meta dict) of an attacked scan; idx = indices of the injected returns (or None)."""
    tab, lab, _ = S.segment(att, table, prm, return_labels=True)
    inj = None
    if idx is not None and len(idx):
        inj = np.zeros(len(att), bool)
        inj[idx] = True
    tl = tiles(att, lab, table.assign(att)["k"], inj)
    meta = {"l1": G.l1_stats(att, table), "n_obj": len(tab), "n_pts": len(att), "main_oid": -1, "main_share": 0.0, "n_inj": 0}
    ph_n = None
    if idx is not None and len(idx):
        pl = lab[idx]
        inn = pl[pl >= 0]
        ph_n = np.bincount(inn, minlength=max(len(tab), 1)) if len(inn) else np.zeros(max(len(tab), 1), int)
        meta["n_inj"] = int(len(idx))
        if len(inn):
            meta["main_oid"] = int(ph_n.argmax())
            meta["main_share"] = float(ph_n.max() / len(idx))
    return compact(tab, ph_n), tl, meta


def attack_cases(pts, rng, table, calib):
    """Yield (attack name, attacked scan, injected indices or None) for one clean scan; fixed draw order."""
    rays = P.prepare(pts, table)
    for band in ("near", "far"):
        p = eval_params(rng, band)
        for mode in ("replace", "budget"):
            att, n, q, idx = P.phantom(pts, rays, p, rng, mode, calib)
            yield f"ph_{mode}_{band}", att, idx
    for name in ("PointDrop", "IntensitySpoof"):
        yield name, apply_attack(name, pts, attack_params(name, rng), rng), None
    pb = attack_params("GhostCluster", rng)
    att = SR.apply_attack("GhostCluster", pts, pb, rng, table)
    yield "cmp_boxcloud", att, np.arange(max(len(att) - pb["n"], 0), len(att))
    for band in ("near", "far"):
        p = eval_params(rng, band)
        att, n, q, idx = P.phantom(pts, rays, p, rng, "add", calib, single_return=False)
        yield f"cmp_mradd_{band}", att, np.arange(len(pts), len(att))


def drive_attacks(d, table, calib, prm, stride=3):
    """All attack object tables of the scans i % stride == 1 of drive d: (objects DataFrame, scans DataFrame)."""
    files = scan_files(d)
    objs, scans, tls = [], [], []
    for i in range(1, len(files), stride):
        pts = load(files[i])
        rng = np.random.default_rng([83, int(d), i])
        g = group_id(d, files[i])
        for name, att, idx in attack_cases(pts, rng, table, calib):
            t, tl, m = segmented(att, idx, table, prm)
            sid = f"{g}|{name}"
            t.insert(0, "scan", sid)
            tl.insert(0, "scan", sid)
            objs.append(t)
            tls.append(tl)
            scans.append(dict(drive=d, idx=i, scan=sid, base=g, attack=name, **{k: v for k, v in m.items() if k != "l1"},
                              **{f"l1_{n}": v for n, v in zip(G.STAT_NAMES, m["l1"])}))
    return pd.concat(objs, ignore_index=True), pd.DataFrame(scans), pd.concat(tls, ignore_index=True)


def drive_clean(d, table, prm, l1=True):
    """Clean scans of drive d (all): compact object tables + L1 statistics (l1=False: train drives, statistics not needed)."""
    objs, scans, tls = [], [], []
    for i, f in enumerate(scan_files(d)):
        pts = load(f)
        tab, lab, _ = S.segment(pts, table, prm, return_labels=True)
        t = compact(tab)
        tl = tiles(pts, lab, table.assign(pts)["k"])
        g = group_id(d, f)
        t.insert(0, "scan", g)
        tl.insert(0, "scan", g)
        objs.append(t)
        tls.append(tl)
        scans.append(dict(drive=d, idx=i, scan=g, attack="clean", n_obj=len(tab), n_pts=len(pts),
                          **({f"l1_{n}": v for n, v in zip(G.STAT_NAMES, G.l1_stats(pts, table))} if l1 else {})))
    return pd.concat(objs, ignore_index=True), pd.DataFrame(scans), pd.concat(tls, ignore_index=True)


def drive_episodes(d, table, calib, prm, n_ep=3):
    """Persistent phantom episodes (EP_LEN consecutive scans, placement parameters fixed): n_ep per kind."""
    files = scan_files(d)
    rng = np.random.default_rng([89, int(d)])
    objs, scans, tls = [], [], []
    for mode, band in EP_KINDS:
        for j in range(n_ep):
            p = eval_params(rng, band)
            s0 = int(rng.integers(1, max(2, len(files) - EP_LEN)))
            kind = f"ep_{mode}_{band}"
            for k in range(s0, min(len(files), s0 + EP_LEN)):
                pts = load(files[k])
                rays = P.prepare(pts, table)
                att, n, q, idx = P.phantom(pts, rays, p, rng, mode, calib)
                t, tl, m = segmented(att, idx, table, prm)
                sid = f"{group_id(d, files[k])}|{kind}|{j}"
                t.insert(0, "scan", sid)
                tl.insert(0, "scan", sid)
                objs.append(t)
                tls.append(tl)
                scans.append(dict(drive=d, idx=k, scan=sid, attack=kind, ep=j, step=k - s0 + 1,
                                  **{kk: v for kk, v in m.items() if kk != "l1"},
                                  **{f"l1_{nn}": v for nn, v in zip(G.STAT_NAMES, m["l1"])}))
    return pd.concat(objs, ignore_index=True), pd.DataFrame(scans), pd.concat(tls, ignore_index=True)
