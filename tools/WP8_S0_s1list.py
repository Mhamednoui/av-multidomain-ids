"""WP8 S0: write the S1 download / extraction list from locks/H31.json and locks/V31_val.json.

Purpose: one machine-readable list (URL, members kept, transfer and on-disk bytes, target folder) for S1.
Inputs: locks/H31.json, locks/V31_val.json. Output: results/WP8/S0/S1_download_list.json (+ printed totals).
Usage: python -I -u -W ignore tools/WP8_S0_s1list.py
"""
import json
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = json.load(open(os.path.join(ROOT, "locks", "H31.json")))["domains"]
V = json.load(open(os.path.join(ROOT, "locks", "V31_val.json")))["domains"]
KT = "../data_extra/D04b_kitti_raw_v31"

items = []
for d in H["kitti_vehicle_block"]["drives"]:
    items.append({"what": "KITTI " + d["drive"], "stratum": d["stratum"], "url": d["url"], "keep": d["keep"],
                  "member_list": d["member_list"], "n_members": d["n_members"], "transfer": d["bytes_transfer"],
                  "on_disk": d["bytes_on_disk"], "target": "%s/%s_sync/" % (KT, d["drive"]), "lock": "H31"})
for c in H["kitti_vehicle_block"]["calibration_zips"]:
    items.append({"what": "KITTI calib", "url": c["url"], "keep": "all", "transfer": 4100, "on_disk": 4100,
                  "target": KT + "/calib/", "lock": "H31"})
for car, lock, c in (("rav4", "H31", H["comma_vehicle_block"]["rav4"]), ("civic", "H31", H["comma_vehicle_block"]["civic"]),
                     ("civic", "V31_val", V["comma"]["civic_chunk3"])):
    items.append({"what": "comma2k19 Chunk_%d (%s)" % (c["chunk"], car), "url": c["url"], "keep": c["keep"],
                  "member_list": c["member_list"], "n_members": c["n_members"], "transfer": c["bytes_transfer"],
                  "on_disk": c["bytes_on_disk"], "target": "../data_extra/D22_comma2k19/Chunk_%d/" % c["chunk"],
                  "lock": lock})
v = H["v2x"]["fresh"]["v2aix"]
items.append({"what": "V2AIX 674 recordings (local extraction)", "url": v["zip"]["path"], "keep": "listed members",
              "n_members": len(v["recordings"]), "transfer": 0, "on_disk": sum(r["bytes"] for r in v["recordings"]),
              "target": "../data_extra/D13_v2aix/extracted_v31/", "lock": "H31"})
tot = {"transfer": sum(i["transfer"] for i in items), "on_disk": sum(i["on_disk"] for i in items)}
for s in ("same_day_2011_09_26", "other_day"):
    tot["kitti_" + s] = sum(i["on_disk"] for i in items if i.get("stratum") == s)
tot["free_now"] = shutil.disk_usage(ROOT).free
out = {"_note": "S1 list (WP8 S0). HTTP range requests through the zip directory, only the listed members; python -I; "
                "keep >= 15 GB free; verify bytes + CRC32 against member_list, then record sha256 in the locks.",
       "items": items, "totals": tot}
p = os.path.join(ROOT, "results", "WP8", "S0", "S1_download_list.json")
json.dump(out, open(p + ".tmp", "w"), indent=1)
os.replace(p + ".tmp", p)
print({k: round(x / 1e9, 2) for k, x in tot.items()})
