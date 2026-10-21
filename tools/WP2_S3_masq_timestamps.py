"""WP2 S3: data caveat check, are ROAD masquerade timestamps copied from the legitimate ECU?

For each ROAD masquerade capture: compare injected-frame timestamps with the same frames in the non-masquerade
capture, count legitimate frames of the injected ID in the attack interval (original vs masquerade), and give gap
statistics of the injected stream vs the same ID before the attack. No skew number is computed here.
Output: results/WP2/s3_road_masq_timestamps.json
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from can import adapters as A
from WP2_S2_run import dump
from common.config import RESULTS

caps = A.road_captures()
out = {}
for _, r in caps[caps.kind == "masquerade"].iterrows():
    base = r["name"].replace("_masquerade", "")
    m, o = A.load_road(r["name"], caps), A.load_road(base, caps)
    mi, oi = m[m.label == 1], o[o.label == 1]
    iid = int(r["meta"]["injection_id"], 16)
    a, b = r["meta"]["injection_interval"]
    gi = np.diff(mi.t.to_numpy())
    gp = np.diff(o[(o.id == iid) & (o.t < a - 1)].t.to_numpy())
    out[r["name"]] = {
        "part": r["part"], "injected_id": hex(iid), "interval_s": [a, b], "n_injected_masq": int(len(mi)), "n_injected_orig": int(len(oi)),
        "frac_injected_timestamps_identical": float(np.isin(np.round(mi.t.to_numpy(), 6), np.round(oi.t.to_numpy(), 6)).mean()),
        "legit_frames_of_id_in_interval_orig": int(((o.id == iid) & (o.label == 0) & (o.t >= a) & (o.t <= b)).sum()),
        "legit_frames_of_id_in_interval_masq": int(((m.id == iid) & (m.label == 0) & (m.t >= a) & (m.t <= b)).sum()),
        "gap_injected_median_s": float(np.median(gi)), "gap_injected_std_s": float(gi.std()),
        "gap_pre_attack_median_s": float(np.median(gp)), "gap_pre_attack_std_s": float(gp.std())}
dump(out, RESULTS / "WP2" / "s3_road_masq_timestamps.json")
print("ok", len(out))
