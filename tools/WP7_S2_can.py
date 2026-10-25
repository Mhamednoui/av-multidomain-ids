"""WP7 S2 CAN pass: the frozen ROAD CAN domain (system/can_runner.py, results/WP2/s7_domain) streamed FRAME BY FRAME over the 15 ROAD TEST captures (4 ambient clean captures, 11 attack
captures incl. masquerade variants). One 1 s window Evidence (combined + L1 / L3c / L3d) is emitted when the next second starts; the last partial window is dropped (the WP2 tables drop it:
`ok` mask). The window label (an injected frame inside the window) comes from the WP2 S7 window tables (ground truth only, never an input of the detector).
Output: ../data_extra/cache_v3/WP7/S2_can.pkl = {"series": [...], "latency": {...}}; check against s3_can.pkl (batch pack) in results/WP7/S2_check_can.json.
Usage: python -u -W ignore tools/WP7_S2_can.py [--smoke] [--only name ...]
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP7_S2_lib as L

import numpy as np
import pandas as pd

from common.config import DATA_EXTRA
from fusion import streams as ST
from system.can_runner import CANRunner

FROZEN = L.ROOT / "results" / "WP2" / "s7_domain"
S2 = DATA_EXTRA / "WP2_S2_cache" / "road"
S4 = DATA_EXTRA / "WP2_S4_cache" / "road"
TAB = DATA_EXTRA / "WP2_S7_cache" / "tables"
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def can_family(name):
    f = re.sub(r"_attack(_\d)?", "", name.replace("_masquerade", ""))
    return f + ("_masquerade" if name.endswith("_masquerade") else "")


def load(name):
    z = np.load(S2 / (name + ".npz"))
    B = np.maximum(np.load(S4 / (name + ".npy")), 0).astype(np.uint8)
    return z["t"], z["id"].astype(np.int64), z["dlc"].astype(np.int64), B


def run_capture(run, name, folder, max_frames=None):
    t, ids, dlc, B = load(name)
    n = len(t) if max_frames is None else min(max_frames, len(t))
    run.reset(name)
    run.latency.clear()
    ev = []
    t_push = []
    for i in range(n):
        out = run.push((t[i], ids[i], dlc[i], B[i]))
        if out:
            ev.extend(out)
            t_push.extend([float(t[i])] * len(out))          # stream time at which the window Evidence appeared
    out = run.flush()
    ev.extend(out)
    t_push.extend([float(t[n - 1])] * len(out))
    tab = dict(np.load(TAB / folder / (name + ".npz")))
    layers = run.dom.layers
    k = 1 + len(layers)
    comb, lay = ev[0::k], [ev[1 + j::k] for j in range(len(layers))]
    sec = np.array([int(e.sample_id.split("/")[-1]) for e in comb])
    avail_t = np.array(t_push[0::k])
    row = {int(s): j for j, s in enumerate(tab["sec"])}
    keep = np.array([int(s) in row and bool(tab["ok"][row[int(s)]]) for s in sec])
    s0 = int(sec[keep].min())
    tick = sec[keep] - s0
    nT = int(tick.max()) + 1
    score = np.zeros(nT, np.float32)
    layers_a = np.zeros((nT, len(layers)), np.float32)
    alarm = np.zeros(nT, bool)
    lalarm = np.zeros((nT, len(layers)), bool)
    label = np.zeros(nT, bool)
    avail = np.arange(nT) + 1.0
    t_base = float(t[0])
    for j in np.flatnonzero(keep):
        kk = int(sec[j] - s0)
        score[kk], alarm[kk] = comb[j].score, comb[j].alarm
        layers_a[kk] = [lay[m][j].score for m in range(len(layers))]
        lalarm[kk] = [lay[m][j].alarm for m in range(len(layers))]
        label[kk] = tab["y"][row[int(sec[j])]] > 0
        avail[kk] = max(avail_t[j] - t_base, kk + 1.0)           # the window is visible when the first frame of the next second arrives
    fam = can_family(name)
    s = L.make_series(name, name, "attack" if label.any() else "clean", fam if label.any() else "none", score, layers_a, alarm, lalarm, label, np.arange(nT) + 0.0, avail=avail)
    s["layer_names"] = list(layers)
    s["frames"] = int(n)
    s["sec0"] = s0
    lat = {"ns": list(run.latency.ns), "emit": list(run.latency.emit), "size": list(run.latency.size)}
    return s, lat


def main():
    smoke = "--smoke" in sys.argv
    pack = pd.read_pickle(L.WP6C / "s3_can.pkl")["test"]
    names = [(s["name"], "test") for s in pack["series"]]
    if "--only" in sys.argv:
        keep = set(a for a in sys.argv[sys.argv.index("--only") + 1:] if not a.startswith("--") and a != sys.argv[sys.argv.index("--tag") + 1 if "--tag" in sys.argv else 0])
        names = [x for x in names if x[0] in keep]
    if smoke:
        names = [("fuzzing_attack_3", "test")]
    run = CANRunner(FROZEN, per_layer=True, explain=True)
    res = {"series": [], "latency": {}}
    chk = {}
    pk = {s["name"]: s for s in pack["series"]}
    for name, folder in names:
        s, lat = run_capture(run, name, folder)
        res["series"].append(s)
        res["latency"][name] = lat
        p = pk[name]
        m = min(len(p["score"]), len(s["score"]))
        chk[name] = {"windows": int(len(s["score"])), "pack_windows": int(len(p["score"])), "max_score_diff": float(np.abs(np.asarray(p["score"])[:m] - s["score"][:m]).max()),
                     "alarm_mismatch": int(((np.asarray(p["score"])[:m] >= pack["dom_thr"]) != s["dom_alarm"][:m]).sum()), "label_ticks": int(s["label"].sum()),
                     "pack_label_ticks": int(np.asarray(p["label"]).sum()), "seconds": float(len(s["score"]))}
        log(name, chk[name])
    if not smoke:
        tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else ""
        L.save_pickle(res, f"S2_can{tag}.pkl")
        (L.OUT / f"S2_check_can{tag}.json").write_text(json.dumps(chk, indent=1))
    log("done")


if __name__ == "__main__":
    main()
