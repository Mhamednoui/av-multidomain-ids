"""WP8 S7 regression R2 (before any H31 file is opened): the frozen v3 loaders reproduce the stored v3 numbers on VALIDATION / v3-split material that is not H31.
Checks (each writes pass / max |diff| into results/WP8/S7/regression.json):
  fusion    load_system(2) on the S6 fixture (results/WP8/S6/regression_fixture.json): identical to 1e-12 (the same check as tests/v31/test_s6_regression.py)
  gps       tools/WP8_S6_kitti.build_drive re-run on V31_val drives 0005 and 0095 (frozen v3 GPS domain, frozen CAN decoder, cross residual tables): identical to the stored S6 records
  comma     tools/WP8_S6_comma.build_route re-run on one V31_val route: identical to the stored S6 record
  lidar     the literal frozen v3 LidarDomain (results/WP3/S9/frozen_lidar) on the first 24 scans of results/WP8/S3/equiv_rows.jsonl: v3 stat identical to the stored value; the fast-path statistics
            (lidar.fast, numba) of the same scans give the same stat (the v3 side of S7 uses the fast statistics)
  can       CanDomain.score_capture on a V31_val ROAD capture vs results/WP8/scores/S5/can_val_<capture>.npz batch_score (exact)
  network   frozen v3 NetworkDomain on D10 VALIDATION: macro / FA of results/WP8/S7/regress/network_val.json (tools/WP8_S7_net.py --split val) vs results/WP8/S4/s4_val_candidates.json (exact), F1 and RC5 too
  v2x       V2XPhysicsDomain.load: thresholds equal domain.json; VeReMi validation ego sources (tools/WP8_S7_v2x.py --split val) equal ../data_extra/cache_v3/WP8/S2/v2x.pkl
  numbers on re-used material (D10 test, VeReMi test, ROAD test): reproduced inside the H31 scoring itself (it IS the same material); see the report
Run: python -u -W ignore tools/WP8_S7_regress.py [check ...]"""
import json
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S7_lib as S7

import numpy as np

RES = S7.OUT / "regression.json"


def rec_equal(a, b):
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(rec_equal(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(rec_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, np.ndarray):
        return a.shape == b.shape and (np.array_equal(a, b, equal_nan=True) if a.dtype.kind in "fc" else bool((a == b).all()))
    if isinstance(a, float):
        return a == b or (np.isnan(a) and np.isnan(b))
    return a == b


def chk_fusion():
    import WP8_S6_fixture as F
    ref = json.loads((S7.ROOT / "results" / "WP8" / "S6" / "regression_fixture.json").read_text())
    cur = F.run_fixture()
    d, ok = 0.0, True
    for fam in ("K", "C"):
        ok &= cur[fam]["alarm"] == ref[fam]["alarm"] and cur[fam]["blame"] == ref[fam]["blame"] and cur[fam]["events"] == ref[fam]["events"] and cur[fam]["threshold"] == ref[fam]["threshold"]
        d = max(d, float(np.abs(np.array(cur[fam]["score"]) - np.array(ref[fam]["score"])).max()))
    return {"pass": bool(ok and d <= 1e-12), "max_abs_score_diff": d}


def chk_gps():
    import WP8_S6_kitti as K6
    from can.domain import CanDomain
    from gps.domain import GPSDomain
    dom_can = CanDomain.load(S7.ROOT / "results" / "WP2" / "s7_domain")
    gdom = GPSDomain.load(S7.ROOT / "results" / "WP1" / "frozen_gps")
    res = {}
    for d in ("0005", "0095"):
        z = pickle.load(open(K6.CACHE / f"kitti_{d}.pkl", "rb"))
        new = K6.build_drive(d, dom_can, gdom, True)
        res[d] = bool(rec_equal(z["records"], new))
    return {"pass": all(res.values()), "drives": res}


def chk_comma():
    import json as js
    import WP8_S6_comma as C6
    train, val = C6.lock_routes()
    allr = sorted(train + val)
    n = val[0]
    sm = js.loads((S7.ROOT / "results" / "WP6" / "s1_sigma_models.json").read_text())["comma_R"]
    new = C6.build_route(n, allr.index(n), True, sm["lags"], (sm["gyro"]["axis"], sm["gyro"]["sign"]))
    old = pickle.load(open(C6.CACHE / f"comma_{n}.pkl", "rb"))
    return {"pass": bool(rec_equal(old, new)), "route": n}


def chk_lidar():
    import pandas as pd
    from lidar import ego
    from lidar.data import load, scan_files
    from lidar.domain import COLS, LidarDomain
    from lidar.fast import PrevScan
    from lidar.s4_build import attack_cases
    import WP8_S7_lidar as T
    g = T.objs()
    rows = [json.loads(x) for x in open(S7.ROOT / "results" / "WP8" / "S3" / "equiv_rows.jsonl")][:24]
    v3 = LidarDomain.load(S7.ROOT / "results" / "WP3" / "S9" / "frozen_lidar")
    dl, df_ = 0.0, 0.0
    for r in rows:
        d, i, kind = r["drive"], r["i"], r["kind"]
        files, pose = scan_files(d), ego.poses(d)
        pts = load(files[i])
        if kind != "clean":
            pts = {n: a for n, a, _ in attack_cases(pts, np.random.default_rng([83, int(d), i]), g["table"], g["calib"])}[kind]
        prev = PrevScan(load(files[i - 1]), pose[i - 1])
        raw3, _ = v3.raw_scores(pts, pose[i], (prev.pts, prev.pose))
        stat = float(v3.stack.stat(pd.DataFrame([{c: raw3[c[4:]] for c in COLS}]))[0])
        dl = max(dl, abs(stat - r["v3_stat"]))
        out, _ = T.score_scan(pts, pose[i], prev, 0.0, i)
        df_ = max(df_, abs(out["v3_stat"] - r["vox_stat"]))
    return {"pass": bool(dl <= 1e-12 and df_ <= 1e-12), "literal_v3_vs_stored_max_diff": dl, "fast_path_v3_vs_stored_vox_max_diff": df_, "scans": len(rows)}


def chk_can():
    from can import adapters as A
    from can.domain import CanDomain
    import WP8_S5_can as C5
    name = "fuzzing_attack_2"
    caps = A.road_captures()
    dom = CanDomain.load(S7.ROOT / "results" / "WP2" / "s7_domain")
    t, ids, dlc, B, lab = C5.load(name, caps)
    comb, per = dom.score_capture(t, ids, dlc, B, name=name, explain=True)
    z = np.load(S7.ROOT / "results" / "WP8" / "scores" / "S5" / f"can_val_{name}.npz")
    d = float(np.abs(np.array([e.score for e in comb]) - z["batch_score"]).max())
    return {"pass": bool(d == 0.0 and len(comb) == len(z["batch_score"])), "capture": name, "max_abs_diff": d, "windows": len(comb)}


def chk_network():
    f = S7.OUT / "regress" / "network_val.json"
    if not f.exists():
        raise RuntimeError("run tools/WP8_S7_net.py --split val --out results/WP8/S7/regress first")
    new = json.loads(f.read_text())["candidates"]
    old = json.loads((S7.ROOT / "results" / "WP8" / "S4" / "s4_val_candidates.json").read_text())["candidates"]
    out = {}
    for n in ("v3", "F1", "RC5"):
        out[n] = {"macro_new": new[n]["macro"], "macro_stored": old[n]["macro"], "fa_new": new[n]["fa"], "fa_stored": old[n]["fa"], "detection_equal": new[n]["detection"] == old[n]["detection"]}
    return {"pass": all(abs(v["macro_new"] - v["macro_stored"]) <= 1e-12 and abs(v["fa_new"] - v["fa_stored"]) <= 1e-12 and v["detection_equal"] for v in out.values()), "candidates": out}


def chk_v2x():
    from system.v2x_runner import V2XPhysicsDomain
    dom = V2XPhysicsDomain.load(S7.ROOT / "results" / "WP7" / "frozen_v2x")
    js = json.loads((S7.ROOT / "results" / "WP7" / "frozen_v2x" / "domain.json").read_text())
    thr_ok = abs(dom.comb_thr - js["combined_threshold"]) <= 1e-12
    f = S7.OUT / "regress" / "v2x_val" / "v2x.pkl"
    same = None
    if f.exists():
        a = pickle.load(open(f, "rb"))
        b = pickle.load(open(S7.DATA_EXTRA / "cache_v3" / "WP8" / "S2" / "v2x.pkl", "rb"))
        same = len(a["series"]) == len(b["series"]) and all(rec_equal(x, y) for x, y in zip(a["series"], b["series"]))
    return {"pass": bool(thr_ok is not False and same is not False), "comb_thr_equals_domain_json": thr_ok, "veremi_val_sources_equal_S2_cache": same}


CHECKS = {"fusion": chk_fusion, "gps": chk_gps, "comma": chk_comma, "lidar": chk_lidar, "can": chk_can, "network": chk_network, "v2x": chk_v2x}


def main():
    names = sys.argv[1:] or list(CHECKS)
    res = json.loads(RES.read_text()) if RES.exists() else {}
    for n in names:
        S7.journal("S7", f"regression check {n}: start", "tools/WP8_S7_regress.py")
        try:
            res[n] = CHECKS[n]()
        except Exception as e:
            import traceback
            res[n] = {"pass": False, "error": traceback.format_exc()[-800:]}
        print(n, res[n], flush=True)
        S7.write_json(res, RES)
        S7.journal("S7", f"regression check {n}: done", f"pass={res[n]['pass']}")
    res["all_pass"] = all(v["pass"] for k, v in res.items() if isinstance(v, dict) and "pass" in v)
    S7.write_json(res, RES)


if __name__ == "__main__":
    main()
