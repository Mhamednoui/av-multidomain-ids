"""WP8 S5 V2X: single-ego stream (v2x/ego_stream.py) vs the batch code on that ego's messages, equality + compute per stream second (V31_val only).

Ego = one receiver: a V2AIX Mobile recording of the V31_val 'val' list with an ego pose (rx_x finite for all messages), and ego views cut from VeReMi VALIDATION blocks
(groups 1, 3, 4, 6 of splits_veremi 'val', held-out types 6 / 12 / 17 removed; ego = genuine sender with >= 60 s of track, heard set = messages of other senders within 300 m
of its interpolated position during its track, as tools/WP7_S2_v2x.py; 6 egos per block, deterministic: every k-th candidate). Batch reference: v2x/v2aix_eval.raws (V2AIX;
per-track checks on t, overlap / birth on recv_s) and V2XPhysicsDomain.raws (VeReMi), on the table of that ego. Evidence: V2XPhysicsDomain.evidence (frozen VeReMi calibration,
read-only) on the same raw scores -> combined score / alarm / per-check scores must be identical.
Rule S5 V1: compute <= 0.5 s per stream second for >= 95% of egos, p99 per message <= 100 ms, 0 mismatches.
Outputs: results/WP8/S5/parts/v2x_<source>_<id>.json (resumable), scores in results/WP8/scores/S5/v2x_<source>.npz (per-ego aggregates only, NO per-message V2AIX data),
results/WP8/S5/v2x_summary.json. Usage: python -u -W ignore tools/WP8_S5_v2x.py [--max-v2aix N]
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import numpy as np
import pandas as pd

from system.v2x_runner import HELDOUT, LAYER_NAMES, V2XPhysicsDomain
from v2x import splitting, v2aix, v2aix_eval
from v2x.ego_stream import CHECKS, EgoStream

OUT = ROOT / "results" / "WP8" / "S5"
SC = ROOT / "results" / "WP8" / "scores" / "S5"
FROZEN = ROOT / "results" / "WP7" / "frozen_v2x"
T0 = time.time()
RADIUS_M, EGO_MIN_S = 300.0, 60.0


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def run_ego(dom, df, batch_raws, use_recv, clock):
    """df in stream (reception) order; batch_raws = dict check -> array aligned with df rows."""
    es = EgoStream(dom.tracker, use_recv=use_recv)
    recs = df.to_dict("records")
    n = len(recs)
    raw = {c: np.empty(n, np.float32) for c in CHECKS}
    wall = np.empty(n)
    ev_s = []
    for i, r in enumerate(recs):
        s = time.perf_counter()
        o = es.push(r)
        wall[i] = time.perf_counter() - s
        for c in CHECKS:
            raw[c][i] = o[c]
    # evidence on the stream raws vs on the batch raws (frozen calibration), timed separately (cheap, vectorised per message below)
    ev_wall = np.empty(n)
    cs, ca, bs, ba, lay_mis = [], [], [], [], 0
    for i in range(n):
        one = df.iloc[[i]].reset_index(drop=True)
        s = time.perf_counter()
        e1 = dom.evidence(one, {c: raw[c][i:i + 1] for c in LAYER_NAMES}, [0])[0]
        ev_wall[i] = time.perf_counter() - s
        e2 = dom.evidence(one, {c: batch_raws[c][i:i + 1] for c in LAYER_NAMES}, [0])[0]
        cs.append(e1.score)
        bs.append(e2.score)
        ca.append(e1.alarm)
        ba.append(e2.alarm)
        lay_mis += int(e1.details["layer_scores"] != e2.details["layer_scores"]) + int(e1.reason != e2.reason)
    bad_rows = np.flatnonzero(np.any([raw[c] != np.asarray(batch_raws[c], np.float32) for c in LAYER_NAMES], axis=0))
    trk = df["track"].to_numpy()
    expl = set()                                  # a message older than the previous one of its track: batch sorts by t (needs the future); explained rows = it and the message of that track received just before it
    for i, tr in es.reordered_rows:
        expl.add(i)
        before = np.flatnonzero(trk[:i] == tr)          # in t order the late message sits before the message received just ahead of it
        if len(before):
            expl.add(int(before[-1]))
    unexplained = int(sum(1 for i in bad_rows if i not in expl))
    d_raw = {c: float(np.max(np.abs(raw[c].astype(np.float64) - np.asarray(batch_raws[c], np.float64)))) for c in LAYER_NAMES}
    mism = {c: int((raw[c] != np.asarray(batch_raws[c], np.float32)).sum()) for c in LAYER_NAMES}
    total = wall + ev_wall
    span = float(clock.max() - clock.min())
    return {"messages": n, "stream_s": span, "compute_s": float(total.sum()), "compute_per_stream_s": float(total.sum() / max(span, 1e-9)),
            "msg_ms": {"median": float(np.median(total) * 1e3), "p99": float(np.percentile(total, 99) * 1e3), "max": float(total.max() * 1e3)},
            "push_ms_p99": float(np.percentile(wall, 99) * 1e3), "raw_mismatch": mism, "raw_mismatch_total": int(sum(mism.values())), "mismatch_rows": int(len(bad_rows)), "mismatch_rows_unexplained": unexplained, "raw_max_abs_diff": d_raw,
            "evidence_score_max_abs_diff": float(np.max(np.abs(np.array(cs) - np.array(bs)))), "evidence_alarm_mismatch": int((np.array(ca) != np.array(ba)).sum()),
            "evidence_layer_or_reason_mismatch": int(lay_mis), "ties": es.ties, "reordered": es.reordered, "ctx_rows_median": float(np.median(es.n_ctx)),
            "alarms": int(np.sum(ca))}, wall + ev_wall


def v2aix_egos(dom, max_n):
    lock = json.load(open(ROOT / "locks" / "V31_val.json"))["domains"]["v2x"]["v2aix"]["val"]
    mobile = [r for r in lock if r.startswith("Mobile/")]
    paths = {v2aix.recording_id(p): p for p in v2aix.list_recordings()}
    cnt = 0
    for rec in mobile:
        if max_n and cnt >= max_n:
            break
        if rec not in paths:
            continue
        df = v2aix.load_recording(paths[rec])
        if not len(df) or not np.isfinite(df["rx_x"].to_numpy(float)).all():
            continue
        cnt += 1
        yield rec, df


def veremi_egos(per_block=6):
    import WP5_S5_dev as dev5
    v, sp = dev5.load_frames()
    va = splitting.rows_of(v, sp["val"])
    va = va[~va["label"].isin(HELDOUT)]
    for g in ["1", "3", "4", "6"]:
        blk = va[va["group"] == g].sort_values("t", kind="stable").reset_index(drop=True)
        lab, snd, t = blk["label"].to_numpy(), blk["sender"].to_numpy(), blk["t"].to_numpy(float)
        x, y = blk["x"].to_numpy(float), blk["y"].to_numpy(float)
        bad = pd.Series(lab > 0).groupby(snd).any()
        dur = pd.Series(t).groupby(snd).agg(lambda s: s.max() - s.min())
        cand = sorted(s for s in dur.index if not bad[s] and dur[s] >= EGO_MIN_S)
        pick = cand[:: max(len(cand) // per_block, 1)][:per_block]
        for e in pick:
            me = snd == e
            te, xe, ye = t[me], x[me], y[me]
            w = (t >= te.min()) & (t <= te.max()) & ~me
            ex, ey = np.interp(t[w], te, xe), np.interp(t[w], te, ye)
            near = np.hypot(x[w] - ex, y[w] - ey) <= RADIUS_M
            sub = blk.iloc[np.flatnonzero(w)[near]].copy().reset_index(drop=True)
            if len(sub) < 50:
                continue
            sub["rx_id"] = "ego"
            yield f"veremi/{g}/{e}", sub


def main():
    max_n = int(sys.argv[sys.argv.index("--max-v2aix") + 1]) if "--max-v2aix" in sys.argv else 0
    dom = V2XPhysicsDomain.load(FROZEN)
    (OUT / "parts").mkdir(parents=True, exist_ok=True)
    SC.mkdir(parents=True, exist_ok=True)
    for src, gen in (("veremi", veremi_egos()), ("v2aix", v2aix_egos(dom, max_n))):
        for rec, df in gen:
            part = OUT / "parts" / ("v2x_" + rec.replace("/", "__") + ".json")
            if part.exists():
                continue
            if src == "v2aix":
                order = np.lexsort((np.arange(len(df)), df["recv_s"].to_numpy(float)))
                braw = v2aix_eval.raws(dom.tracker, df)
                sdf = df.iloc[order].reset_index(drop=True)
                braw = {c: np.asarray(braw[c])[order] for c in LAYER_NAMES}
                clock = sdf["recv_s"].to_numpy(float)
                res, _ = run_ego(dom, sdf, braw, True, clock)
            else:
                sdf = df.sort_values("t", kind="stable").reset_index(drop=True)
                braw = dom.raws(sdf)
                res, _ = run_ego(dom, sdf, braw, False, sdf["t"].to_numpy(float))
            res.update({"source": src, "ego": rec})
            tmp = part.with_suffix(".tmp")
            tmp.write_text(json.dumps(res, indent=1))
            tmp.replace(part)
            log(rec, {k: res[k] for k in ("messages", "stream_s", "compute_per_stream_s", "msg_ms", "raw_mismatch_total", "evidence_alarm_mismatch", "ties", "reordered")})
    allr = [json.load(open(p)) for p in sorted((OUT / "parts").glob("v2x_*.json"))]
    (OUT / "v2x_summary.json").write_text(json.dumps(allr, indent=1))
    for src in ("veremi", "v2aix"):
        r = [a for a in allr if a["source"] == src]
        if r:
            np.savez(SC / f"v2x_{src}_ego_aggregates.npz", ego=np.array([a["ego"] for a in r]), messages=np.array([a["messages"] for a in r]),
                     stream_s=np.array([a["stream_s"] for a in r]), compute_per_stream_s=np.array([a["compute_per_stream_s"] for a in r]),
                     msg_p99_ms=np.array([a["msg_ms"]["p99"] for a in r]), raw_mismatch=np.array([a["raw_mismatch_total"] for a in r]))


if __name__ == "__main__":
    main()
