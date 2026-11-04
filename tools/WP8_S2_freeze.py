"""WP8 S2 freeze: the selected v3.1 system (results/WP8/S2/<tag>_eval.json "chosen") refitted on ALL V31_val clean data and saved as results/WP8/S2/frozen_system31/.

Entry ECDFs = the all-groups calibrators of tools/WP8_S2_sim.Sources (cal_full; V2X: density transform G(M)^k with G on all blocks' clean messages, then ECDF);
system threshold = tie-safe budget b on the fused clean-timeline ticks computed by the FROZEN object from the RAW tick values (SystemV31.run path).
Check (labelled in-sample, calibration only): the frozen object is run with SystemV31.run on every V31_val composite from raw tick values.
Inputs of the frozen system per tick (S7 runners): gps = frozen v3 GPS combined score / alarm; lidar = frozen_lidar31 combined score (tick max over the scans of the second),
own alarm = any scan alarm; can = IncrementalCan combined; network = F1 (Stream31Final, minute max of the host's flows, held one minute); v2x = EgoStream combined
(tick max, count = messages heard); cross = max edge score of the cross layer fitted on TRAIN (tools/WP8_S6_eval.fit_k / fit_c), own alarm = any edge >= tau, blame = A1.
Usage: python -u -W ignore tools/WP8_S2_freeze.py [--tag r1]
"""
import argparse
import hashlib
import json
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S2_sim as M

import numpy as np

OUT = M.OUT / "frozen_system31"


def raw_parts(c, names, lvar):
    P = c["parts"]
    out = {}
    for d in names:
        p = P[d]
        sx = "_L125" if (d == "lidar" and lvar == "L125") else ""
        out[d] = {"score": p["raw" + sx], "count": p.get("cnt", np.ones(len(p["raw"]))), "dom_alarm": p["own" + sx]}
        if d == "cross":
            out[d]["blame"] = p["blame_A1"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="r1")
    a = ap.parse_args()
    ev = json.loads((M.OUT / f"{a.tag}_eval.json").read_text())
    key = ev["chosen"]
    p = M.parts_of(key)
    S = M.Sources()
    systems, check = {}, {}
    for fam in ("K", "C"):
        F = M.Fam(S, fam)
        s = M.config_system(key, F.names)
        cf = S.cal_full[fam]
        for e in F.names:
            c = cf[e]
            if e == "lidar":
                c = c[p["L"]]
            if e == "network":
                c = c["F1"]
            s.cal[e] = c
        s.density["v2x"] = S.v2x_density_full
        s.fit_threshold([s.matrix(raw_parts(c, F.names, p["L"])) for c in F.clean])
        s.meta = {"step": "WP8 S2", "selection": a.tag, "key": key, "fit": "all V31_val clean groups (entry ECDFs) + all 19 clean timelines (threshold)",
                  "inputs": __doc__.split("Inputs of the frozen system per tick (S7 runners): ")[1].split("\nUsage")[0].replace("\n", " ")}
        systems[fam] = s
        # in-sample check through the raw-input path
        hours = sum(c["n"] for c in F.clean) / 3600.0
        al = ev_n = ss = 0
        for c in F.clean:
            o = s.run(raw_parts(c, F.names, p["L"]))
            al += int(o["alarm"].sum())
            ev_n += len(o["events"])
            ss += sum(e.response == "SAFE_STOP" for e in o["events"])
        det = []
        for i in F.single:
            c = F.att[i]
            o = s.run(raw_parts(c, F.names, p["L"]))
            hit = any((o["alarm"][e.start:e.end + 1] & c["label"][e.start:e.end + 1]).any() for e in o["events"])
            det.append(((c["scenario"], c["type"]), hit))
        per = {}
        for t, h in det:
            per.setdefault(t, []).append(h)
        check[fam] = {"label": "in-sample (calibration fitted on the same V31_val clean data); not a validation number", "threshold": s.threshold,
                      "fa_tick": al / sum(c["n"] for c in F.clean), "events_per_hour": ev_n / hours, "safe_stop_per_hour": ss / hours,
                      "det_single": float(np.mean([np.mean(v) for v in per.values()]))}
        M.log(fam, check[fam])
    OUT.mkdir(parents=True, exist_ok=True)
    pk = OUT / "system31.pkl"
    tmp = pk.with_suffix(".tmp")
    pickle.dump(systems, open(tmp, "wb"), protocol=4)
    tmp.replace(pk)
    sha = hashlib.sha256(pk.read_bytes()).hexdigest()
    meta = {"version": "v3.1 S2", "how_to_load": "fusion.system31.load_system31() -> {'K': SystemV31, 'C': SystemV31}; SystemV31.run(parts)", "key": key,
            "sha256_pkl": sha, "systems": {f: {k: v for k, v in s.to_dict().items() if k not in ("cal", "density")} for f, s in systems.items()}, "in_sample_check": check}
    (OUT / "system31.json").write_text(json.dumps(meta, indent=1, default=float))
    M.log("frozen", key, "sha256", sha)


if __name__ == "__main__":
    main()
