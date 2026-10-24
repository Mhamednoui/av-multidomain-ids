"""WP6 S5 stage 1: tick packs for the M2 system (fusion/streams.py format), built with the S3 stream code (tools/WP6_S3_streams.py, PREFIX = "s5").
- cross_comma: S2b inst |z| WITHOUT the comma CAN glitch filter (dropped, ORCHESTRATOR 2026-10-24 (1)).
- network, v2x: the S3 series plus the per-tick sample count ("count") and the per-group clean per-sample combined scores ("clean_samples") for the density model.
- lidar: reduced to the label-free L1 union (the supervised interim XGB is out of the M2 system, ORCHESTRATOR 2026-10-24 WP6 decisions (4)).
gps, can, cross_kitti are used as cached in S3 (s3_*.pkl). Checks: v2x / network tick scores identical to S3 (asserted); cross_comma clean ticks compared with S3.
Usage: python -u -W ignore tools/WP6_S5_streams.py [cross_comma network v2x lidar check]
Output: ../data_extra/cache_v3/WP6/s5_<name>.pkl
"""
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP6_S3_streams as S3  # noqa: E402

S3.PREFIX = "s5"
CACHE = S3.CACHE
log = S3.log


def stage_lidar():
    P = pickle.load(open(CACHE / "s3_lidar.pkl", "rb"))
    out = {}
    for part, p in P.items():
        j = p["layer_names"].index("lidar.l1_union")
        thr = float(np.asarray(p["layer_thr"])[j])
        q = {k: v for k, v in p.items() if k != "series"}
        q.update({"layer_names": ["lidar.l1_union"], "layer_thr": np.array([thr]), "dom_thr": thr, "status": "INTERIM, label-free L1 union only (WP3 S2)", "series": []})
        for s in p["series"]:
            t = dict(s)
            t["layers"] = s["layers"][:, j:j + 1].copy()
            t["score"] = t["layers"][:, 0].copy()
            q["series"].append(t)
        out[part] = q
    S3.save("lidar", out)


def check():
    res = {}
    for name in ("network", "v2x"):
        a, b = pickle.load(open(CACHE / f"s3_{name}.pkl", "rb")), pickle.load(open(CACHE / f"s5_{name}.pkl", "rb"))
        for part in ("val", "test"):
            sa, sb = a[part]["series"], b[part]["series"]
            assert [s["name"] for s in sa] == [s["name"] for s in sb], (name, part)
            d = max(float(np.abs(x["layers"] - y["layers"]).max()) for x, y in zip(sa, sb))
            assert d == 0.0, (name, part, d)
            assert all(len(y["count"]) == len(y["score"]) for y in sb)
            res[(name, part)] = d
    a, b = pickle.load(open(CACHE / "s3_cross_comma.pkl", "rb")), pickle.load(open(CACHE / "s5_cross_comma.pkl", "rb"))
    for part in ("val", "test"):
        sa = [s for s in a[part]["series"] if s["kind"] == "clean"]
        sb = [s for s in b[part]["series"] if s["kind"] == "clean"]
        fa = lambda ss: float(np.mean(np.concatenate([s["dom_alarm"] for s in ss])))
        log("cross_comma", part, "glitch", b[part].get("glitch_filter"), "clean dom-alarm rate S3 (filter)", round(fa(sa), 4), "S5 (no filter)", round(fa(sb), 4))
    log("identical layers (max diff):", res)


STAGES = {"cross_comma": lambda: S3.stage_cross_comma(glitch=False), "network": S3.stage_network, "v2x": S3.stage_v2x, "lidar": stage_lidar, "check": check}

if __name__ == "__main__":
    for s in sys.argv[1:] or list(STAGES):
        log("stage", s)
        STAGES[s]()
    log("done")
