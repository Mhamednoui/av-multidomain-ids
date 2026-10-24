"""WP7 S1 CAN: streaming (system/can_runner.py, one frame at a time) vs the frozen BATCH CanDomain.score_capture on VALIDATION captures of ROAD
(attack instance 2 + ambient val captures of results/WP2/splits_road.json). A1 exactness of combined + per-layer Evidence and of the wheel-speed MotionEstimates,
A2 causality by truncation (batch and stream), A3 reset, A4 latency (3 repetitions; per frame and per emitted window). No test capture is read.
Run from codes_v3/: python -I -u -W ignore tools/WP7_S1_can.py     Output: results/WP7/S1_can.json
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP7_S1_lib as L

import numpy as np

from common.config import DATA_EXTRA
from system.can_runner import CANRunner
from system.runner import compare_sequences

FROZEN = L.ROOT / "results" / "WP2" / "s7_domain"
S2 = DATA_EXTRA / "WP2_S2_cache" / "road"
S4 = DATA_EXTRA / "WP2_S4_cache" / "road"
A1_CAPTURES = ["correlated_signal_attack_2", "correlated_signal_attack_2_masquerade", "reverse_light_off_attack_2", "reverse_light_on_attack_2",
               "max_speedometer_attack_2", "ambient_dyno_drive_winter"]
LAT_CAPTURES = ["correlated_signal_attack_2", "reverse_light_off_attack_2"]
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def load(name):
    z = np.load(S2 / (name + ".npz"))
    B = np.maximum(np.load(S4 / (name + ".npy")), 0).astype(np.uint8)
    return z["t"], z["id"].astype(np.int64), z["dlc"].astype(np.int64), B, z["label"]


def frames(cap, i0=0, i1=None):
    t, ids, dlc, B, _ = cap
    i1 = len(t) if i1 is None else i1
    return [(t[i], ids[i], dlc[i], B[i]) for i in range(i0, i1)]


merge = L.merge


def split_out(out, layers):
    n = len(layers) + 1
    return out[0::n], {l: out[1 + j::n] for j, l in enumerate(layers)}


def motion_equal(a, b, tol=1e-9):
    if len(a) != len(b):
        return False
    return all(abs(x.t - y.t) < 1e-9 and abs(x.speed - y.speed) <= tol and abs(x.sigma - y.sigma) <= tol and x.source == y.source for x, y in zip(a, b))


def main():
    run = CANRunner(FROZEN)
    dom = run.dom
    caps = {n: load(n) for n in A1_CAPTURES}
    log("loaded", {n: len(c[0]) for n, c in caps.items()})
    comb_c, lay_c, mot_ok, batch = [], [], [], {}
    info = []
    for n, cap in caps.items():
        t, ids, dlc, B, lab = cap
        comb, per = dom.score_capture(t, ids, dlc, B, name=n)
        batch[n] = (comb, per)
        me_b = dom.motion_estimates(t, ids, dlc, B)
        run.reset(n)
        out = run.run(frames(cap), key=n)
        s_comb, s_lay = split_out(out, dom.layers)
        mot = run.pop_motion()
        comb_c.append(compare_sequences(s_comb, comb))
        lay_c.append(merge([compare_sequences(s_lay[l], per[l]) for l in dom.layers]))
        mot_ok.append(motion_equal(mot, me_b))
        info.append({"capture": n, "frames": int(len(t)), "seconds": float(t[-1] - t[0]), "windows": len(comb), "alarms": int(sum(e.alarm for e in comb)),
                     "identical_combined": comb_c[-1]["identical"], "identical_layers": lay_c[-1]["all_identical"], "motion_identical": mot_ok[-1], "n_motion": len(me_b)})
        log("A1", n, info[-1])
    a1 = {"combined": merge(comb_c), "per_layer": merge(lay_c), "motion_estimates_identical_all": bool(all(mot_ok)), "captures": info}
    # ---- A2 truncation ----
    a2 = {"batch_prefix_equals_batch_full_completed_windows": [], "stream_prefix_equals_stream_full": []}
    for n in ["correlated_signal_attack_2", "reverse_light_off_attack_2", "max_speedometer_attack_2"]:
        cap = caps[n]
        t, ids, dlc, B, _ = cap
        comb_full = batch[n][0]
        full_stream = None
        for frac in (0.3, 0.6, 0.9):
            k = int(frac * len(t))
            combk, _ = dom.score_capture(t[:k], ids[:k], dlc[:k], B[:k], name=n)
            m = len(combk) - 1                                  # the last window of a prefix is partial
            a2["batch_prefix_equals_batch_full_completed_windows"].append({"capture": n, "frames": k, "windows_compared": m, **compare_sequences(combk[:m], comb_full[:m])})
            r2 = CANRunner(FROZEN, per_layer=False)
            outk = r2.run(frames(cap, 0, k), key=n, flush=False)       # truncated stream, no flush: only completed windows
            if full_stream is None:
                full_stream = CANRunner(FROZEN, per_layer=False).run(frames(cap), key=n)
            a2["stream_prefix_equals_stream_full"].append({"capture": n, "frames": k, "windows_emitted": len(outk), **compare_sequences(outk, full_stream[:len(outk)])})
    allc = a2["batch_prefix_equals_batch_full_completed_windows"] + a2["stream_prefix_equals_stream_full"]
    a2["all_identical"] = all(c["identical"] for c in allc)
    a2["n_checks"] = len(allc)
    log("A2", a2["all_identical"])
    # ---- A3 reset ----
    r1 = CANRunner(FROZEN)
    r1.run(frames(caps["reverse_light_off_attack_2"]), key="A")
    after = r1.run(frames(caps["ambient_dyno_drive_winter"], 0, 40000), key="B")
    fresh = CANRunner(FROZEN).run(frames(caps["ambient_dyno_drive_winter"], 0, 40000), key="B")
    a3 = compare_sequences(after, fresh)
    log("A3", a3["identical"])
    # ---- A4 latency ----
    ns, em, sz = [], [], []
    for rep in range(3):
        rr = CANRunner(FROZEN)
        for n in LAT_CAPTURES:
            rr.run(frames(caps[n]), key=n)
        ns.append(list(rr.latency.ns)), em.append(list(rr.latency.emit)), sz.append(list(rr.latency.size))
        log("latency rep", rep, f"windows median {np.median(np.asarray(ns[-1])[np.asarray(em[-1]) > 0]) / 1e6:.0f} ms")
    lat = {"per_frame_all_calls": L.pooled(ns, em), "per_emitted_window": L.pooled(ns, em, only_emitting=True),
           "window_by_context_frames": L.growth(sz, ns, em, only_emitting=True), "captures": LAT_CAPTURES,
           "v2_reference_ms_per_frame": 0.05, "window_period_s": 1.0}
    lat["p99_window_below_period"] = bool(lat["per_emitted_window"]["pooled"]["p99_ms"] < 1000.0)
    lat["amortised_ms_per_frame"] = float(np.sum(np.concatenate([np.asarray(x, float) for x in ns])) / 1e6 / sum(len(x) for x in ns))
    lat["note"] = ("a frame that does not complete a window only appends it; a window is scored by a prefix re-score of the frozen batch code (L1 rules + L3c + L3d + culprit signal), "
                   "cost grows with the capture so far; the amortised number is total time / total frames")
    res = {"data": {"split": "ROAD validation captures (attack instance 2, ambient val)", "captures": A1_CAPTURES}, "A1_exactness": a1, "A2_causality_truncation": a2,
           "A3_reset": a3, "A4_latency": lat, "machine": L.machine(), "seconds": time.time() - T0}
    L.dump(res, "S1_can.json")
    log("done")


if __name__ == "__main__":
    main()
