"""WP5 S3b step 2: the frozen V2X physics stack and the receiver-position layers on GENUINE real V2AIX traffic (test scored once; thresholds from validation).
Variants: A = frozen VeReMi calibration, B = re-calibrated on the genuine V2AIX validation recordings of the same environment (Mobile and Stationary separately).
Outputs: results/WP5/s3b_clean.json, results/WP5/s3b_clean.md. Run from codes_v3/: python -I -u -W ignore tools/WP5_S3b_clean.py  (--smoke: score VALIDATION as stand-in test).
No per-message output is written (licence)."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP5_S3b_lib as L

import numpy as np
import pandas as pd

from v2x import l2, l_rx
from v2x import v2aix_eval as ev

T0 = time.time()
SMOKE = "--smoke" in sys.argv


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def rate_block(df, alarm):
    p, lo, hi, n = ev.boot_rate(df, alarm)
    return {"p": p, "ci": [lo, hi], "n": n, "alarms": int(np.sum(alarm))}


def sender_block(df, alarm, k_val, k3=3):
    c = ev.sender_counts(df, alarm)["n_alarm"]
    return {"n_senders": int(len(c)), "k3": float((c >= k3).mean()), "k_val": int(k_val), "at_k_val": float((c >= k_val).mean()),
            "senders_k3": int((c >= k3).sum()), "senders_kval": int((c >= k_val).sum())}


def sender_profile(df, alarm_b, alarm_a, layers_b):
    """Per sender: size, alarms, kinematic anomalies (implied speed, reported speed, jumps) for the senders whose alarms may be real anomalies."""
    d = df[["sender", "recording", "loc", "t", "x", "y", "speed", "track"]].copy()
    d["ab"], d["aa"] = np.asarray(alarm_b, bool), np.asarray(alarm_a, bool)
    for n, a in layers_b.items():
        d[n] = a
    d = d.sort_values(["track", "t"], kind="stable")
    same = d["track"].to_numpy()[1:] == d["track"].to_numpy()[:-1]
    dt = np.diff(d["t"].to_numpy())
    dd = np.hypot(np.diff(d["x"].to_numpy()), np.diff(d["y"].to_numpy()))
    ok = same & (dt > 0) & (dt <= 5.0)
    imp = np.where(ok, dd / np.maximum(dt, 1e-3), 0.0)
    d["imp"] = np.r_[0.0, imp]
    d["jump"] = np.r_[0.0, np.where(ok, dd, 0.0)]
    d["gj"] = (d["imp"] > 70.0) & (d["jump"] >= 15.0)          # GNSS jump: moved faster than any road car between two CAMs and by more than the GNSS noise
    g = d.groupby("sender", sort=False)
    t = g.agg(recording=("recording", "first"), loc=("loc", "first"), n=("ab", "size"), alarms_B=("ab", "sum"), alarms_A=("aa", "sum"), v_max=("speed", "max"),
              v_med=("speed", "median"), imp_max=("imp", "max"), jump_max=("jump", "max"))
    t["imp_gt70"] = g["gj"].sum()
    t["share_B"] = t["alarms_B"] / t["n"]
    lay = d.groupby("sender", sort=False)[list(layers_b)].sum()
    t["top_layers"] = lay.apply(lambda r: ",".join(f"{k.split('.')[1]}:{int(v)}" for k, v in r.sort_values(ascending=False).head(3).items() if v > 0), axis=1)
    return t


def describe(r):
    if r["imp_gt70"] > 0:
        return "GNSS position jump (position moved at > 70 m/s between two CAMs, by >= 15 m)"
    if r["v_max"] > 70:
        return "speed glitch (reported speed > 70 m/s)"
    if r["v_med"] < 1.0:
        return "parked / queuing sender (median speed < 1 m/s): heading and speed noise at standstill"
    return "no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs)"


def main():
    res = {"smoke": SMOKE, "envs": {}}
    md = [f"# S3b real genuine traffic ({'VALIDATION stand-in (smoke)' if SMOKE else 'TEST, scored once'}); thresholds from validation of the same environment", ""]
    glitch_rows = []
    for env in L.ENVS:
        S = L.Setup(env)
        S.k_val["A_physics"] = ev.k_for_budget(ev.sender_counts(S.val, S.alarms_A(S.val, S.raw_val)[0])["n_alarm"])
        log(env, "setup done; val messages", len(S.val), "k val", S.k_val)
        test = S.val if SMOKE else L.load_env("test", env, S.sp)
        sc = S.score(test)
        al = sc["alarm"]
        hours = ev.recording_hours(test)
        e = {"n_messages": int(len(test)), "n_senders": int(test["sender"].nunique()), "n_recordings": int(test["recording"].nunique()), "receiver_hours": hours,
             "val": {"messages": int(len(S.val)), "senders": int(S.val["sender"].nunique()), "recordings": int(S.val["recording"].nunique()), "receiver_hours": ev.recording_hours(S.val)},
             "thresholds_B": S.B.thr, "comb_threshold_B": S.B.comb_thr, "comb_threshold_A": S.A.comb_thr, "cfg_threshold_B": S.cfg_thr,
             "k_val": S.k_val}
        # ---- thresholds in raw units for the receiver layers ----
        rv = S.range.calibrator.sorted_
        e["range_pooled_val_raw_quantiles_km"] = {str(q): float(np.quantile(rv, q)) for q in (0.5, 0.9, 0.99, 0.999, 1.0)}
        e["range_loc_val_p99_km"] = {loc: float(np.quantile(lay.calibrator.sorted_, 0.99)) for loc, lay in S.range_loc.items()}
        # ---- false alarms per message / sender / hour ----
        fa = {}
        for name in ["A_physics", "physics", "L1", "L2", "L3", "fresh", "physics+fresh", "range", "range_loc", "physics+range", "rx", "physics+rx", "appear"]:
            a = al[name]
            if name == "appear":
                _, evf = l_rx.first_flags(test)
                fa[name] = {"per_message": rate_block(test, a), "alarms": int(a.sum()), "evaluable_first_messages": int(evf.sum()),
                            "per_evaluable_first": float(a[evf].mean()) if evf.any() else None,
                            "physical_300m_alarms_on_evaluable_first": float(l_rx.appearance_physical_alarm(test)[evf].mean()) if evf.any() else None}
                continue
            if name in ("range", "range_loc"):
                fin = np.isfinite(l_rx.distance_to_receiver(test))
                fa[name] = {"per_message": rate_block(test, a), "per_message_with_rx": float(a[fin].mean()) if fin.any() else None, "messages_with_rx": int(fin.sum())}
            else:
                fa[name] = {"per_message": rate_block(test, a)}
            fa[name]["alarms"] = int(a.sum())
            fa[name]["alarms_per_hour"] = float(a.sum() / hours) if hours > 0 else None
            fa[name]["events_per_hour"] = float(ev.alarm_events(test, a) / hours) if hours > 0 else None
            fa[name]["sender"] = sender_block(test, a, S.k_val.get(name, S.k_val["physics"]))
        e["false_alarms"] = fa
        e["per_layer_FA"] = {"A": {n.split(".")[1]: float(a.mean()) for n, a in sc["A_layers"].items()},
                             "B": {n.split(".")[1]: float(a.mean()) for n, a in sc["B_layers"].items()}}
        # ---- per location ----
        e["per_location"] = {}
        for loc, h in test.groupby("loc"):
            m = (test["loc"] == loc).to_numpy()
            hh = ev.recording_hours(h)
            e["per_location"][loc] = {"messages": int(m.sum()), "recordings": int(h["recording"].nunique()), "hours": hh,
                                      "FA_B_physics": float(al["physics"][m].mean()), "FA_A_physics": float(al["A_physics"][m].mean()),
                                      "alarms_per_hour_B": float(al["physics"][m].sum() / hh) if hh > 0 else None,
                                      "FA_range_pooled": float(al["range"][m].mean()), "FA_range_loc": float(al["range_loc"][m].mean())}
        # ---- row kinds ----
        k = np.asarray(__import__("v2x.l4", fromlist=["row_kinds"]).row_kinds(test))
        e["row_kinds"] = {"scored": float((k == 0).mean()), "unscored_first_or_gap": float((k == 1).mean()), "exact_repeat": float((k == 2).mean())}
        e["FA_B_scored_rows"] = float(al["physics"][k == 0].mean())
        # ---- where do the false alarms sit: distance to the receiver and gap since the previous CAM of the sender ----
        d = l_rx.distance_to_receiver(test)
        e["FA_B_by_distance"] = {}
        for lo, hi, nm in ((0, 100, "<100 m"), (100, 300, "100-300 m"), (300, 1000, "0.3-1 km"), (1000, 2000, "1-2 km"), (2000, 5000, "2-5 km"), (5000, 1e9, ">5 km")):
            m = np.isfinite(d) & (d >= lo) & (d < hi)
            e["FA_B_by_distance"][nm] = {"messages": int(m.sum()), "FA_B_physics": float(al["physics"][m].mean()) if m.any() else None}
        pr = l2.Pairs(test)
        gap = np.empty(len(test))
        gap[pr.order] = np.where(pr.valid, pr.dt, np.nan)
        e["FA_B_by_gap"] = {}
        for lo, hi, nm in ((0, 0.2, "<0.2 s"), (0.2, 0.5, "0.2-0.5 s"), (0.5, 1.0, "0.5-1 s"), (1.0, 2.0, "1-2 s"), (2.0, 5.01, "2-5 s")):
            m = np.isfinite(gap) & (gap >= lo) & (gap < hi)
            e["FA_B_by_gap"][nm] = {"messages": int(m.sum()), "FA_B_physics": float(al["physics"][m].mean()) if m.any() else None}
        e["FA_B_by_gap"]["no predecessor (first / after gap)"] = {"messages": int((~np.isfinite(gap)).sum()), "FA_B_physics": float(al["physics"][~np.isfinite(gap)].mean())}
        # ---- anomalous senders ----
        prof = sender_profile(test, al["physics"], al["A_physics"], sc["B_layers"])
        prof["kind"] = prof.apply(describe, axis=1)
        top = prof.sort_values(["alarms_B"], ascending=False)
        e["flagged_senders_B"] = {"senders_with_ge1_alarm": int((prof["alarms_B"] > 0).sum()), "senders_with_k3": int((prof["alarms_B"] >= 3).sum()),
                                  "kinds_among_k3": {k_: int(v) for k_, v in prof[prof["alarms_B"] >= 3]["kind"].value_counts().items()},
                                  "alarm_share_in_k3_senders": float(prof[prof["alarms_B"] >= 3]["alarms_B"].sum() / max(prof["alarms_B"].sum(), 1)),
                                  "top": [{"rank": i + 1, "env_loc": r["loc"], "messages": int(r["n"]), "alarms_B": int(r["alarms_B"]), "alarms_A": int(r["alarms_A"]),
                                           "v_max": float(r["v_max"]), "implied_speed_max": float(r["imp_max"]), "jump_max_m": float(r["jump_max"]), "kind": r["kind"],
                                           "top_layers": r["top_layers"]} for i, (_, r) in enumerate(top.head(12).iterrows())]}
        res["envs"][env] = e
        log(env, "FA B physics", fa["physics"]["per_message"]["p"], "FA A", fa["A_physics"]["per_message"]["p"])
        # ---- speeds > 70 m/s over all splits ----
        full = pd.concat([L.load_env(p, env, S.sp).assign(part=p) for p in ("train", "val", "test")], ignore_index=True)
        gl = full[full["speed"] > 70]
        for _, r in gl.iterrows():
            rec = full[full["recording"] == r["recording"]].sort_values(["track", "t"], kind="stable").reset_index(drop=True)
            same = rec[(rec["sender"] == r["sender"])]
            i = int(np.flatnonzero((same["t"] == r["t"]).to_numpy())[0])
            s2 = S.score(rec)
            pos = int(np.flatnonzero(((rec["sender"] == r["sender"]) & (rec["t"] == r["t"])).to_numpy())[0])
            glitch_rows.append({"env": env, "split": r["part"], "location": r["loc"], "speed_mps": float(r["speed"]), "sender_msgs_in_recording": int(len(same)),
                                "prev_speed": float(same["speed"].iloc[i - 1]) if i > 0 else None, "next_speed": float(same["speed"].iloc[i + 1]) if i + 1 < len(same) else None,
                                "pos_sigma": float(r["pos_sigma"]), "alarm_L1_field_ranges_B": bool(s2["B_layers"]["v2x.field_ranges"][pos]),
                                "alarm_physics_A": bool(s2["alarm"]["A_physics"][pos]), "alarm_physics_B": bool(s2["alarm"]["physics"][pos]),
                                "layers_B_alarming": [n.split(".")[1] for n, a in s2["B_layers"].items() if a[pos]]})
        log(env, "glitch rows", len(gl))
    res["speed_gt_70"] = glitch_rows
    out = L.OUT / ("s3b_clean_smoke.json" if SMOKE else "s3b_clean.json")
    out.write_text(json.dumps(res, indent=1, default=float))
    # ---- markdown ----
    def pc(x, d=2):
        return "-" if x is None else f"{100 * x:.{d}f}%"
    for env, e in res["envs"].items():
        md += [f"## {env}: {e['n_messages']} genuine messages, {e['n_senders']} senders, {e['n_recordings']} recordings, {e['receiver_hours']:.2f} receiver-hours (validation: {e['val']['messages']} msgs, {e['val']['senders']} senders)", "",
               "| configuration | FA per message [95% CI by recordings] | alarms / receiver-hour | alarm events / hour | senders k=3 | senders k val (k) |", "|---|---|---|---|---|---|"]
        for name, f in e["false_alarms"].items():
            if name == "appear":
                continue
            s = f["sender"]
            m = f["per_message"]
            kv = "n/a" if name == "A_physics" else f"{pc(s['at_k_val'], 1)} (k={s['k_val']})"
            md.append(f"| {name} | {pc(m['p'], 2)} [{pc(m['ci'][0], 2)}, {pc(m['ci'][1], 2)}] | {f['alarms_per_hour']:.0f} | {f['events_per_hour']:.0f} | {pc(s['k3'], 1)} ({s['senders_k3']}/{s['n_senders']}) | {kv} |")
        a = e["false_alarms"]["appear"]
        md += ["", f"Appearance (data-driven 1% of evaluable first messages): evaluable genuine first messages in this set {a['evaluable_first_messages']}, alarms {a['alarms']} "
               f"(per evaluable first message {pc(a['per_evaluable_first'])}, per message {pc(a['per_message']['p'], 3)}); physical 300 m design value alarms {pc(a['physical_300m_alarms_on_evaluable_first'])} of them.",
               f"Range with receiver position: messages {e['false_alarms']['range']['messages_with_rx']}; pooled FA among them {pc(e['false_alarms']['range']['per_message_with_rx'])}; per-location FA {pc(e['false_alarms']['range_loc']['per_message_with_rx'])}.",
               f"Row kinds: {e['row_kinds']}; FA of B physics on scored rows {pc(e['FA_B_scored_rows'])}.", "",
               "Per check FA, A (frozen VeReMi) vs B (V2AIX validation):", "", "| check | A | B |", "|---|---|---|"]
        for n in e["per_layer_FA"]["A"]:
            md.append(f"| {n} | {pc(e['per_layer_FA']['A'][n])} | {pc(e['per_layer_FA']['B'][n])} |")
        md += ["", "| location | messages | recordings | hours | FA B physics | alarms/h B | FA A physics | FA range pooled | FA range per-location |", "|---|---|---|---|---|---|---|---|---|"]
        for loc, v in e["per_location"].items():
            md.append(f"| {loc} | {v['messages']} | {v['recordings']} | {v['hours']:.2f} | {pc(v['FA_B_physics'])} | " + (f"{v['alarms_per_hour_B']:.0f}" if v["alarms_per_hour_B"] is not None else "-") +
                      f" | {pc(v['FA_A_physics'])} | {pc(v['FA_range_pooled'])} | {pc(v['FA_range_loc'])} |")
        md += ["", "B physics false alarms by distance to the receiver / by gap since the sender's previous CAM:", "", "| bin | messages | FA |", "|---|---|---|"]
        for nm, v in list(e["FA_B_by_distance"].items()) + list(e["FA_B_by_gap"].items()):
            md.append(f"| {nm} | {v['messages']} | {pc(v['FA_B_physics'])} |")
        fs = e["flagged_senders_B"]
        md += ["", f"Senders with >= 1 B alarm: {fs['senders_with_ge1_alarm']} of {e['n_senders']}; with >= 3: {fs['senders_with_k3']}; their share of all B alarms {pc(fs['alarm_share_in_k3_senders'], 0)}; kinds among the k>=3 senders: {fs['kinds_among_k3']}.", "",
               "| rank | location | messages | alarms B | alarms A | v max | implied speed max | jump max (m) | kind | top checks |", "|---|---|---|---|---|---|---|---|---|---|"]
        for r in fs["top"]:
            md.append(f"| {r['rank']} | {r['env_loc']} | {r['messages']} | {r['alarms_B']} | {r['alarms_A']} | {r['v_max']:.1f} | {r['implied_speed_max']:.1f} | {r['jump_max_m']:.0f} | {r['kind']} | {r['top_layers']} |")
        md.append("")
    md += ["## Speeds above 70 m/s (all splits, left in the data)", "", "| env | split | location | speed (m/s) | prev / next speed | pos sigma | L1 field_ranges (B) | physics A | physics B | checks alarming (B) |", "|---|---|---|---|---|---|---|---|---|---|"]
    for g in glitch_rows:
        md.append(f"| {g['env']} | {g['split']} | {g['location']} | {g['speed_mps']:.2f} | {g['prev_speed']} / {g['next_speed']} | {g['pos_sigma']:.1f} | {g['alarm_L1_field_ranges_B']} | {g['alarm_physics_A']} | {g['alarm_physics_B']} | {','.join(g['layers_B_alarming'])} |")
    (L.OUT / ("s3b_clean_smoke.md" if SMOKE else "s3b_clean.md")).write_text("\n".join(md))
    log("done")


if __name__ == "__main__":
    main()
