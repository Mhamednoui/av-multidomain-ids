"""WP8 S7 vehicle-block sources: per run the GPS tick series (frozen v3 GPS domain), the cross-domain tick series (frozen cross recipe: the v3 recipe fitted on the v3 TRAIN drives / routes only,
pickled in the freeze as results/WP8/S7/frozen_cross31.pkl) and the blame verdicts of v3 (crossdomain.consistency.blame), v3.1 A1 and the labelled variant A3, exactly as
WP8_S2_build.stage_kveh / stage_cveh (same code), on the H31 records of tools/WP8_S7_kitti.py / WP8_S7_comma.py.
`--material val` is the dry run on the V31_val S6 records: the output must equal ../data_extra/cache_v3/WP8/S2/{kveh,cveh}.pkl (checked, array by array).
Output: ../data_extra/cache_v3/WP8/S7/{kveh,cveh}.pkl. Run: python -u -W ignore tools/WP8_S7_veh.py [--material h31|val] [--out DIR]"""
import argparse
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S7_lib as S7

import numpy as np

import WP8_S6_eval as E6
import WP6_S2_comma as SC
from crossdomain import blame31 as B
from crossdomain import consistency as CS
from system.cross_runner import DOMAIN_OF as K_DOMAIN_OF


def blame_str(b):
    return np.array([None if x is None else str(x) for x in b], object)


def build_k(records, fk):
    edges = fk["edges"]
    a1, a3 = B.Blame31(B.graph_k(False), B.EQUAL_COST), B.Blame31(B.graph_k(True), B.PRIOR_COST)
    out = {}
    for d, rs in sorted(records.items()):
        for r in rs:
            Z = E6.z_of(r["R"], r["V"], edges, fk["models"])
            S, es, al, ob = E6.cross_arrays(Z, fk["cal"])
            ca = al.any(axis=1)
            ia, io = fk["inertial"].edges(r["speed"], r["A"], ca)
            t = np.asarray(r["t"], float)
            lab = (t >= r["onset_t"]) if np.isfinite(r["onset_t"]) else np.zeros(len(t), bool)
            out[(d, int(r["phase"]), r["family"])] = {
                "t": t, "n": len(t), "label": lab, "onset_t": float(r["onset_t"]), "gps_score": np.asarray(r["gps_score"], np.float32), "gps_alarm": np.asarray(r["gps_alarm"], bool),
                "cross_score": es.max(axis=1).astype(np.float32), "cross_alarm": ca, "cross_layers": es.astype(np.float32), "cross_layer_alarm": al, "cross_present": ob.any(axis=1),
                "blame_A1": blame_str(B.blame_run(a1, al, ob, ca)), "blame_A3": blame_str(B.blame_run(a3, al, ob, ca, ia, io)),
                "blame_V3": blame_str([x if a else None for x, a in zip(CS.blame(edges, al, ob, K_DOMAIN_OF), ca)])}
        print("kveh", d, len(out), flush=True)
    return {"series": out, "edges": [e.name for e in edges], "tau_cross": float(fk["cal"].tau)}


def build_c(routes, fc):
    edges = fc["edges"]
    a1 = B.Blame31(B.graph_c(), B.EQUAL_COST)
    out = {}
    for n, d in sorted(routes.items()):
        k = "g10" if d["gyro_hz"] <= 20 else "g100"
        for ep in d["episodes"]:
            Z = E6.z_of(ep["R"], ep["V"], edges, fc["models"][k])
            S, es, al, ob = E6.cross_arrays(Z, fc["cal"])
            ca = al.any(axis=1)
            t = np.asarray(ep["t"], float)
            lab = (t >= ep["onset_t"]) if np.isfinite(ep["onset_t"]) else np.zeros(len(t), bool)
            out[(n, int(ep["window"]), ep["family"], int(ep["rep"]))] = {
                "t": t, "n": len(t), "label": lab, "onset_t": float(ep["onset_t"]), "cross_score": es.max(axis=1).astype(np.float32), "cross_alarm": ca,
                "cross_layers": es.astype(np.float32), "cross_layer_alarm": al, "cross_present": ob.any(axis=1), "blame_A1": blame_str(B.blame_run(a1, al, ob, ca)),
                "blame_V3": blame_str([x if a else None for x, a in zip(CS.blame(edges, al, ob, SC.DOMAIN_OF), ca)])}
        print("cveh", n, len(out), flush=True)
    return {"series": out, "edges": [e.name for e in edges], "tau_cross": float(fc["cal"].tau)}


def load_h31():
    recs, routes = {}, {}
    for f in sorted(S7.CACHE.glob("kitti_*.pkl")):
        z = pickle.load(open(f, "rb"))
        recs[z["drive"]] = z["records"]
    for f in sorted(S7.CACHE.glob("comma_*.pkl")):
        z = pickle.load(open(f, "rb"))
        routes[z["route"]] = z
    return recs, routes


def same(a, b):
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, np.ndarray):
        return a.shape == b.shape and (np.array_equal(a, b) if a.dtype != object else all((x == y) or (x is None and y is None) for x, y in zip(a.ravel(), b.ravel())))
    return a == b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--material", default="h31")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    fits = pickle.load(open(S7.OUT / "frozen_cross31.pkl", "rb"))
    if a.material == "val":
        tk, vk = E6.load_k()
        tc, vc = E6.load_c()
        recs, routes, out = vk, vc, Path(a.out)
        # the fits of the freeze must equal a fresh fit on the same train records
        fk2 = E6.fit_k(tk)
        assert np.allclose(fk2["cal"].tau, fits["K"]["cal"].tau), "frozen cross fit differs from a fresh fit on the V31 train drives"
    else:
        S7.open_guard()
        recs, routes = load_h31()
        out = S7.CACHE
    out.mkdir(parents=True, exist_ok=True)
    S7.journal("S7", f"vehicle sources {a.material}: start", f"{len(recs)} drives, {len(routes)} routes")
    k = build_k(recs, fits["K"])
    c = build_c(routes, fits["C"])
    pickle.dump(k, open(out / "kveh.pkl", "wb"), protocol=4)
    pickle.dump(c, open(out / "cveh.pkl", "wb"), protocol=4)
    if a.material == "val":
        s2k = pickle.load(open(S7.DATA_EXTRA / "cache_v3" / "WP8" / "S2" / "kveh.pkl", "rb"))
        s2c = pickle.load(open(S7.DATA_EXTRA / "cache_v3" / "WP8" / "S2" / "cveh.pkl", "rb"))
        print("kveh equals S2 cache:", same(k, s2k), " cveh equals S2 cache:", same(c, s2c), flush=True)
    S7.journal("S7", f"vehicle sources {a.material}: done", f"K runs {len(k['series'])}, C windows {len(c['series'])}")


if __name__ == "__main__":
    main()
