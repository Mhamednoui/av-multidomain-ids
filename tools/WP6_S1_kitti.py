"""WP6 S1 KITTI: motion-witness streams, latency, normalised residuals and sigma honesty (gps, imu, lidar, simulated can).

Stages (python -u -W ignore tools/WP6_S1_kitti.py <stage>):
  build : per drive (23), clean phase-0 run of the WP1 stream: MotionEstimate streams of every source -> 1 Hz grid
          -> pair tables; native-rate signals for latency. Cache ../data_extra/cache_v3/WP6/s1_kitti.pkl.
  dev   : latency on TRAIN drives, honesty with published sigmas on TRAIN and VAL, SigmaModel fitted on TRAIN, honesty
          after recalibration on VAL -> results/WP6/s1_kitti_dev.json, recalibration -> results/WP6/s1_sigma_models.json.
  test  : ONCE, after dev: honesty on TEST with the published sigmas and the frozen train recalibration
          -> results/WP6/s1_kitti_test.json.
Split: WP1 drive split (gps/stream.py TEST / VAL; rest train). Seeds: common.config.SEED.
"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import DATA_EXTRA, SEED, results_dir  # noqa: E402
from crossdomain import kitti as K  # noqa: E402
from crossdomain import witness as W  # noqa: E402
from gps import stream as GS  # noqa: E402

CACHE = DATA_EXTRA / "cache_v3" / "WP6"
OUT = results_dir("WP6")
WP1_STREAM = Path(__import__("tempfile").gettempdir()) / "wp1_s4_kitti.pkl"     # WP1 S4 cache (read only); rebuilt identically if absent
SPEED_PAIRS = [("gps", "lidar"), ("gps", "can"), ("lidar", "can")]
YAW_PAIRS = [("gps", "lidar"), ("gps", "imu"), ("imu", "lidar")]
LAT_PAIRS = {"oxts-lidar speed": ("oxts_speed", "lidar_speed"), "oxts-lidar yaw_rate": ("oxts_yaw", "lidar_yaw")}
VEHICLE_SCALE = float(np.random.default_rng([SEED, 6, 3]).normal(0, 0.02))   # R2: one car -> one tyre-scale draw
R2_DRIVE_SIGMA = 0.0015                                                        # R2: comma train per-route scale spread (0.00145)
GPS_POS_DIFF_SIGMA = 0.447        # per axis, receiver AR(1) (phi 0.9, sigma 1 m) differenced over 1 s (gps.domain sigma 0.45)


def kitti_stream():
    if WP1_STREAM.exists():
        return pd.read_pickle(WP1_STREAM)[GS.COLUMNS]
    return GS.build_kitti(np.random.default_rng(SEED), new_attacks=GS.ATTACKS_NEW)


def lateral_table(ga, gb):
    """gps-lidar lateral (dy, body left) residual; sigmas: gps = hypot(position difference, v x compass), lidar = its speed sigma."""
    j = ga.join(gb, how="inner", lsuffix="_a", rsuffix="_b")
    v = j["speed_b"].to_numpy(float)
    sa = np.hypot(GPS_POS_DIFF_SIGMA, v * W.COMPASS_SIGMA_RAD)
    sb = j["sigma_b"].to_numpy(float)
    r = j["dy_a"].to_numpy(float) - j["dy_b"].to_numpy(float)
    s = np.hypot(sa, sb)
    f = pd.DataFrame({"t": j.index.to_numpy(float), "pair": "gps-lidar", "quantity": "lateral", "a": j["dy_a"].to_numpy(float),
                      "b": j["dy_b"].to_numpy(float), "r": r, "s": s, "z": r / s, "v": v})
    return f[np.isfinite(f["r"]) & np.isfinite(f["s"])]


def build():
    from can.domain import CanDomain
    dom = CanDomain.load(Path(__file__).resolve().parent.parent / "results" / "WP2" / "s7_domain")
    kx = kitti_stream()
    rows, native, sources, scales = [], {}, {}, {}
    rowsR, scalesR = [], {}
    for d in sorted(GS.SCENE):
        run = kx[kx["run"] == f"{d}/p0/r0"].sort_values("t").reset_index(drop=True)
        assert (run["attack"] == "none").all()
        ox = GS.load_oxts(d)
        rng = np.random.default_rng([SEED, 6, 1, int(d)])
        src, truth = K.drive_sources(run, d, ox, dom, rng)
        scales[d] = truth["scale"]
        grid = run["t"].to_numpy(float)
        G = {s: W.to_grid(f, grid) for s, f in src.items()}
        parts = [W.pair_table(G[a], G[b], a, b, "speed") for a, b in SPEED_PAIRS]
        parts += [W.pair_table(G[a], G[b], a, b, "yaw_rate") for a, b in YAW_PAIRS]
        parts.append(lateral_table(G["gps"], G["lidar"]))
        tab = pd.concat(parts, ignore_index=True)
        tab["drive"], tab["part"] = d, GS.part_of(d)
        rows.append(tab)
        # revised design R (notes 2026-10-22): R2 one vehicle tyre scale + per-drive 0.15%, R4 forward-displacement speed
        srcR, truthR = K.drive_sources(run, d, ox, dom, np.random.default_rng([SEED, 6, 2, int(d)]),
                                       scale=VEHICLE_SCALE + np.random.default_rng([SEED, 6, 4, int(d)]).normal(0, R2_DRIVE_SIGMA))
        GR = {s: W.to_grid(f, grid) for s, f in srcR.items()}
        GR["gps"], GR["lidar"] = K.forward_speed(GR["gps"]), K.forward_speed(GR["lidar"])
        partsR = [W.pair_table(GR[a], GR[b], a, b, "speed") for a, b in SPEED_PAIRS]
        partsR += [W.pair_table(GR[a], GR[b], a, b, "yaw_rate") for a, b in YAW_PAIRS]
        partsR.append(lateral_table(GR["gps"], GR["lidar"]))
        tabR = pd.concat(partsR, ignore_index=True)
        tabR["drive"], tabR["part"] = d, GS.part_of(d)
        rowsR.append(tabR)
        scalesR[d] = truthR["scale"]
        native[d] = K.native_signals(d, ox)
        sources[d] = {s: len(f) for s, f in src.items()}
        print(d, GS.part_of(d), sources[d], len(tab), flush=True)
    tab = pd.concat(rows, ignore_index=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    pickle.dump({"tab": tab, "native": native, "sources": sources, "scales": scales,
                 "tabR": pd.concat(rowsR, ignore_index=True), "scalesR": scalesR}, open(CACHE / "s1_kitti.pkl", "wb"))


def latency(native, drives):
    out = {}
    for name, (a, b) in LAT_PAIRS.items():
        parts = [W.lag_covariance(*native[d][a], *native[d][b], max_lag=1.0, dt=0.01, diff=0.2) for d in drives]
        out[name] = W.estimate_lag(parts)
    return out


def honesty_block(tab, models=None):
    res = {}
    for (pair, q), g in tab.groupby(["pair", "quantity"], sort=True):
        key = f"{pair} {q}"
        res[key] = {"published": W.honesty(g["z"])}
        if models is not None and key in models:
            m = W.SigmaModel.from_dict(models[key])
            res[key]["recalibrated"] = W.honesty(m.z(g["r"], g["v"]))
        res[key]["drives"] = int(g["drive"].nunique())
    return res


def dev():
    c = pickle.load(open(CACHE / "s1_kitti.pkl", "rb"))
    tab = c["tab"]
    train = sorted(d for d in GS.SCENE if GS.part_of(d) == "train")
    tr, va = tab[tab["part"] == "train"], tab[tab["part"] == "val"]
    models = {}
    for (pair, q), g in tr.groupby(["pair", "quantity"]):
        models[f"{pair} {q}"] = W.SigmaModel().fit(g["r"], g["v"]).to_dict()
    res = {"split": {"train": train, "val": GS.VAL, "test": GS.TEST}, "sources_per_drive": c["sources"],
           "can_sim_scales": c["scales"], "counts": tab.groupby(["pair", "quantity", "part"]).size().rename("n").reset_index().to_dict("records"),
           "latency_train": latency(c["native"], train),
           "train": honesty_block(tr, models), "val": honesty_block(va, models), "sigma_models": models}
    tR = c["tabR"]
    trR, vaR = tR[tR["part"] == "train"], tR[tR["part"] == "val"]
    modelsR = {f"{p} {q}": W.SigmaModel(bias="linear").fit(g["r"], g["v"]).to_dict() for (p, q), g in trR.groupby(["pair", "quantity"])}
    res["revised_R"] = {"design": "R1 linear bias + R2 one-vehicle CAN scale + R4 forward-displacement speed (notes 2026-10-22)",
                        "vehicle_scale": VEHICLE_SCALE, "can_sim_scales": c["scalesR"],
                        "train": honesty_block(trR, modelsR), "val": honesty_block(vaR, modelsR), "sigma_models": modelsR}
    (OUT / "s1_kitti_dev.json").write_text(json.dumps(res, indent=1))
    sm = json.loads((OUT / "s1_sigma_models.json").read_text()) if (OUT / "s1_sigma_models.json").exists() else {}
    sm["kitti"] = {"fitted_on": "KITTI train drives (WP1 split), clean phase-0 runs", "models": models}
    sm["kitti_R"] = {"fitted_on": "KITTI train drives, revised design R (R1 + R2 + R4)", "models": modelsR}
    (OUT / "s1_sigma_models.json").write_text(json.dumps(sm, indent=1))
    for k, v in res["val"].items():
        print(k, v)
    for k, v in res["revised_R"]["val"].items():
        print("R", k, v)
    print(res["latency_train"])


def test():
    c = pickle.load(open(CACHE / "s1_kitti.pkl", "rb"))
    tab = c["tab"]
    sm = json.loads((OUT / "s1_sigma_models.json").read_text())
    tR = c["tabR"]
    res = {"note": "computed once after s1_kitti_dev.json; not used for any choice",
           "test": honesty_block(tab[tab["part"] == "test"], sm["kitti"]["models"]),
           "test_revised_R": honesty_block(tR[tR["part"] == "test"], sm["kitti_R"]["models"]),
           "latency_test": latency(c["native"], GS.TEST)}
    (OUT / "s1_kitti_test.json").write_text(json.dumps(res, indent=1))
    for k, v in res["test"].items():
        print(k, v)


if __name__ == "__main__":
    {"build": build, "dev": dev, "test": test}[sys.argv[1]]()
