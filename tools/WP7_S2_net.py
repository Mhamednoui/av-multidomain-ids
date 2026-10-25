"""WP7 S2 network pass: the frozen network domain (system/net_runner.py, stack H, results/WP4/s7_domain) streamed FLOW BY FLOW over the D10 (CICIDS2017 mirror) TEST split, one
(day, period) block at a time (31 blocks, 585,951 flows of all hosts: the window layers need the traffic of the whole network). A flow's Evidence is final only when its 5-minute bin
has closed (S1b): the pass records the stream time at which each flow's Evidence appeared (the ts of the flow whose arrival closed the bin; the block end at flush).
View of the vehicle host 192.168.10.50 (dense id 49, the host the D10 attacks target): the M2 tick model, kept so the frozen network ECDF / system v2 stay valid: tick value = per-layer
maximum over the host's flows of the last CLOSED minute, held for the next 60 s; labels shifted with it. Added here: avail[tick] = the stream time (s from the block start) at which that
minute's Evidence was final, i.e. the time the system could first see the tick; onset_flow = first attack flow of a held attack minute (flow time) for the true delay.
Block clock: second 0 = the start of the first minute of the host's flows in the block.
Output: ../data_extra/cache_v3/WP7/S2_net<tag>.pkl; check against s5_network.pkl (the batch pack) in results/WP7/S2_check_net<tag>.json.
Usage: python -u -W ignore tools/WP7_S2_net.py [--part i n] [--smoke]  (--smoke: validation block, first 3000 flows)
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
from network.domain import RAW_COLUMNS, NetworkDomain
from system.net_runner import NetworkRunner
from tools.WP4_S3_lib import load, stream

FROZEN = L.ROOT / "results" / "WP4" / "s7_domain"
HOST = 49
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def stream_block(run, blk):
    """All flows of a block through the runner, one at a time -> per-flow combined / per-layer Evidence and the stream time (epoch s) at which each flow's Evidence appeared."""
    recs = blk[RAW_COLUMNS].to_dict("records")
    n = len(recs)
    run.reset("blk")
    run.latency.clear()
    comb, lay, emit_t = [None] * n, [None] * n, np.full(n, np.nan)
    ts = blk["t"].to_numpy(float)
    for i, r in enumerate(recs):
        out = run.push(r)
        if out:
            _collect(out, comb, lay, emit_t, ts[i])
    out = run.flush()
    if out:
        _collect(out, comb, lay, emit_t, ts[-1])
    return comb, lay, emit_t


def _collect(out, comb, lay, emit_t, when):
    """out = [combined, layer Evidence...] per flow, flows in arrival order; sample_id = arrival index of the flow."""
    g = sum(1 for e in out if e.sample_id == out[0].sample_id)
    for j in range(0, len(out), g):
        i = int(out[j].sample_id)
        comb[i], lay[i], emit_t[i] = out[j], out[j + 1:j + g], when


def host_series(blk, comb, lay, emit_t, grp, pack_names):
    """Minute-hold ticks of the host's flows (M2 tick model) with availability times."""
    ts = blk["t"].to_numpy(float)
    m = ((blk["src_id"].to_numpy() == HOST) | (blk["dst_id"].to_numpy() == HOST))
    idx = np.flatnonzero(m)
    if not len(idx):
        return None
    names = [e.name for e in lay[idx[0]]]
    Lm = np.array([[e.score for e in lay[i]] for i in idx], np.float32)
    Am = np.array([[e.alarm for e in lay[i]] for i in idx], bool)
    fam = blk["family"].astype(str).to_numpy()[idx]
    att = fam != "BENIGN"
    mins = (ts[idx] // 60).astype(np.int64)
    u, inv = np.unique(mins, return_inverse=True)
    V = ST.tick_max(inv, Lm, len(u))
    lab = ST.tick_any(inv, att, len(u))
    fm = ST.tick_family(inv, np.where(att, fam, ""), len(u))
    cnt = np.bincount(inv, minlength=len(u)).astype(np.float32)
    nmin = int(u.max()) - int(u.min()) + 2
    j = u - u.min() + 1
    Vt = np.zeros((nmin, V.shape[1]), np.float32)
    Lt = np.zeros(nmin, bool)
    Ft = np.full(nmin, "", object)
    Ct = np.zeros(nmin, np.float32)
    Tmin = np.zeros(nmin, bool)                                   # tick minute holds a value
    avail_min = np.full(nmin, np.nan)
    Vt[j], Lt[j], Ft[j], Ct[j], Tmin[j] = V, lab, fm, cnt, True
    t_blk0 = float(u.min() * 60)
    em = pd.Series(emit_t[idx]).groupby(inv).max().to_numpy() - t_blk0
    avail_min[j] = np.maximum(em, (j) * 60.0)                       # the held value starts at its minute; visible when the bin closed
    # alarm flags per tick: any flow alarm of that minute
    A = np.zeros((nmin, V.shape[1]), bool)
    for c in range(V.shape[1]):
        A[j, c] = pd.Series(Am[:, c]).groupby(inv).max().to_numpy()
    comb_alarm = np.zeros(nmin, bool)
    comb_alarm[j] = pd.Series(np.array([comb[i].alarm for i in idx])).groupby(inv).max().to_numpy()
    comb_score = np.zeros(nmin, np.float32)
    comb_score[j] = pd.Series(np.array([comb[i].score for i in idx], np.float32)).groupby(inv).max().to_numpy()
    rep = lambda x: np.repeat(x, 60, axis=0)
    avail = np.repeat(np.where(np.isnan(avail_min), 0.0, avail_min), 60)
    avail = np.maximum(avail, np.arange(nmin * 60) + 1.0)
    fam_t = rep(Ft)
    lab_t = rep(Lt)
    kind = "attack" if lab_t.any() else "clean"
    fams = sorted(set(fam_t[lab_t]))
    # first attack minute start in flow time (block clock) of each tick's held minute
    s = L.make_series(grp, grp, kind, ",".join(fams) if fams else "none", rep(comb_score), rep(Vt), rep(comb_alarm), rep(A), lab_t, np.arange(nmin * 60) + 0.0, fam=fam_t,
                      count=rep(Ct), avail=avail)
    s["layer_names"] = names
    s["t_block0"] = t_blk0
    s["minute_bounds"] = (int(u.min()), int(u.max()))
    s["host_flows"] = int(len(idx))
    s["audit_flows"] = int(blk["audit"].to_numpy()[idx].sum())
    return s


def main():
    smoke = "--smoke" in sys.argv
    part_i, part_n = (int(sys.argv[sys.argv.index("--part") + 1]), int(sys.argv[sys.argv.index("--part") + 2])) if "--part" in sys.argv else (0, 1)
    dom = NetworkDomain.load(FROZEN)
    d = load("D10")
    t = stream(d, "val" if smoke else "test")
    del d
    t["src_ip"] = "h" + t["src_id"].astype(str)
    t["dst_ip"] = "h" + t["dst_id"].astype(str)
    t["blk"] = t["day"].astype(str) + "|" + t["period"].astype(str)
    blocks = sorted(t["blk"].unique())
    pack = pd.read_pickle(L.WP6C / "s5_network.pkl")["val" if smoke else "test"]
    pk = {s["name"]: s for s in pack["series"]}
    run = NetworkRunner(dom, per_layer=True)
    res = {"series": [], "latency": {}, "blocks": {}}
    chk = {}
    for bi, b in enumerate(blocks):
        if bi % part_n != part_i:
            continue
        blk = t[t["blk"] == b].sort_values(["t", "row"], kind="stable").reset_index(drop=True)
        if smoke:
            blk = blk.iloc[:3000].reset_index(drop=True)
        comb, lay, emit_t = stream_block(run, blk)
        miss = sum(c is None for c in comb)
        s = host_series(blk, comb, lay, emit_t, b, None)
        res["latency"][b] = {"ns": list(run.latency.ns), "emit": list(run.latency.emit), "size": list(run.latency.size)}
        res["blocks"][b] = {"flows": int(len(blk)), "span_s": float(blk["t"].max() - blk["t"].min()), "missing_evidence": int(miss), "t0": float(blk["t"].min()),
                            "host_flows": 0 if s is None else s["host_flows"]}
        if s is not None:
            res["series"].append(s)
            if b in pk:
                p = pk[b]
                m = min(len(p["score"]), len(s["score"]))
                chk[b] = {"ticks": int(len(s["score"])), "pack_ticks": int(len(p["score"])), "max_score_diff": float(np.abs(np.asarray(p["score"])[:m] - s["score"][:m]).max()),
                          "label_equal": bool((np.asarray(p["label"])[:m] == s["label"][:m]).all()), "alarm_mismatch": int(((np.asarray(p["score"])[:m] >= pack["dom_thr"]) != s["dom_alarm"][:m]).sum()),
                          "max_delay_s": float((s["avail"] - np.arange(len(s["avail"])) - 1.0).max()), "median_delay_s": float(np.median(s["avail"] - np.arange(len(s["avail"])) - 1.0))}
        log("block", b, res["blocks"][b], chk.get(b))
    tag = "_smoke" if smoke else (f"_p{part_i}" if part_n > 1 else "")
    L.save_pickle(res, f"S2_net{tag}.pkl")
    (L.OUT / f"S2_check_net{tag}.json").write_text(json.dumps(chk, indent=1))
    log("done")


if __name__ == "__main__":
    main()
