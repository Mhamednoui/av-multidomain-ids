"""WP7 S2 V2X pass: the frozen VeReMi physics stack (system/v2x_runner.py, WP7 S1) streamed message by message over every VeReMi TEST time block (class 12 dropped, an artefact never
claimed; messages in time order). The runner sees the whole block (all senders), so the frozen scores equal the batch scores of the WP6 packs. The ego views are then cut from the
Evidence log exactly as tools/WP6_S3_streams.py ego_series does (ego = a genuine sender with >= 60 s of track, heard set = messages of other senders within 300 m of the ego's
interpolated position during the ego's track), but for ALL candidate egos of every block (no random subset of 10): clean ego series (genuine messages only) and attack ego series (all heard
messages, labelled by attack class, tick label = the most frequent class of the tick).
Output: ../data_extra/cache_v3/WP7/S2_v2x.pkl = {"series": [...], "blocks": {...}, "latency": {...}}; check against s5_v2x.pkl in results/WP7/S2_check_v2x.json.
Usage: python -u -W ignore tools/WP7_S2_v2x.py [--smoke]   (--smoke: one VALIDATION block, 400 messages, plumbing only)
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP7_S2_lib as L

import numpy as np
import pandas as pd

from fusion import streams as ST
from system.v2x_runner import HELDOUT, V2XPhysicsDomain, V2XRunner
from tools.WP5_S2_l1 import aname
from v2x import splitting
import WP5_S5_dev as dev5

RADIUS_M, EGO_MIN_S = 300.0, 60.0
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def stream_block(runner, df, key):
    """Messages of one block through the runner, one at a time -> arrays: combined score / alarm, 12 layer scores / alarms (n, 12), per message."""
    recs = df.to_dict("records")
    runner.reset(key)
    ev = []
    for i, r in enumerate(recs):
        ev.extend(runner.push(r))
        if (i + 1) % 10000 == 0:
            log("  ", key, i + 1, "of", len(recs), "messages")
    ev.extend(runner.flush())
    n = len(recs)
    assert len(ev) == 13 * n, (len(ev), n)
    comb = ev[0::13]
    lay = [ev[1 + j::13] for j in range(12)]
    return {"score": np.array([e.score for e in comb], np.float32), "alarm": np.array([e.alarm for e in comb], bool),
            "layers": np.column_stack([[e.score for e in l] for l in lay]).astype(np.float32), "layer_alarm": np.column_stack([[e.alarm for e in l] for l in lay]),
            "names": [l[0].name for l in lay]}


def ego_views(blk, sc, grp, series):
    lab = blk["label"].to_numpy()
    snd = blk["sender"].to_numpy()
    t = blk["t"].to_numpy(float)
    x, y = blk["x"].to_numpy(float), blk["y"].to_numpy(float)
    bad = pd.Series(lab > 0).groupby(snd).any()
    dur = pd.Series(t).groupby(snd).agg(lambda v: v.max() - v.min())
    cand = sorted(s for s in dur.index if not bad[s] and dur[s] >= EGO_MIN_S)
    for e in cand:
        me = snd == e
        te, xe, ye = t[me], x[me], y[me]
        t0, t1 = te.min(), te.max()
        w = (t >= t0) & (t <= t1) & ~me
        ex, ey = np.interp(t[w], te, xe), np.interp(t[w], te, ye)
        near = np.hypot(x[w] - ex, y[w] - ey) <= RADIUS_M
        idx = np.flatnonzero(w)[near]
        n = int(np.ceil(t1 - t0)) + 1
        k = np.floor(t[idx] - t0).astype(np.int64)
        gen = lab[idx] == 0

        def pack(sel, kind, name, fam_arr, labels):
            ks, ii = k[sel], idx[sel]
            V = ST.tick_max(ks, sc["layers"][ii], n)
            S = ST.tick_max(ks, sc["score"][ii], n)
            s = L.make_series(grp, name, kind, "none" if kind == "clean" else ",".join(sorted(set(fam_arr[labels]))), S, V, ST.tick_any(ks, sc["alarm"][ii], n),
                              np.column_stack([ST.tick_any(ks, sc["layer_alarm"][ii, j], n) for j in range(V.shape[1])]), labels, np.arange(n) + 0.0, fam=fam_arr,
                              count=np.bincount(ks, minlength=n)[:n].astype(np.float32))
            return s

        z = np.zeros(n, bool)
        series.append(pack(gen, "clean", f"{grp}/ego{e}/clean", np.full(n, "", object), z))
        series[-1]["ego"] = str(e)
        if (~gen).any():
            fam = np.where(gen, "", np.array([aname(int(c)) if c > 0 else "" for c in lab[idx]], object))
            Lt = ST.tick_any(k, ~gen, n)
            Ft = ST.tick_family(k, fam, n)
            s = pack(np.ones(len(idx), bool), "attack", f"{grp}/ego{e}/attack", Ft, Lt)
            s["ego"] = str(e)
            series.append(s)


def main():
    smoke = "--smoke" in sys.argv
    v, sp = dev5.load_frames()
    part = "val" if smoke else "test"
    df = splitting.rows_of(v, sp[part])
    df = df[df["label"] != 12].sort_values("t", kind="stable").reset_index(drop=True)
    dom = V2XPhysicsDomain.load(L.OUT / "frozen_v2x")
    runner = V2XRunner(dom, per_layer=True)
    series, blocks, lat = [], {}, {"ns": [], "emit": [], "size": []}
    groups = sorted(df["group"].unique(), key=str)
    tag = ""
    if "--blocks" in sys.argv:
        want = sys.argv[sys.argv.index("--blocks") + 1].split(",")
        groups = [g for g in groups if str(g) in want]
        tag = "_" + sys.argv[sys.argv.index("--tag") + 1]
    if smoke:
        groups = groups[:1]
    for g in groups:
        blk = df[df["group"] == g].reset_index(drop=True)
        if smoke:
            blk = blk.iloc[:400].reset_index(drop=True)
        sc = stream_block(runner, blk, f"block{g}")
        blocks[str(g)] = {"n": len(blk), "tie_events": runner.tie_events, "out_of_order": runner.out_of_order, "t0": float(blk["t"].min()), "t1": float(blk["t"].max()),
                          "genuine_msg_fa": float(sc["alarm"][blk["label"].to_numpy() == 0].mean()) if (blk["label"] == 0).any() else None,
                          "messages_by_class": {int(c): int(n) for c, n in blk["label"].value_counts().items()}}
        lat["ns"] += list(runner.latency.ns)
        lat["emit"] += list(runner.latency.emit)
        lat["size"] += list(runner.latency.size)
        runner.latency.clear()
        ego_views(blk, sc, str(g), series)
        blocks[str(g)]["egos"] = sum(1 for s in series if s["name"].startswith(f"{g}/") and s["kind"] == "clean")
        log("block", g, blocks[str(g)])
    out = {"series": series, "blocks": blocks, "latency": lat, "layer_names": sc["names"], "part": part}
    if not smoke:
        L.save_pickle(out, f"S2_v2x{tag}.pkl")
        pk = pd.read_pickle(L.WP6C / "s5_v2x.pkl")["test"]
        clean_pack = np.concatenate([s["score"] for s in pk["series"] if s["kind"] == "clean"])
        clean_s2 = np.concatenate([s["score"] for s in series if s["kind"] == "clean"])
        res = {"series": len(series), "clean_series": int(sum(s["kind"] == "clean" for s in series)), "attack_series": int(sum(s["kind"] == "attack" for s in series)),
               "pack_clean_series": int(sum(s["kind"] == "clean" for s in pk["series"])), "pack_attack_series": int(sum(s["kind"] == "attack" for s in pk["series"])),
               "dom_thr_stream": float(dom.comb_thr), "dom_thr_pack": float(pk["dom_thr"]), "clean_tick_alarm_rate_stream": float(np.mean(np.concatenate([s["dom_alarm"] for s in series if s["kind"] == "clean"]))),
               "clean_tick_alarm_rate_pack": float(np.mean(np.concatenate([np.asarray(s["score"]) >= pk["dom_thr"] for s in pk["series"] if s["kind"] == "clean"]))),
               "blocks": blocks}
        (L.OUT / f"S2_check_v2x{tag}.json").write_text(json.dumps(res, indent=1, default=float))
    log("done", len(series))


if __name__ == "__main__":
    main()
