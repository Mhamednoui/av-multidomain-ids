"""WP2 S4: L2b signal physics on ROAD. Stages (resumable, checkpoints in ../data_extra/WP2_S4_cache/):
  stats    capture statistics of the 8 clean ambient captures (train + val, incl. exercise_all_bits) + code maps
  fold     for each held-out clean capture (7) and each variant: fit on the other 7 ambient, record per-check violation counts
  final    fit on all 8 ambient (per variant)
  weights  per check surprise weight from the pooled LOCO violation counts
  score    weighted frame scores: loco (held-out captures), attack (train/val attack captures), test (ONE run, chosen variant)
Scores are stored as sparse per-type raw frame arrays (index, value) per capture and variant.
Usage: python -u -W ignore tools/WP2_S4_run.py stats|fold [captures]|final|weights|score loco|attack|test <variants>
Protocol and acceptance rule: notes/WP2_can.md "S4 start".
"""
import pickle
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from can import l2b_signals as Z
from can import signals as S
from common.config import DATA_EXTRA, RESULTS

CACHE = DATA_EXTRA / "WP2_S4_cache"
OUT = RESULTS / "WP2"
AMB = ["ambient_dyno_drive_basic_long", "ambient_dyno_drive_extended_long", "ambient_dyno_drive_radio_infotainment",
       "ambient_dyno_exercise_all_bits", "ambient_dyno_idle_radio_infotainment", "ambient_highway_street_driving_long",
       "ambient_dyno_drive_basic_short", "ambient_dyno_drive_winter"]
LOCO = [n for n in AMB if n != "ambient_dyno_exercise_all_bits"]
Z.MUTE_T0 = 3.0                    # in-situ baseline: checks that violate in the first 3 s of a capture are muted (design change 2)
import os
SUF = os.environ.get("S4_SUFFIX", "_m")
if os.environ.get("S4_JOINT_ONLY"):          # revision R1 (validation only): joint checks that involve the reverse-light bit
    Z.JOINT_ONLY = {(int(x.split(".")[0], 16), int(x.split(".")[1])) for x in os.environ["S4_JOINT_ONLY"].split(",")}
H = [(0.98, 1), (0.98, 10), (0.995, 1), (0.995, 10)]
FAMS = ["correlated_signal", "max_speedometer", "reverse_light_off", "reverse_light_on", "fuzzing"]


def attack_names(inst):
    out = []
    for f in FAMS:
        out.append(f"{f}_attack_{inst}")
        if f != "fuzzing":
            out.append(f"{f}_attack_{inst}_masquerade")
    return out


def test_names():
    out = [f"{f}_attack_3" for f in FAMS] + [f"{f}_attack_3_masquerade" for f in FAMS if f != "fuzzing"]
    out += ["max_engine_coolant_temp_attack", "max_engine_coolant_temp_attack_masquerade"]
    out += ["ambient_dyno_drive_benign_anomaly", "ambient_dyno_drive_extended_short", "ambient_dyno_reverse",
            "ambient_highway_street_driving_diagnostics"]
    return out


def load_capture(name):
    raw = np.load(DATA_EXTRA / "WP2_S2_cache" / "road" / (name + ".npz"))
    B = np.load(CACHE / "road" / (name + ".npy"))
    tm = np.maximum.accumulate(raw["t"])
    return tm, raw["id"], raw["label"], S.decode_all(raw["id"], B, DBC)


DBC = S.parse_dbc()
CAT = Z.Catalog(DBC)


def sparse_save(path, raws):
    d = {}
    for t, a in raws.items():
        idx = np.flatnonzero(a)
        d[t + "_i"], d[t + "_v"] = idx.astype(np.int32), a[idx]
    d["n"] = len(next(iter(raws.values())))
    np.savez(path, **d)


def sparse_load(path):
    z = np.load(path)
    n = int(z["n"])
    out = {}
    for t in Z.TYPES:
        a = np.zeros(n, np.float32)
        a[z[t + "_i"]] = z[t + "_v"]
        out[t] = a
    return out


def get_stats():
    st = {n: pickle.load(open(CACHE / "stats" / (n + ".pkl"), "rb")) for n in AMB}
    maps = pickle.load(open(CACHE / "stats" / "maps.pkl", "rb"))
    codes = {n: Z.grid_codes(st[n], maps) for n in AMB}
    return st, maps, codes


def stage_stats():
    (CACHE / "stats").mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for n in AMB:
        p = CACHE / "stats" / (n + ".pkl")
        if p.exists():
            continue
        tm, ids, _, dec = load_capture(n)
        st = Z.capture_stats(n, tm, dec, CAT)
        pickle.dump(st, open(p, "wb"))
        print(f"stats {n} ({time.time() - t0:.0f}s)", flush=True)
    st = {n: pickle.load(open(CACHE / "stats" / (n + ".pkl"), "rb")) for n in AMB}
    pickle.dump(Z.build_codemaps(list(st.values()), CAT), open(CACHE / "stats" / "maps.pkl", "wb"))
    print("maps done", flush=True)


def fit(st, codes, maps, names, h):
    return Z.fit_model([st[n] for n in names], [codes[n] for n in names], CAT, maps, *H[h])


def mdir(sub):
    d = CACHE / sub
    d.mkdir(parents=True, exist_ok=True)
    return d


def stage_fold():
    """Fit each LOCO fold model (pickled), record how often every check fires on the held-out clean capture."""
    st, maps, codes = get_stats()
    caps = sys.argv[2:] or LOCO
    t0 = time.time()
    for c in caps:
        tm = dec = None
        for h in range(len(H)):
            pm, pt = mdir("models") / f"h{h}__{c}.pkl", mdir("trace_m") / f"h{h}__{c}.pkl"
            if pt.exists():
                continue
            if tm is None:
                tm, ids, _, dec = load_capture(c)
            if pm.exists():
                M = pickle.load(open(pm, "rb"))
            else:
                M = fit(st, codes, maps, [n for n in AMB if n != c], h)
                pickle.dump(M, open(pm, "wb"))
            Z.TRACE = {}
            Z.WEIGHTS = None
            Z.score_frames(M, tm, dec, len(tm))
            pickle.dump(Z.TRACE, open(pt, "wb"))
            Z.TRACE = None
            print(f"fold h{h} {c} lin={len(M.lin)} joint={len(M.joint)} ({time.time() - t0:.0f}s)", flush=True)


def stage_final():
    st, maps, codes = get_stats()
    for h in range(len(H)):
        p = mdir("models") / f"h{h}__final.pkl"
        if not p.exists():
            pickle.dump(fit(st, codes, maps, AMB, h), open(p, "wb"))
            print("final", h, flush=True)


def stage_weights():
    import json
    summ = {}
    for h in range(len(H)):
        tot = {}
        for c in LOCO:
            for tag, (n, v) in pickle.load(open(CACHE / "trace_m" / f"h{h}__{c}.pkl", "rb")).items():
                a = tot.setdefault(tag, [0, 0])
                a[0] += n
                a[1] += v
        W = {tag: Z.check_weight(v, n) for tag, (n, v) in tot.items()}
        pickle.dump(W, open(CACHE / f"weights_m_h{h}.pkl", "wb"))
        w = np.array(list(W.values()))
        summ[h] = {"checks": len(W), "weight_quantiles": np.quantile(w, [0, 0.1, 0.5, 0.9, 1]).tolist(),
                   "never_fire": int(sum(1 for n, v in tot.values() if v == 0))}
    json.dump(summ, open(OUT / "s4_weights_summary.json", "w"), indent=1)
    print(summ)


def stage_score():
    """argv: score loco|attack|test <variants comma list>; weighted frame scores, sparse."""
    group = sys.argv[2]
    hs = [int(x) for x in sys.argv[3].split(",")]
    st = None
    t0 = time.time()
    names = {"loco": LOCO, "attack": attack_names(1) + attack_names(2), "test": test_names()}[group]
    d = mdir(group + SUF)
    for c in names:
        todo = [h for h in hs if not (d / f"h{h}__{c}.npz").exists()]
        if not todo:
            continue
        tm, ids, _, dec = load_capture(c)
        for h in todo:
            M = pickle.load(open(CACHE / "models" / f"h{h}__{c if group == 'loco' else 'final'}.pkl", "rb"))
            Z.WEIGHTS = pickle.load(open(CACHE / f"weights_m_h{h}.pkl", "rb"))
            sparse_save(d / f"h{h}__{c}.npz", Z.score_frames(M, tm, dec, len(tm)))
        Z.WEIGHTS = None
        print(f"score {group} {c} ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    {"stats": stage_stats, "fold": stage_fold, "final": stage_final, "weights": stage_weights, "score": stage_score}[sys.argv[1]]()
