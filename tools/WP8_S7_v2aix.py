"""WP8 S7 V2AIX (M4-11): the 674 H31 recordings (fresh per recording; 672 share site + day with a v3 TRAIN recording = the per-deployment calibration regime, 2 are independent). python -I compatible; V2AIX data
and per-message outputs are NEVER committed (no cache written, aggregates only).
Added AFTER the S7 freeze commit as a separate scoring tool; its sha256 is in results/WP8/S7/freeze_addendum.json, written before the first H31 recording is read.
Rows:
  (1) genuine false alarms per message of the frozen physics stack with the V31_val-fitted variant-B calibration (tools/WP5_S3b_lib.Setup with val := the v3 val + test recordings = V31_val, per environment
      Mobile / Stationary; thresholds 1 % of the V31_val genuine messages) on the H31 recordings; separately for the 672 same-site-day recordings and the 2 independent ones (descriptive); also variant A (frozen VeReMi calibration).
  (2) injected VeReMi-taxonomy attacks (v2x/v2aix_inject.py scenarios from the H31 recordings of the environment, scored once): physics-config message-level detection per type, mean over types; the frozen domain is
      the same object in v3 and v3.1, so the v3 (batch) and v3.1 (EgoStream) detection are compared on the stream-checked egos (paired difference of the raw scores' alarms).
  (3) single-ego runtime: EgoStream on every H31 Mobile recording with a full ego pose (tools/WP8_S5_v2x.run_ego): compute per stream second (rule <= 0.5), p99 per message, mismatches vs the time-sorted batch.
Output: results/WP8/S7/v2aix.json. Run: python -I -u -W ignore tools/WP8_S7_v2aix.py [--max-egos N]"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True

import numpy as np
import pandas as pd

import WP8_S7_lib as S7
import WP5_S3b_lib as L
import WP8_S5_v2x as S5V
from system.v2x_runner import LAYER_NAMES, V2XPhysicsDomain
from v2x import l4, v2aix, v2aix_eval as ev, v2aix_inject as inj

H31_ROOT = S7.DATA_EXTRA / "D13_v2aix" / "extracted_v31" / "json"
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def site_day(rid):
    p = rid.split("/")
    return (p[0] + "/" + p[2], p[3][:10])


def boot_groups(vals, groups, B=1000, seed=31):
    """rate with a 95 % CI resampling recordings (cluster bootstrap over `groups`); vals bool array per message."""
    g = pd.Series(vals.astype(float)).groupby(np.asarray(groups)).agg(["sum", "count"])
    s, c = g["sum"].to_numpy(), g["count"].to_numpy()
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(B):
        i = rng.integers(0, len(s), len(s))
        bs.append(s[i].sum() / c[i].sum())
    return float(s.sum() / c.sum()), [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]


def load_h31(env, rids):
    paths = {v2aix.recording_id(p, H31_ROOT): p for p in v2aix.list_recordings(H31_ROOT)}
    parts = []
    for rid in rids:
        if not rid.startswith(env + "/") or rid not in paths:
            continue
        d = v2aix.load_recording(paths[rid], H31_ROOT, cache=False)
        if len(d):
            parts.append(d)
    df = pd.concat(parts, ignore_index=True)
    df["env"] = env
    df["loc"] = df["recording"].map(v2aix.stratum_of)
    return df.sort_values(["recording", "track", "t"], kind="stable").reset_index(drop=True)


def main():
    global H31_ROOT
    max_egos = int(sys.argv[sys.argv.index("--max-egos") + 1]) if "--max-egos" in sys.argv else 0
    dry = int(sys.argv[sys.argv.index("--dry") + 1]) if "--dry" in sys.argv else 0
    S7.open_guard()
    outd = S7.OUT / ("v2aix_dry" if dry else "v2aix")
    outd.mkdir(parents=True, exist_ok=True)
    sp = json.loads((S7.ROOT / "results" / "WP5" / "splits_v2aix.json").read_text())
    v31 = json.loads((S7.ROOT / "locks" / "V31_val.json").read_text())["domains"]["v2x"]["v2aix"]
    val31 = sorted(v31["val"])
    assert val31 == sorted(set(sp["val"]) | set(sp["test"])), "V31_val V2AIX list differs from the v3 val + test split"
    sp31 = dict(sp, val=val31)
    (outd / "splits_v2aix.json").write_text(json.dumps(sp31))
    L.OUT = outd                                                  # Setup reads <OUT>/splits_v2aix.json: val := V31_val
    rids = [r["rid"] for r in S7.h31()["domains"]["v2x"]["fresh"]["v2aix"]["recordings"]]
    if dry:                                       # dry run on v3 TEST recordings (now V31_val) read from the v3 extraction, a few per environment; output to results/WP8/S7/v2aix_dry.json
        H31_ROOT = v2aix.JSON_ROOT
        rids = [r for env in L.ENVS for r in [x for x in sp["test"] if x.startswith(env + "/")][:dry]]
    train_sd = {site_day(r) for r in sp["train"]}
    if dry:
        S7.journal("S7", "V2AIX dry run on v3 test recordings (V31_val), not H31", f"{dry} per environment")
    same_sd = {r: site_day(r) in train_sd for r in rids}
    S7.journal("S7", "V2AIX H31: start", f"{len(rids)} recordings, {sum(same_sd.values())} same site-day as a v3 train recording; out results/WP8/S7/v2aix.json")
    res = {"exposure": "fresh H31 (per recording); 'same site-day as calibration' for the 672, 2 independent (descriptive)", "recordings": len(rids), "same_site_day": int(sum(same_sd.values())),
           "independent": sorted(r for r, v in same_sd.items() if not v), "envs": {}}
    dom = V2XPhysicsDomain.load(S7.ROOT / "results" / "WP7" / "frozen_v2x")
    f_out = S7.OUT / ("v2aix_dry.json" if dry else "v2aix.json")
    for env in L.ENVS:
        S = L.Setup(env)
        df = load_h31(env, rids)
        log(env, "setup done; val messages", len(S.val), "H31 messages", len(df), "recordings", df["recording"].nunique())
        sc = S.score(df)
        al = sc["alarm"]
        e = {"val_messages": int(len(S.val)), "val_recordings": int(S.val["recording"].nunique()), "h31_messages": int(len(df)), "h31_recordings": int(df["recording"].nunique()),
             "k_val": S.k_val, "thresholds_B_comb": S.B.comb_thr, "false_alarms": {}}
        sd = df["recording"].map(same_sd).to_numpy(bool)
        for name in ("physics", "A_physics", "L1", "L2", "L3"):
            a = np.asarray(al[name], bool)
            p, ci = boot_groups(a, df["recording"].to_numpy())
            e["false_alarms"][name] = {"per_message": p, "ci": ci, "same_site_day": float(a[sd].mean()) if sd.any() else None, "independent": float(a[~sd].mean()) if (~sd).any() else None,
                                       "n_independent_messages": int((~sd).sum())}
        e["false_alarms"]["V31_val_target_per_message"] = 0.01
        log(env, "FA physics", e["false_alarms"]["physics"])
        # ---- injected attacks
        e["injected"] = {}
        for code in inj.ALL_TYPES:
            try:
                scn, att = inj.build_scenario(df, code)
            except ValueError as err:
                e["injected"][code] = {"error": str(err)}
                continue
            y = scn["injected"].to_numpy(bool)
            if not y.any():
                continue
            s = S.score(scn)
            kinds = np.asarray(l4.row_kinds(scn))
            a = s["alarm"]["physics"]
            p, ci = boot_groups(a[y], scn["recording"].to_numpy()[y])
            e["injected"][code] = {"name": inj.type_name(code), "n_injected": int(y.sum()), "physics_msg_all": p, "ci": ci,
                                   "physics_msg_scored": float(a[y & (kinds == 0)].mean()) if (y & (kinds == 0)).any() else None, "fa_on_scenario_genuine": float(a[~y].mean())}
            log(env, code, e["injected"][code]["name"], round(p, 3))
        det = [v["physics_msg_all"] for v in e["injected"].values() if "physics_msg_all" in v]
        e["injected_mean_over_types"] = float(np.mean(det)) if det else None
        res["envs"][env] = e
        S7.write_json(res, f_out)
        del df, sc
    # ---- single-ego runtime on the H31 Mobile recordings with a full ego pose
    egos = []
    for rid in rids:
        if not rid.startswith("Mobile/"):
            continue
        if max_egos and len(egos) >= max_egos:
            break
        paths = {v2aix.recording_id(p, H31_ROOT): p for p in v2aix.list_recordings(H31_ROOT)}
        d = v2aix.load_recording(paths[rid], H31_ROOT, cache=False)
        if not len(d) or not np.isfinite(d["rx_x"].to_numpy(float)).all():
            continue
        order = np.lexsort((np.arange(len(d)), d["recv_s"].to_numpy(float)))
        braw = v2aix_eval_raws = ev.raws(dom.tracker, d)
        sdf = d.iloc[order].reset_index(drop=True)
        braw = {c: np.asarray(braw[c])[order] for c in LAYER_NAMES}
        r, _ = S5V.run_ego(dom, sdf, braw, True, sdf["recv_s"].to_numpy(float))
        r["ego"] = rid
        egos.append(r)
        log("ego", rid, round(r["compute_per_stream_s"], 4), r["raw_mismatch_total"])
    comp = np.array([e["compute_per_stream_s"] for e in egos])
    res["runtime"] = {"egos": len(egos), "compute_per_stream_s_max": float(comp.max()) if len(comp) else None, "share_le_0.5": float((comp <= 0.5).mean()) if len(comp) else None,
                      "msg_p99_ms_max": float(max(e["msg_ms"]["p99"] for e in egos)) if egos else None, "identical_egos": int(sum(e["raw_mismatch_total"] == 0 for e in egos)),
                      "mismatch_rows_total": int(sum(e["mismatch_rows"] for e in egos)), "mismatch_rows_unexplained": int(sum(e["mismatch_rows_unexplained"] for e in egos)),
                      "messages_total": int(sum(e["messages"] for e in egos)), "evidence_alarm_mismatch": int(sum(e["evidence_alarm_mismatch"] for e in egos)),
                      "per_ego": [{k: e[k] for k in ("ego", "messages", "stream_s", "compute_per_stream_s", "raw_mismatch_total", "mismatch_rows", "reordered")} for e in egos]}
    S7.write_json(res, f_out)
    S7.journal("S7", "V2AIX H31: done", f"FA physics Mobile {res['envs']['Mobile']['false_alarms']['physics']['per_message']:.4f}, egos {len(egos)}")


if __name__ == "__main__":
    main()
