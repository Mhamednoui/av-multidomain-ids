"""WP8 S5 follow-up: stream vs batch on ARRIVAL order for the V2AIX egos with out-of-order CAMs (np.lexsort((t, track)) replaced by arrival rank inside the layer code). Output results/WP8/S5/v2x_arrival.json"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools"))
import numpy as np
import WP8_S5_v2x as W
from system.v2x_runner import V2XPhysicsDomain, LAYER_NAMES
from v2x import v2aix, v2aix_eval

_orig = np.lexsort
def _arrival(keys, *a, **k):
    if isinstance(keys, tuple) and len(keys) == 2 and keys[0].dtype.kind == "f" and keys[1].dtype.kind in "iu":
        keys = (np.arange(len(keys[0])), keys[1])
    return _orig(keys, *a, **k)

dom = V2XPhysicsDomain.load(W.FROZEN)
paths = {v2aix.recording_id(p): p for p in v2aix.list_recordings()}
res = []
for f in sorted((W.OUT / "parts").glob("v2x_Mobile*.json")):
    r = json.load(open(f))
    if r["reordered"] == 0:
        continue
    df = v2aix.load_recording(paths[r["ego"]])
    order = np.lexsort((np.arange(len(df)), df["recv_s"].to_numpy(float)))
    sdf = df.iloc[order].reset_index(drop=True)
    np.lexsort = _arrival
    try:
        braw = v2aix_eval.raws(dom.tracker, sdf)
        out, _ = W.run_ego(dom, sdf, {c: np.asarray(braw[c]) for c in LAYER_NAMES}, True, sdf["recv_s"].to_numpy(float))
    finally:
        np.lexsort = _orig
    res.append({"ego": r["ego"], "messages": out["messages"], "mismatch_rows_vs_arrival_batch": out["mismatch_rows"], "evidence_alarm_mismatch": out["evidence_alarm_mismatch"],
                "evidence_layer_or_reason_mismatch": out["evidence_layer_or_reason_mismatch"], "mismatch_rows_vs_time_sorted_batch": r["mismatch_rows"]})
    print(res[-1], flush=True)
(W.OUT / "v2x_arrival.json").write_text(json.dumps(res, indent=1))
