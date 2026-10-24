"""WP6 S4 stage 1: the extra material the zero-day step needs on top of the S3 tick packs (fusion/streams.py format).
 net_o   network pack with stack O layers (H + net.dos_rate + net.l3_service + net.l3_ae), same D10 host view / blocks / minute hold as S3
         (tools/WP6_S3_streams.py stage_network); calibrations = WP4 S7 cal.pkl (frozen). 'score' = max of the four H layers (= S3 domain score).
 gps_l3  WP1 S7 L3 column (MCD, fit on normal rows only; out-of-fold on dev rows, final model on test rows; results/WP1/cache/s8_raw.pkl) aligned to the S3 GPS
         series by (run, t); ECDF calibrated on the clean VALIDATION rows (tier table only; gps_can runs have no L3 column and get NaN).
Usage: python -u -W ignore tools/WP6_S4_streams.py net_o gps_l3       Outputs: ../data_extra/cache_v3/WP6/s4_network.pkl, s4_gps_l3.pkl
Nothing is chosen here. References: notes/WP6_crossdomain.md "S4 start".
"""
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from common.calibration import ECDFCalibrator  # noqa: E402
from common.config import DATA_EXTRA  # noqa: E402
from fusion import streams as ST  # noqa: E402

CACHE = DATA_EXTRA / "cache_v3" / "WP6"
T0 = time.time()
HOST = 49


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def stage_net_o():
    from tools.WP4_S6_lib import load_s6
    from tools.WP4_S7_lib import COL, H, O, load_tables
    meta = json.loads((ROOT / "results" / "WP4" / "s7_domain" / "domain.json").read_text())
    thr = float(meta["combined_threshold"])
    d, _ = load_s6()
    ids = d[["src_id", "dst_id"]].to_numpy()
    val, test, cal = load_tables()
    lthr = np.array([cal[n][1] for n in O])
    packs = {}
    for part, tb in (("val", val), ("test", test)):
        pos = tb["pos"].to_numpy()
        m = (ids[pos, 0] == HOST) | (ids[pos, 1] == HOST)
        x = tb[m].reset_index(drop=True)
        L = np.column_stack([cal[n][0].transform(x[COL[n]].to_numpy(float)) for n in O]).astype(np.float32)
        fam = x["fam"].astype(str).to_numpy()
        att = fam != "BENIGN"
        mins = (x["t"].to_numpy(float) // 60).astype(np.int64)
        blk = x["day"].astype(str) + "|" + x["period"].astype(str)
        p = {"domain": "network", "layer_names": list(O), "layer_thr": lthr, "dom_thr": thr, "series": [], "host": "192.168.10.50 (id 49)", "n_flows": int(m.sum())}
        for b, idx in pd.Series(np.arange(len(x))).groupby(blk.to_numpy()).indices.items():
            mi = mins[idx]
            u, inv = np.unique(mi, return_inverse=True)
            V = ST.tick_max(inv, L[idx], len(u))
            lab = ST.tick_any(inv, att[idx], len(u))
            fm = ST.tick_family(inv, np.where(att[idx], fam[idx], ""), len(u))
            Vt, Lt, Ft = ST.hold_minutes(u, V, lab, fm, int(u.min()), int(u.max()) + 1)
            kind = "attack" if Lt.any() else "clean"
            fams = sorted(set(Ft[Lt]))
            s = ST.series(b, b, kind, ",".join(fams) if fams else "none", Vt[:, :len(H)].max(axis=1), Vt, Lt, fam=Ft)
            p["series"].append(s)
        packs[part] = p
        log("net_o", part, "host flows", int(m.sum()), "series", len(p["series"]))
    pickle.dump(packs, open(CACHE / "s4_network.pkl", "wb"))


def stage_gps_l3():
    raw = pd.read_pickle(ROOT / "results" / "WP1" / "cache" / "s8_raw.pkl")[["run", "t", "part", "attack", "opt.l3"]]
    raw["tk"] = np.round(raw["t"].to_numpy(float), 3)
    cal_rows = raw[(raw["part"] == "val") & (raw["attack"] == "none")]
    cal = ECDFCalibrator().fit(cal_rows["opt.l3"].to_numpy(float))
    s3 = pickle.load(open(CACHE / "s3_gps.pkl", "rb"))
    key = raw.set_index(["run", "tk"])["opt.l3"]
    key = key[~key.index.duplicated(keep="first")]
    out = {}
    for part in ("val", "test"):
        for s in s3[part]["series"]:
            idx = pd.MultiIndex.from_arrays([np.full(len(s["t"]), s["name"]), np.round(s["t"], 3)])
            v = key.reindex(idx).to_numpy(float)
            out[(part, s["name"])] = np.where(np.isnan(v), np.nan, cal.transform(np.nan_to_num(v))).astype(np.float32)
    cover = {part: float(np.mean([np.isfinite(out[(part, s['name'])]).mean() for s in s3[part]["series"] if s["family"] != "gps_can"])) for part in ("val", "test")}
    log("gps_l3 coverage (non gps_can series)", cover)
    pickle.dump({"l3": out, "cal": cal.to_dict(), "coverage": cover}, open(CACHE / "s4_gps_l3.pkl", "wb"))


if __name__ == "__main__":
    for st in sys.argv[1:]:
        {"net_o": stage_net_o, "gps_l3": stage_gps_l3}[st]()
