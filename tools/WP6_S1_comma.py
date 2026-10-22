"""WP6 S1 comma2k19: CAN-vs-GNSS speed relation, CAN wheel-speed unit, latency, normalised residuals, sigma honesty.

Stages (python -u -W ignore tools/WP6_S1_comma.py <stage>); the data files are read with np.load(allow_pickle=False):
  build : load the 20 routes of Chunk_1 (native-rate arrays) -> ../data_extra/cache_v3/WP6/s1_comma_routes.pkl
  dev   : on TRAIN routes: gyro yaw axis / sign, latency per pair (a = gnss), CAN/GNSS scale, raw 0xAA unit fit;
          residual tables (lag-corrected, 1 Hz interval means) for train / val / test, SigmaModel fitted on TRAIN,
          honesty on TRAIN and VAL -> results/WP6/s1_comma_dev.json (+ s1_sigma_models.json["comma"]); grids cached.
  test  : ONCE, after dev: honesty on TEST routes -> results/WP6/s1_comma_test.json.
Split by route (crossdomain.comma.split_routes, fixed before results).
"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import DATA_EXTRA, results_dir  # noqa: E402
from crossdomain import comma as C  # noqa: E402
from crossdomain import witness as W  # noqa: E402

CACHE = DATA_EXTRA / "cache_v3" / "WP6"
OUT = results_dir("WP6")
SPEED_PAIRS = [("gnss", "can"), ("gnss", "wheel")]
MIN_SCALE_SPEED = 5.0


def build():
    rs = C.routes()
    sp = C.split_routes(rs)
    part = {r.name: p for p, lst in sp.items() for r in lst}
    data = {}
    for r in rs:
        data[r.name] = C.load_route(r)
        d = data[r.name]
        print(r.name, part[r.name], len(d["segments"]), len(d["can_t"]), len(d["gnss_t"]), len(d["gyro_t"]), len(d["raw_wheel_t"]), flush=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    pickle.dump({"data": data, "part": part}, open(CACHE / "s1_comma_routes.pkl", "wb"))


def grid_of(r):
    t0 = max(r["can_t"][0], r["gnss_t"][0], r["gyro_t"][0])
    t1 = min(r["can_t"][-1], r["gnss_t"][-1], r["gyro_t"][-1])
    return np.arange(np.ceil(t0) + 1.0, np.floor(t1) - 1.0, 1.0)


def choose_gyro(data, train):
    """Gyro axis / sign with the largest |correlation| with the GNSS bearing-rate yaw (1 Hz interval means), train routes."""
    best = {}
    for ax in range(3):
        xs, ys = [], []
        for n in train:
            r = data[n]
            f = C.frames(r, gyro_axis=ax)
            g = grid_of(r)
            a = W.to_grid(f["gnss_yaw"], g, kind="inst")["yaw_rate"].to_numpy()
            b = W.to_grid(f["imu"], g, kind="inst")["yaw_rate"].to_numpy()
            ok = np.isfinite(a) & np.isfinite(b)
            xs.append(a[ok]); ys.append(b[ok])
        x, y = np.concatenate(xs), np.concatenate(ys)
        best[ax] = float(np.corrcoef(x, y)[0, 1])
    ax = max(best, key=lambda k: abs(best[k]))
    return ax, float(np.sign(best[ax])), best


def latency(data, names, gyro):
    pairs = {"gnss-can speed": ("gnss_t", "gnss_v", "can_t", "can_v"), "gnss-wheel speed": ("gnss_t", "gnss_v", "wheel_t", "wheel_v")}
    out = {}
    for k, (ta, a, tb, b) in pairs.items():
        out[k] = W.estimate_lag([W.lag_covariance(data[n][ta], data[n][a], data[n][tb], data[n][b], max_lag=2.0, dt=0.02, diff=0.4)
                                 for n in names])
    parts = []
    for n in names:
        r = data[n]
        ty, wy = C.gnss_yaw_rate(r["gnss_t"], r["gnss_bearing"], r["gnss_v"])
        parts.append(W.lag_covariance(ty, wy, r["gyro_t"], gyro[1] * r["gyro"][:, gyro[0]], max_lag=2.0, dt=0.02, diff=0.4))
    out["gnss-imu yaw_rate"] = W.estimate_lag(parts)
    return out


def tables(data, part, gyro, lags):
    rows = []
    for n, r in data.items():
        f = C.frames(r, gyro_axis=gyro[0], gyro_sign=gyro[1])
        g = grid_of(r)
        G = {"gnss": W.to_grid(f["gnss"], g, kind="inst"), "can": W.to_grid(f["can"], g, kind="inst", lag=lags["gnss-can speed"]),
             "wheel": W.to_grid(f["wheel"], g, kind="inst", lag=lags["gnss-wheel speed"]),
             "imu": W.to_grid(f["imu"], g, kind="inst", lag=lags["gnss-imu yaw_rate"])}
        G["gnss"]["yaw_rate"] = W.to_grid(f["gnss_yaw"], g, kind="inst")["yaw_rate"].to_numpy()
        parts = [W.pair_table(G[a], G[b], a, b, "speed") for a, b in SPEED_PAIRS]
        G["imu"]["speed"] = G["gnss"]["speed"].to_numpy()        # speed of the pair for the sigma model
        # yaw has no published sigma on comma: keep the rows (r, v) for the train-fitted model, s / z = NaN
        yaw = W.pair_table(G["gnss"], G["imu"], "gnss", "imu", "yaw_rate", sa=np.ones(len(g)), sb=np.zeros(len(g)))
        yaw["s"], yaw["z"] = np.nan, np.nan
        tab = pd.concat(parts + [yaw], ignore_index=True)
        tab["route"], tab["part"] = n, part[n]
        rows.append(tab)
    return pd.concat(rows, ignore_index=True)


def scale_fit(data, names, tkey, vkey, n_boot=500, seed=42):
    """Slope through the origin of the 1 Hz CAN speed on the 1 Hz GNSS speed (v_gnss > 5 m/s); bootstrap over routes."""
    per = []
    for n in names:
        r = data[n]
        g = grid_of(r)
        fa = pd.DataFrame({"t": r["gnss_t"], "source": "gnss", "speed": r["gnss_v"], "yaw_rate": np.nan, "dx": np.nan, "dy": np.nan, "sigma": 0.0})
        fb = pd.DataFrame({"t": r[tkey], "source": "can", "speed": r[vkey], "yaw_rate": np.nan, "dx": np.nan, "dy": np.nan, "sigma": 0.0})
        a = W.to_grid(fa, g, kind="inst")["speed"].to_numpy()
        b = W.to_grid(fb, g, kind="inst")["speed"].to_numpy()
        ok = np.isfinite(a) & np.isfinite(b) & (a > MIN_SCALE_SPEED)
        per.append((float(a[ok] @ b[ok]), float(a[ok] @ a[ok]), int(ok.sum())))
    P = np.array(per)
    slope = P[:, 0].sum() / P[:, 1].sum()
    rng = np.random.default_rng(seed)
    bs = [P[i, 0].sum() / P[i, 1].sum() for i in (rng.integers(0, len(P), len(P)) for _ in range(n_boot))]
    return {"slope": float(slope), "ci95": [float(x) for x in np.percentile(bs, [2.5, 97.5])], "n": int(P[:, 2].sum()),
            "per_route": [float(p[0] / p[1]) if p[1] > 0 else None for p in per]}


def raw_unit_fit(data, names):
    """Least squares raw_count_mean = k * v_gnss_kmh + c on 1 Hz interval means (v_gnss > 5 m/s): k = counts per km/h (1 / unit),
    -c / k = offset (km/h). Toyota convention (opendbc): unit 0.01 km/h (k = 100), offset -67.67 km/h (c = 6767)."""
    X, Y = [], []
    for n in names:
        r = data[n]
        g = grid_of(r)
        cnt = C.raw_wheel_counts(r["raw_wheel_B"]).mean(1).astype(float)
        fa = pd.DataFrame({"t": r["gnss_t"], "source": "gnss", "speed": r["gnss_v"], "yaw_rate": np.nan, "dx": np.nan, "dy": np.nan, "sigma": 0.0})
        fb = pd.DataFrame({"t": r["raw_wheel_t"], "source": "can", "speed": cnt, "yaw_rate": np.nan, "dx": np.nan, "dy": np.nan, "sigma": 0.0})
        a = W.to_grid(fa, g, kind="inst")["speed"].to_numpy() * 3.6
        b = W.to_grid(fb, g, kind="inst")["speed"].to_numpy()
        ok = np.isfinite(a) & np.isfinite(b) & (a > MIN_SCALE_SPEED * 3.6)
        X.append(a[ok]); Y.append(b[ok])
    x, y = np.concatenate(X), np.concatenate(Y)
    k, c = np.polyfit(x, y, 1)
    res = y - (k * x + c)
    # same counts decoded with comma's own decoded wheel speed: exact unit check (no GNSS noise)
    cnt_all, ws_all = [], []
    for n in names:
        r = data[n]
        cnt = C.raw_wheel_counts(r["raw_wheel_B"]).mean(1).astype(float)
        ws = np.interp(r["raw_wheel_t"], r["wheel_t"], r["wheel_v"]) * 3.6
        cnt_all.append(cnt); ws_all.append(ws)
    k2, c2 = np.polyfit(np.concatenate(ws_all), np.concatenate(cnt_all), 1)
    return {"vs_gnss": {"counts_per_kmh": float(k), "unit_kmh_per_count": float(1 / k), "offset_kmh": float(-c / k), "resid_std_counts": float(res.std()), "n": int(len(x))},
            "vs_comma_decoded": {"counts_per_kmh": float(k2), "unit_kmh_per_count": float(1 / k2), "offset_kmh": float(-c2 / k2)}}


def honesty_block(tab, models):
    res = {}
    for (pair, q), g in tab.groupby(["pair", "quantity"], sort=True):
        key = f"{pair} {q}"
        res[key] = {"published": W.honesty(g["z"]) if g["z"].notna().any() else {"n": int(len(g)), "honest": None, "note": "no published sigma"}}
        if key in models:
            m = W.SigmaModel.from_dict(models[key])
            res[key]["recalibrated"] = W.honesty(m.z(g["r"], g["v"]))
        res[key]["routes"] = int(g["route"].nunique())
    return res


def dev():
    c = pickle.load(open(CACHE / "s1_comma_routes.pkl", "rb"))
    data, part = c["data"], c["part"]
    train = sorted(n for n in data if part[n] == "train")
    ax, sg, corr = choose_gyro(data, train)
    gyro = (ax, sg)
    lat = latency(data, train, gyro)
    lags = {k: v["lag"] for k, v in lat.items()}
    tab = tables(data, part, gyro, lags)
    tr = tab[tab["part"] == "train"]
    models = {f"{p} {q}": W.SigmaModel().fit(g["r"], g["v"]).to_dict() for (p, q), g in tr.groupby(["pair", "quantity"])}
    res = {"split": {p: sorted(n for n in data if part[n] == p) for p in ("train", "val", "test")},
           "hours": {p: float(sum(data[n]["can_t"][-1] - data[n]["can_t"][0] for n in data if part[n] == p) / 3600) for p in ("train", "val", "test")},
           "gyro_choice": {"axis": ax, "sign": sg, "corr_per_axis": corr},
           "latency_train": lat, "counts": tab.groupby(["pair", "quantity", "part"]).size().rename("n").reset_index().to_dict("records"),
           "scale_train": {"can": scale_fit(data, train, "can_t", "can_v"), "wheel": scale_fit(data, train, "wheel_t", "wheel_v")},
           "scale_val": {"can": scale_fit(data, sorted(n for n in data if part[n] == "val"), "can_t", "can_v"),
                         "wheel": scale_fit(data, sorted(n for n in data if part[n] == "val"), "wheel_t", "wheel_v")},
           "raw_unit_train": raw_unit_fit(data, train),
           "train": honesty_block(tr, models), "val": honesty_block(tab[tab["part"] == "val"], models), "sigma_models": models}
    modelsR = {f"{p} {q}": W.SigmaModel(bias="linear").fit(g["r"], g["v"]).to_dict() for (p, q), g in tr.groupby(["pair", "quantity"])}
    res["revised_R"] = {"design": "R1 linear bias (notes 2026-10-22)", "train": honesty_block(tr, modelsR),
                        "val": honesty_block(tab[tab["part"] == "val"], modelsR), "sigma_models": modelsR}
    (OUT / "s1_comma_dev.json").write_text(json.dumps(res, indent=1))
    sm = json.loads((OUT / "s1_sigma_models.json").read_text()) if (OUT / "s1_sigma_models.json").exists() else {}
    sm["comma"] = {"fitted_on": "comma2k19 Chunk_1 train routes", "models": models, "lags": lags, "gyro": {"axis": ax, "sign": sg}}
    sm["comma_R"] = {"fitted_on": "comma2k19 Chunk_1 train routes, revised design R1", "models": modelsR, "lags": lags, "gyro": {"axis": ax, "sign": sg}}
    (OUT / "s1_sigma_models.json").write_text(json.dumps(sm, indent=1))
    tab.to_pickle(CACHE / "s1_comma_tab.pkl")
    for k in ("gyro_choice", "latency_train", "scale_train", "scale_val", "raw_unit_train"):
        print(k, res[k])
    for k, v in res["val"].items():
        print("val", k, v)
    for k, v in res["revised_R"]["val"].items():
        print("val R", k, v)


def test():
    tab = pd.read_pickle(CACHE / "s1_comma_tab.pkl")
    sm = json.loads((OUT / "s1_sigma_models.json").read_text())
    models = sm["comma"]["models"]
    c = pickle.load(open(CACHE / "s1_comma_routes.pkl", "rb"))
    te = sorted(n for n in c["data"] if c["part"][n] == "test")
    res = {"note": "computed once after s1_comma_dev.json; not used for any choice", "test": honesty_block(tab[tab["part"] == "test"], models),
           "test_revised_R": honesty_block(tab[tab["part"] == "test"], sm["comma_R"]["models"]),
           "scale_test": {"can": scale_fit(c["data"], te, "can_t", "can_v"), "wheel": scale_fit(c["data"], te, "wheel_t", "wheel_v")}}
    (OUT / "s1_comma_test.json").write_text(json.dumps(res, indent=1))
    for k, v in res["test"].items():
        print(k, v)
    for k, v in res["test_revised_R"].items():
        print("R", k, v)
    print(res["scale_test"])


if __name__ == "__main__":
    {"build": build, "dev": dev, "test": test}[sys.argv[1]]()
