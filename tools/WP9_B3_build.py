"""WP9 B3 step 2: feature tables for the B3 parts (train / val; test only when asked, at the single scoring).

Run from codes_v3/:  python -I -u -W ignore tools/WP9_B3_build.py --parts train val [--cache DIR]
Uses locks/WP9_veremi.json (sender lists per part), v2x.l4.feature_table (v3 L4 features) and raw message fields.
Kalman noise (sp, sv, sa) is refit on B3-train genuine rows (results/WP9/B3_tracker.json); resumable: finished parts are skipped.
Cache (outside the repo): <cache>/<part>_feat.npy (float32), <part>_meta.pkl, columns.json.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd

from v2x import adapters, l3, l4

CACHE = ROOT.parent / "data_extra" / "cache_v3" / "WP9" / "B3"
OUT = ROOT / "results" / "WP9"
LOCK = ROOT / "locks" / "WP9_veremi.json"
BLOCK_S = 1800.0
RAW = ["x", "y", "speed", "hcos", "hsin", "acl", "pos_sigma", "spd_sigma", "acl_sigma"]


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def raw_fields(df):
    return pd.DataFrame({"x": df["x"], "y": df["y"], "speed": df["speed"], "hcos": np.cos(df["heading"]), "hsin": np.sin(df["heading"]),
                         "acl": df["acl"], "pos_sigma": df["pos_sigma"], "spd_sigma": df["spd_sigma"], "acl_sigma": df["acl_sigma"]}).astype(np.float32)


def main():
    parts = sys.argv[sys.argv.index("--parts") + 1:] if "--parts" in sys.argv else ["train", "val"]
    parts = [p for p in parts if not p.startswith("--")]
    cache = Path(sys.argv[sys.argv.index("--cache") + 1]) if "--cache" in sys.argv else CACHE
    cache.mkdir(parents=True, exist_ok=True)
    lock = json.loads(LOCK.read_text())
    todo = [p for p in parts if not (cache / f"{p}_feat.npy").exists()]
    if not todo:
        log("nothing to do", parts)
        return
    log("loading VeReMi")
    v = adapters.load_veremi()
    first_t = v.groupby("sender")["t"].min()
    v["block"] = v["sender"].map((first_t // BLOCK_S).astype(int))
    ids = {p: set(map(str, lock["sender_ids"][p])) for p in ("train", "val", "test")}
    tpath = OUT / "B3_tracker.json"
    if tpath.exists():
        tracker = l3.Tracker(l3.KalmanParams(**json.loads(tpath.read_text())["params"]))
    else:
        tr = v[v["sender"].isin(ids["train"]) & (v["label"] == 0)]
        tracker = l3.Tracker()
        t0 = time.time()
        info = tracker.fit(tr)
        assert set(info["senders_used"]) <= ids["train"]
        info.pop("senders_used")
        tpath.write_text(json.dumps({"params": tracker.params.to_dict(), "info": info, "fit_rows": "B3 train genuine"}, indent=1))
        log("tracker fitted on B3 train genuine", tracker.params.to_dict(), info, f"{time.time() - t0:.0f}s")
    cols = None
    for p in todo:
        d = v[v["sender"].isin(ids[p])].reset_index(drop=True)
        log(p, "rows", len(d), "senders", d["sender"].nunique())
        t0 = time.time()
        F = l4.feature_table(d, tracker)
        F = pd.concat([F, raw_fields(d)], axis=1)
        kinds = l4.row_kinds(d)
        cols = list(F.columns)
        meta = pd.DataFrame({"label": d["label"].to_numpy().astype(np.int16), "sender": d["sender"].astype(np.int64).to_numpy(), "pseudo": d["pseudo"].astype(np.int64).to_numpy(),
                             "t": d["t"].to_numpy(), "block": d["block"].to_numpy().astype(np.int16), "kind": kinds.astype(np.int8)})
        np.save(cache / f"{p}_feat.tmp.npy", F.to_numpy(np.float32))
        meta.to_pickle(cache / f"{p}_meta.pkl")
        (cache / f"{p}_feat.tmp.npy").replace(cache / f"{p}_feat.npy")
        (cache / "columns.json").write_text(json.dumps(cols))
        log(p, "features done", f"{time.time() - t0:.0f}s", "attack share", float((meta["label"] > 0).mean()))


if __name__ == "__main__":
    main()
