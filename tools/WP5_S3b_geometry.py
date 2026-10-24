"""WP5 S3b step 1: explain (or not) the km-scale sender-to-ego distances of V2AIX before any acceptance-range calibration.
Data used: TRAIN + VALIDATION recordings only (a diagnosis of the data, nothing is fitted; the test recordings are not read here).
Checks (criteria fixed in notes/WP5_v2x.md before this script was run):
  E1 frame      distance in the local frame vs haversine on lat / lon: the scale error at the reported distance
  E2 time       ego-pose alignment: share of consecutive message pairs of one sender whose change of distance exceeds what both vehicles can move
                (reported sender speed + ego speed implied by the pose, + 15 m/s slack) with the logger reception clock; compared near / far
  E3 relay      relative latency age_s of far vs near messages (store-and-forward would add latency); concentration of far messages in recordings / senders
  E4 link       free-space link budget of ITS-G5 (5.9 GHz) at the observed maximum distance vs the receiver sensitivity (documented assumptions)
Output: results/WP5/s3b_geometry.json, results/WP5/s3b_geometry.md. Run from codes_v3/: python -I -u -W ignore tools/WP5_S3b_geometry.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd

from v2x import v2aix

OUT = ROOT / "results" / "WP5"
R_EARTH = 6371008.8
BINS = [0, 100, 300, 1000, 2000, 5000, 1e9]
BIN_NAMES = ["<100 m", "100-300 m", "0.3-1 km", "1-2 km", "2-5 km", ">5 km"]


def haversine(la1, lo1, la2, lo2):
    la1, lo1, la2, lo2 = map(np.radians, (la1, lo1, la2, lo2))
    a = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return 2 * R_EARTH * np.arcsin(np.sqrt(a))


def inverse_xy(x, y):
    lat = v2aix.LAT0 + y / v2aix._M_PER_DEG
    lon = v2aix.LON0 + x / (v2aix._M_PER_DEG * np.cos(np.radians(v2aix.LAT0)))
    return lat, lon


def main():
    sp = json.loads((OUT / "splits_v2aix.json").read_text())
    df = v2aix.load_all(recordings=sp["train"] + sp["val"])
    df = df[np.isfinite(df["rx_x"]) & np.isfinite(df["rx_y"])].copy()
    df["env"] = df["recording"].str.split("/").str[0]
    df["loc"] = df["recording"].map(v2aix.stratum_of)
    df["d"] = np.hypot(df["x"] - df["rx_x"], df["y"] - df["rx_y"])
    rla, rlo = inverse_xy(df["rx_x"].to_numpy(), df["rx_y"].to_numpy())
    dh = haversine(df["lat"].to_numpy(), df["lon"].to_numpy(), rla, rlo)
    df["ratio_hav"] = np.where(df["d"] > 50, dh / np.maximum(df["d"], 1e-9), np.nan)
    df["bin"] = pd.cut(df["d"], BINS, labels=BIN_NAMES, right=False)
    res = {"n_messages": int(len(df)), "n_recordings": int(df["recording"].nunique()), "envs": {}}
    # ---- E2: distance-rate consistency, per sender track in reception order -----------------------------------------------------------
    df = df.sort_values(["track", "recv_s"], kind="stable").reset_index(drop=True)
    same = (df["track"].to_numpy()[1:] == df["track"].to_numpy()[:-1])
    dt = np.diff(df["recv_s"].to_numpy())
    dd = np.abs(np.diff(df["d"].to_numpy()))
    ego_step = np.hypot(np.diff(df["rx_x"].to_numpy()), np.diff(df["rx_y"].to_numpy()))
    ok = same & (dt > 0.02) & (dt < 1.5)
    v_ego = np.where(ok, ego_step / np.maximum(dt, 1e-3), np.nan)
    v_s = df["speed"].to_numpy()[1:]
    excess = np.where(ok, dd / np.maximum(dt, 1e-3) - (v_s + v_ego) - 15.0, np.nan)
    # E2prime (added after the first run, post-hoc, NOT the pre-registered E2): same test with the generation-time difference of the sender (the clock of its positions)
    dtg = np.diff(df["t"].to_numpy())
    ok2 = same & (dtg > 0.02) & (dtg < 1.5)
    excess2 = np.where(ok2, dd / np.maximum(dtg, 1e-3) - (v_s + np.where(ok2, ego_step / np.maximum(dt, 1e-3), np.nan)) - 15.0, np.nan)
    excess2 = np.where(ok2 & ~(dt > 0.0), np.nan, excess2)
    pair = pd.DataFrame({"env": df["env"].to_numpy()[1:], "bin": df["bin"].to_numpy()[1:], "ok": ok, "viol": excess > 0, "v_ego": v_ego,
                         "ok2": ok2 & np.isfinite(excess2), "viol2": excess2 > 0})
    for env, g in df.groupby("env"):
        e = {"messages": int(len(g)), "senders": int(g["sender"].nunique()), "recordings": int(g["recording"].nunique())}
        e["distance_m_quantiles"] = {str(q): float(np.quantile(g["d"], q)) for q in (0.5, 0.9, 0.99, 0.999, 1.0)}
        e["share_beyond_m"] = {str(r): float((g["d"] > r).mean()) for r in (300, 1000, 2000, 5000)}
        e["by_bin"] = {}
        for b in BIN_NAMES:
            h = g[g["bin"] == b]
            pe = pair[(pair["env"] == env) & (pair["bin"] == b) & pair["ok"]]
            e["by_bin"][b] = {"messages": int(len(h)), "recordings": int(h["recording"].nunique()), "senders": int(h["sender"].nunique()),
                              "age_s_p50": float(h["age_s"].median()) if len(h) else None, "age_s_p99": float(h["age_s"].quantile(0.99)) if len(h) else None,
                              "E2_pairs": int(len(pe)), "E2_violation_share": float(pe["viol"].mean()) if len(pe) else None,
                              "E2prime_pairs": int(pair[(pair["env"] == env) & (pair["bin"] == b) & pair["ok2"]].shape[0]),
                              "E2prime_violation_share": float(pair[(pair["env"] == env) & (pair["bin"] == b) & pair["ok2"]]["viol2"].mean()) if pair[(pair["env"] == env) & (pair["bin"] == b) & pair["ok2"]].shape[0] else None,
                              "haversine_over_local_ratio_p1_p99": [float(h["ratio_hav"].quantile(0.01)), float(h["ratio_hav"].quantile(0.99))] if h["ratio_hav"].notna().any() else None}
        far = g[g["d"] > 2000]
        e["far_gt_2km"] = {"messages": int(len(far)), "recordings": int(far["recording"].nunique()), "senders": int(far["sender"].nunique()),
                           "by_location": {k: int(v) for k, v in far["loc"].value_counts().items()},
                           "top_recording_share": float(far["recording"].value_counts(normalize=True).iloc[0]) if len(far) else None}
        e["ego_speed_implied_p50_p99_max"] = [float(np.nanquantile(pair[(pair["env"] == env) & pair["ok"]]["v_ego"], q)) for q in (0.5, 0.99, 1.0)]
        e["per_location"] = {}
        for loc, h in g.groupby("loc"):
            e["per_location"][loc] = {"messages": int(len(h)), "recordings": int(h["recording"].nunique()), "d_p50": float(h["d"].median()),
                                      "d_p99": float(h["d"].quantile(0.99)), "d_max": float(h["d"].max()), "rx_src": sorted(set(h["rx_src"]))}
        res["envs"][env] = e
    # ---- E1 globally -------------------------------------------------------------------------------------------------------------------
    r = df["ratio_hav"].dropna()
    res["E1_haversine_over_local"] = {"n": int(len(r)), "p1": float(r.quantile(0.01)), "median": float(r.median()), "p99": float(r.quantile(0.99)),
                                      "min": float(r.min()), "max": float(r.max())}
    far = df[df["d"] > 2000]
    rf = far["ratio_hav"].dropna()
    res["E1_haversine_over_local_far_gt_2km"] = {"n": int(len(rf)), "min": float(rf.min()) if len(rf) else None, "max": float(rf.max()) if len(rf) else None}
    # ---- E4 link budget (assumptions written in the report) ----------------------------------------------------------------------------
    def fspl_db(d_m, f_hz=5.9e9):
        return 20 * np.log10(d_m) + 20 * np.log10(f_hz) - 147.55
    lb = {"assumptions": {"eirp_dbm": 33.0, "rx_antenna_gain_dbi_fixed_unit": 8.0, "rx_antenna_gain_dbi_vehicle": 3.0, "sensitivity_dbm_3mbps_10mhz": -95.0,
                          "source": "ETSI EN 302 663 (ITS-G5 G5A EIRP limit 33 dBm); IEEE 802.11p receiver minimum sensitivity -85 dBm (typical chips -95 to -98 dBm at 3 Mbit/s)"}}
    for env in res["envs"]:
        dmax = res["envs"][env]["distance_m_quantiles"]["1.0"]
        g_rx = lb["assumptions"]["rx_antenna_gain_dbi_fixed_unit"] if env == "Stationary" else lb["assumptions"]["rx_antenna_gain_dbi_vehicle"]
        rx_dbm = lb["assumptions"]["eirp_dbm"] + g_rx - fspl_db(dmax)
        lb[env] = {"d_max_m": dmax, "free_space_path_loss_db": float(fspl_db(dmax)), "received_power_dbm_free_space": float(rx_dbm),
                   "margin_to_minus95_dbm_db": float(rx_dbm + 95.0), "margin_to_minus85_dbm_db": float(rx_dbm + 85.0)}
    res["E4_link_budget"] = lb
    (OUT / "s3b_geometry.json").write_text(json.dumps(res, indent=1))
    L = ["# S3b geometry diagnosis (train + validation recordings; results/WP5/s3b_geometry.json)", ""]
    for env, e in res["envs"].items():
        L += [f"## {env}: {e['messages']} messages with ego pose, {e['senders']} senders, {e['recordings']} recordings",
              f"distance quantiles (m): " + ", ".join(f"q{k}={v:.0f}" for k, v in e["distance_m_quantiles"].items()),
              f"share beyond 300 m / 1 km / 2 km / 5 km: " + " / ".join(f"{100 * v:.1f}%" for v in e["share_beyond_m"].values()),
              f"implied ego speed p50 / p99 / max: " + " / ".join(f"{v:.1f}" for v in e["ego_speed_implied_p50_p99_max"]) + " m/s", "",
              "| distance bin | messages | recordings | senders | age_s p50 | age_s p99 | E2 violations | E2prime (generation-time dt, post-hoc) | haversine/local p1..p99 |", "|---|---|---|---|---|---|---|---|---|"]
        for b, v in e["by_bin"].items():
            hv = v["haversine_over_local_ratio_p1_p99"]
            L.append(f"| {b} | {v['messages']} | {v['recordings']} | {v['senders']} | " + (f"{v['age_s_p50']:.3f}" if v["age_s_p50"] is not None else "-") + " | " +
                     (f"{v['age_s_p99']:.2f}" if v["age_s_p99"] is not None else "-") + " | " +
                     (f"{100 * v['E2_violation_share']:.2f}% of {v['E2_pairs']}" if v["E2_violation_share"] is not None else "-") + " | " +
                     (f"{100 * v['E2prime_violation_share']:.2f}% of {v['E2prime_pairs']}" if v["E2prime_violation_share"] is not None else "-") + " | " +
                     (f"{hv[0]:.4f}..{hv[1]:.4f}" if hv else "-") + " |")
        f = e["far_gt_2km"]
        L += ["", f"messages beyond 2 km: {f['messages']} from {f['recordings']} recordings / {f['senders']} senders; largest single-recording share "
              + (f"{100 * f['top_recording_share']:.0f}%" if f["top_recording_share"] is not None else "-") + f"; by location: {f['by_location']}", "",
              "| location | messages | recordings | d p50 | d p99 | d max | ego pose source |", "|---|---|---|---|---|---|---|"]
        for loc, v in e["per_location"].items():
            L.append(f"| {loc} | {v['messages']} | {v['recordings']} | {v['d_p50']:.0f} | {v['d_p99']:.0f} | {v['d_max']:.0f} | {', '.join(v['rx_src'])} |")
        L.append("")
    L += ["## E4 link budget (free space, upper bound of the reachable range)", "```", json.dumps(lb, indent=1), "```", "",
          f"E1 haversine / local-frame distance: {res['E1_haversine_over_local']}; beyond 2 km: {res['E1_haversine_over_local_far_gt_2km']}"]
    (OUT / "s3b_geometry.md").write_text("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
