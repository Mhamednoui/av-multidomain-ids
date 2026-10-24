"""WP6 S5b post-test DIAGNOSTIC (no choice depends on it): what the clean SAFE_STOP events of the system v2 consist of (domains with own alarms, blamed domain,
duration), on the S5b test composites. Run after tools/WP6_S5b_test.py. Output: results/WP6/s5b_diag.json"""
import json
import pickle
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.config import results_dir  # noqa: E402
import WP6_S3_lib as L3  # noqa: E402
import WP6_S5b_lib as L  # noqa: E402

OUT = results_dir("WP6")


def main():
    fz = pickle.load(open(OUT / "s5b_frozen.pkl", "rb"))
    packs = L.assemble(L.load_unique("test"))
    res = {"note": "post-test diagnostic, no choice depends on it"}
    for fam in ("K", "C"):
        c = fz["composites_test"][fam]
        comps = [x for x in L3.build_set(fam, packs[fam], None, c["seed"], c["n_clean"], c["n_attack"]) if x["family"] == "none"]
        sysm = fz["systems"][fam]
        X = L.matrix(sysm.density, sysm.fusion, comps)
        s = sysm.fusion.scores(X)
        outs = L.evaluate(comps, X, s, sysm.fusion.threshold, sysm.entries, sysm.correlator, keep_events=True)
        ev = [e for r in outs for e in r["event_list"]]
        ss = [e for e in ev if e.response == "SAFE_STOP"]
        own_rate = {d: float(np.mean(np.concatenate([np.asarray(L.entry_part(x["parts"], d)["dom_alarm"], bool) for x in comps]))) for d in sysm.entries}
        res[fam] = {"clean_events": len(ev), "safe_stop_events": len(ss), "safe_stop_blamed": dict(Counter(e.blamed for e in ss)),
                    "safe_stop_domains": dict(Counter("+".join(e.domains) for e in ss)), "safe_stop_degraded": dict(Counter("+".join(e.degraded) for e in ss)),
                    "safe_stop_median_duration_s": float(np.median([e.end - e.start + 1 for e in ss])) if ss else None,
                    "event_blamed": dict(Counter(e.blamed for e in ev)), "clean_own_alarm_tick_rate": own_rate}
        print(fam, json.dumps(res[fam]))
    (OUT / "s5b_diag.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
