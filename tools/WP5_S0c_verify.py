"""WP5 S0c: parse all extracted V2AIX recordings, split by recording, verify fields / ranges / receiver distance. No detection.
Run: python -I -u -W ignore tools/WP5_S0c_verify.py  (from codes_v3). Writes results/WP5/{splits_v2aix.json,s0c_verify.json,s0c_tables.md}.
Per-message data stays in ../data_extra/D13_v2aix/cache (licence: never committed)."""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from v2x import v2aix
from v2x.schema import validate
from common.config import SEED

OUT = ROOT / "results" / "WP5"
t0 = time.time()
paths = v2aix.list_recordings()
print("recordings on disk:", len(paths), flush=True)
parts = []
for i, p in enumerate(paths):
    parts.append(v2aix.load_recording(p))
    if i % 100 == 0:
        print(i, round(time.time() - t0), "s", sum(len(x) for x in parts), "msgs", flush=True)
al = pd.concat([p for p in parts if len(p)], ignore_index=True)
recs_with = sorted(al["recording"].unique())
print("messages", len(al), "recordings with messages", len(recs_with), flush=True)
validate(al, sorted_per_track=True)

spl = v2aix.split_recordings(recs_with, seed=SEED)
sets = {k: set(v) for k, v in spl.items()}
assert not (sets["train"] & sets["val"]) and not (sets["train"] & sets["test"]) and not (sets["val"] & sets["test"])
al["split"] = al["recording"].map({r: k for k, v in spl.items() for r in v})
al["kind"] = al["recording"].str.split("/").str[0]
al["stratum"] = al["recording"].map(v2aix.stratum_of)
al["dist"] = np.hypot(al["x"] - al["rx_x"], al["y"] - al["rx_y"])
json.dump({"seed": SEED, "fractions": [0.6, 0.2, 0.2],
           "rule": "by recording, stratified by (Mobile|Stationary, location), strata with < 3 recordings pooled per kind",
           "n_recordings_extracted": len(paths), "n_recordings_with_cam": len(recs_with), **spl},
          open(OUT / "splits_v2aix.json", "w"), indent=1)


def q(a, ps=(0, 1, 50, 99, 100)):
    a = np.asarray(a, float)
    a = a[np.isfinite(a)]
    return {str(p): round(float(np.percentile(a, p)), 3) for p in ps} if len(a) else {}


res = {"messages": int(len(al)), "recordings": len(recs_with), "senders_unique_per_recording": int(al["sender"].nunique()),
       "dropped_note": "rows without finite t, x, y, speed are dropped by the adapter; duplicates (sender, t) dropped"}
res["split"] = {}
for s in ("train", "val", "test"):
    g = al[al["split"] == s]
    res["split"][s] = {"recordings": len(spl[s]), "messages": int(len(g)), "senders": int(g["sender"].nunique()),
                       "tracks": int(g["track"].nunique()), "mobile_msgs": int((g["kind"] == "Mobile").sum()),
                       "stationary_msgs": int((g["kind"] == "Stationary").sum())}
st = al.groupby("stratum").agg(recordings=("recording", "nunique"), messages=("msg_id", "size"), senders=("sender", "nunique"))
st = st.join(al.groupby(["stratum", "split"])["recording"].nunique().unstack(fill_value=0))
res["strata"] = json.loads(st.to_json(orient="index"))
fields = ["t", "x", "y", "speed", "vx", "vy", "heading", "acl", "yaw_rate", "pos_sigma", "spd_sigma", "acl_sigma", "rx_x", "rx_y", "age_s"]
res["completeness"] = {c: round(float(al[c].notna().mean()), 4) for c in fields}
res["completeness_by_kind"] = {k: {c: round(float(g[c].notna().mean()), 4) for c in ["acl", "yaw_rate", "rx_x", "heading", "pos_sigma"]}
                               for k, g in al.groupby("kind")}
res["station_type"] = {str(k): int(v) for k, v in al["station_type"].value_counts().items()}
res["rx_src"] = {k: int(v) for k, v in al["rx_src"].value_counts().items()}
res["ranges"] = {"speed_mps": q(al["speed"]), "heading_rad": q(al["heading"]), "acl_mps2": q(al["acl"]), "yaw_rate_rad_s": q(al["yaw_rate"]),
                 "lat": q(al["lat"]), "lon": q(al["lon"]), "age_s": q(al["age_s"], (50, 90, 99, 100)), "pos_sigma_m": q(al["pos_sigma"])}
res["distance_to_ego_m"] = {k: q(g["dist"], (0, 1, 5, 25, 50, 75, 95, 99, 100)) for k, g in al.groupby("kind")}
res["distance_by_stratum_p50_p99_max"] = {k: [round(float(np.nanpercentile(g["dist"], p)), 1) for p in (50, 99, 100)]
                                          for k, g in al.groupby("stratum") if g["dist"].notna().any()}
res["own_cam_check"] = {"share_msgs_within_3m_of_ego": round(float((al["dist"] < 3).mean()), 5),
                        "share_msgs_within_10m": round(float((al["dist"] < 10).mean()), 5),
                        "recordings_with_any_msg_within_3m": int(al[al["dist"] < 3]["recording"].nunique())}
res["rx_nan_share"] = round(float(al["rx_x"].isna().mean()), 5)
rate = al.groupby("track")["t"].apply(lambda s: np.median(np.diff(s.to_numpy())) if len(s) > 2 else np.nan)
res["median_dt_per_track_s"] = q(rate, (5, 25, 50, 75, 95))
res["track_lengths_msgs"] = q(al.groupby("track").size(), (0, 25, 50, 75, 100))
g = al.sort_values(["track", "t"])
dd = np.hypot(g["x"].diff(), g["y"].diff())
dtt = g["t"].diff()
ok = (g["track"] == g["track"].shift()) & (dtt > 0)
v = (dd / dtt)[ok]
res["implied_speed_mps"] = q(v, (50, 99, 99.9, 100))
res["speed_vs_implied_absdiff_p50_p99_mps"] = [round(float(np.nanpercentile(np.abs((v - g["speed"][ok]).to_numpy()), p)), 2) for p in (50, 99)]
res["runtime_s"] = round(time.time() - t0, 1)
json.dump(res, open(OUT / "s0c_verify.json", "w"), indent=1)

L = ["# WP5 S0c V2AIX verification (generated by tools/WP5_S0c_verify.py from results/WP5/s0c_verify.json)", "",
     f"Messages {res['messages']}, recordings with CAM {res['recordings']} of {len(paths)} extracted, "
     f"unique (recording, station) senders {res['senders_unique_per_recording']}.", "",
     "## Per split", "", "| split | recordings | messages | senders | tracks | Mobile msgs | Stationary msgs |", "|---|---|---|---|---|---|---|"]
for s, d in res["split"].items():
    L.append(f"| {s} | {d['recordings']} | {d['messages']} | {d['senders']} | {d['tracks']} | {d['mobile_msgs']} | {d['stationary_msgs']} |")
L += ["", "## Per stratum", "", "| stratum | recordings | messages | senders | train | val | test |", "|---|---|---|---|---|---|---|"]
for k, d in res["strata"].items():
    L.append(f"| {k} | {d['recordings']} | {d['messages']} | {d['senders']} | {d.get('train', 0)} | {d.get('val', 0)} | {d.get('test', 0)} |")
L += ["", "## Field completeness (share of messages with a finite value)", "", "| field | share |", "|---|---|"]
L += [f"| {k} | {v} |" for k, v in res["completeness"].items()]
L += ["", "## Ranges (percentiles 0 / 1 / 50 / 99 / 100 unless the keys say otherwise)", ""]
L += [f"- {k}: {v}" for k, v in res["ranges"].items()]
L += ["", "## Sender-to-ego distance (m), percentiles", ""]
L += [f"- {k}: {v}" for k, v in res["distance_to_ego_m"].items()]
L += [f"- by stratum [p50, p99, max]: {res['distance_by_stratum_p50_p99_max']}", "",
      f"Own-CAM check: {res['own_cam_check']}", "", f"rx NaN share: {res['rx_nan_share']}; rx source: {res['rx_src']}; station types: {res['station_type']}", "",
      f"Median dt per track (s), percentiles 5/25/50/75/95: {res['median_dt_per_track_s']}", "",
      f"Implied speed from consecutive positions (m/s): {res['implied_speed_mps']}; |reported - implied| p50, p99 = {res['speed_vs_implied_absdiff_p50_p99_mps']}"]
open(OUT / "s0c_tables.md", "w").write("\n".join(L) + "\n")
print("done", res["runtime_s"], "s")
