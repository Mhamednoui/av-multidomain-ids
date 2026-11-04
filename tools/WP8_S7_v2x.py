"""WP8 S7 V2X (VeReMi TEST blocks = H31 'V2X re-used', exposure n+1): ego views of the frozen VeReMi physics stack (system/v2x_runner.V2XPhysicsDomain, results/WP7/frozen_v2x), same construction as
WP8_S2_build.stage_v2x (class 12 dropped; ego = a genuine sender with >= 60 s of track, heard set = other senders within 300 m of the ego's interpolated position; at most 40 egos per block, evenly spaced;
each ego's heard table scored as that receiver hears it: V2XPhysicsDomain.raws == EgoStream, S5). The V2X Evidence is the same frozen object in v3 and v3.1.
`--split val` is the dry run on VALIDATION blocks (output to --out; the sources must equal ../data_extra/cache_v3/WP8/S2/v2x.pkl).
Output: ../data_extra/cache_v3/WP8/S7/v2x_parts/block_<g>.pkl (resumable) and v2x.pkl, results/WP8/scores/S7/v2x_veremi_test.npz (per-tick scores / labels per ego series).
Run: python -u -W ignore tools/WP8_S7_v2x.py [--split test|val] [--out DIR]"""
import argparse
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S7_lib as S7

import numpy as np
import pandas as pd

import WP5_S5_dev as dev5
import WP8_S2_build as B2
from WP5_S2_l1 import aname
from system.v2x_runner import LAYER_NAMES, V2XPhysicsDomain
from v2x import splitting


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    test = a.split == "test"
    if test:
        S7.open_guard()
    cache = S7.CACHE if test else Path(a.out)
    part = cache / "v2x_parts"
    part.mkdir(parents=True, exist_ok=True)
    dom = V2XPhysicsDomain.load(S7.ROOT / "results" / "WP7" / "frozen_v2x")
    S7.journal("S7", f"V2X VeReMi {a.split}: start", f"parts {part}")
    v, sp = dev5.load_frames()
    va = splitting.rows_of(v, sp[a.split])
    del v
    va = va[va["label"] != 12]
    groups = sorted(va["group"].astype(str).unique(), key=lambda g: int(g))
    for g in groups:
        f = part / f"block_{g}.pkl"
        if f.exists():
            print("skip block", g, flush=True)
            continue
        blk = va[va["group"].astype(str) == g].sort_values("t", kind="stable").reset_index(drop=True)
        lab, snd, t = blk["label"].to_numpy(), blk["sender"].to_numpy(), blk["t"].to_numpy(float)
        x, y = blk["x"].to_numpy(float), blk["y"].to_numpy(float)
        bad = pd.Series(lab > 0).groupby(snd).any()
        dur = pd.Series(t).groupby(snd).agg(lambda s: s.max() - s.min())
        cand = sorted(s for s in dur.index if not bad[s] and dur[s] >= B2.EGO_MIN_S)
        k_ = int(np.ceil(len(cand) / B2.EGOS_PER_BLOCK)) if cand else 1
        pick = cand[::max(k_, 1)][:B2.EGOS_PER_BLOCK]
        series, clean_msg = [], []
        for e in pick:
            me = snd == e
            te, xe, ye = t[me], x[me], y[me]
            t0, t1 = te.min(), te.max()
            w = (t >= t0) & (t <= t1) & ~me
            ex, ey = np.interp(t[w], te, xe), np.interp(t[w], te, ye)
            idx = np.flatnonzero(w)[np.hypot(x[w] - ex, y[w] - ey) <= B2.RADIUS_M]
            if len(idx) < 2:
                continue
            sub = blk.iloc[idx].copy().reset_index(drop=True)
            sub["rx_id"] = "ego"
            raws = dom.raws(sub)
            cal = dom.calibrated(raws)
            C = np.column_stack([cal[nm] for nm in LAYER_NAMES]).astype(np.float32)
            comb = C.max(axis=1)
            alarm = comb >= dom.comb_thr
            lalarm = np.column_stack([cal[nm] >= dom.thr[nm] for nm in LAYER_NAMES])
            n = int(np.ceil(t1 - t0)) + 1
            kk = np.clip(np.floor(t[idx] - t0).astype(np.int64), 0, n - 1)
            lb = lab[idx]
            gen = lb == 0
            clean_msg.append(comb[gen])

            def pack(sel, kind, fam_t, lab_t):
                ks = kk[sel]
                return {"group": g, "name": f"{g}/ego{e}/{kind}", "kind": kind, "ego": str(e), "score": B2.tick_max(ks, comb[sel], n), "layers": B2.tick_max(ks, C[sel], n),
                        "dom_alarm": B2.tick_any(ks, alarm[sel], n), "layer_alarm": B2.tick_any(ks, lalarm[sel], n), "count": np.bincount(ks, minlength=n)[:n].astype(np.float32),
                        "label": lab_t, "fam": fam_t}
            series.append(pack(gen, "clean", np.full(n, "", object), np.zeros(n, bool)))
            if (~gen).any():
                fam = np.where(gen, "", np.array([aname(int(c)) if c > 0 else "" for c in lb], object))
                series.append(pack(np.ones(len(idx), bool), "attack", B2.tick_family(kk, fam, n), B2.tick_any(kk, ~gen, n)))
        obj = {"group": g, "series": series, "clean_msg": np.concatenate(clean_msg) if clean_msg else np.zeros(0, np.float32), "candidates": len(cand), "picked": len(pick)}
        tmp = f.with_suffix(".tmp")
        pickle.dump(obj, open(tmp, "wb"), protocol=4)
        tmp.replace(f)
        print("v2x block", g, "candidates", len(cand), "egos", len(pick), "series", len(series), "messages", len(blk), flush=True)
    allp = [pickle.load(open(part / f"block_{g}.pkl", "rb")) for g in groups]
    pickle.dump({"series": [s for p in allp for s in p["series"]], "clean_msg": {p["group"]: p["clean_msg"] for p in allp},
                 "blocks": {p["group"]: {"candidates": p["candidates"], "picked": p["picked"]} for p in allp}, "layer_names": LAYER_NAMES, "comb_thr": float(dom.comb_thr)},
                open(cache / "v2x.pkl", "wb"), protocol=4)
    S7.journal("S7", f"V2X VeReMi {a.split}: done", f"{sum(len(p['series']) for p in allp)} ego series")


if __name__ == "__main__":
    main()
