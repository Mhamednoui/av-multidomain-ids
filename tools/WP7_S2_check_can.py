"""WP7 S2 integrity check of the CAN pass: windows of the frame-by-frame CANRunner stream (tools/WP7_S2_can.py) equal the WP6 S3 batch pack window by window (score, alarm). The pack drops windows
the WP2 table marks not ok and collapses the gaps; the stream keeps time, so the comparison selects the ok windows through the table's `sec`. Output: results/WP7/S2_check_can.json."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP7_S2_lib as L

import numpy as np
import pandas as pd

from common.config import DATA_EXTRA

TAB = DATA_EXTRA / "WP2_S7_cache" / "tables" / "test"


def main():
    pack = pd.read_pickle(L.WP6C / "s3_can.pkl")["test"]
    pk = {s["name"]: s for s in pack["series"]}
    res = {}
    for f in ("S2_can_attack.pkl", "S2_can_ambient.pkl"):
        for s in L.load_pickle(f)["series"]:
            tab = dict(np.load(TAB / (s["name"] + ".npz")))
            ok = tab["ok"].astype(bool)
            ticks = tab["sec"][ok].astype(int) - int(s["sec0"])
            p = pk[s["name"]]
            sc = s["score"][ticks]
            res[s["name"]] = {"windows_pack": int(len(p["score"])), "windows_stream_ok": int(len(ticks)), "max_score_diff": float(np.abs(sc - np.asarray(p["score"])).max()),
                              "alarm_mismatch": int(((np.asarray(p["score"]) >= pack["dom_thr"]) != s["dom_alarm"][ticks]).sum()), "time_gaps_s": int(len(s["score"]) - len(ticks)),
                              "label_ticks": int(s["label"].sum()), "pack_label_ticks": int(np.asarray(p["label"]).sum())}
    (L.OUT / "S2_check_can.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: (v["max_score_diff"], v["alarm_mismatch"], v["time_gaps_s"]) for k, v in res.items()}))


if __name__ == "__main__":
    main()
