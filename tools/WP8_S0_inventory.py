"""WP8 S0: on-disk inventory of unscored material (read-only; no data is modified).

Purpose: list, per dataset already in ../data_extra, which files / groups exist and which of them
v3 never used (not in any v3 split), so H31 / V31_val can be defined from facts on disk.
Inputs: ../data_extra/* (read only, zip directories read with zipfile, nothing extracted),
        results/WP*/splits*.json.
Outputs: results/WP8/S0/inventory.json
Run: python -I -u -W ignore tools/WP8_S0_inventory.py   (from codes_v3/; -I because data is untrusted)
"""
import json
import os
import sys
import zipfile
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DX = os.path.join(os.path.dirname(ROOT), "data_extra")
OUT = os.path.join(ROOT, "results", "WP8", "S0")


def v2aix():
    z = zipfile.ZipFile(os.path.join(DX, "D13_v2aix", "v2aix_json.zip"))
    split = json.load(open(os.path.join(ROOT, "results", "WP5", "splits_v2aix.json")))
    used = set(split["train"]) | set(split["val"]) | set(split["test"])
    ext_root = os.path.join(DX, "D13_v2aix", "extracted")
    tops = Counter()
    scen = defaultdict(lambda: {"n": 0, "bytes": 0, "n_extracted": 0, "n_in_split": 0,
                                "n_unused": 0, "bytes_unused": 0})
    unused = []
    for i in z.infolist():
        if i.is_dir():
            continue
        p = i.filename
        parts = p.split("/")
        tops["/".join(parts[:2])] += 1
        if "/scenarios/" not in p or not p.endswith(".json"):
            continue
        j = parts.index("scenarios")
        stratum = "/".join(parts[1:j])
        rid = stratum + "/" + parts[-1][:-5]
        s = scen[stratum]
        s["n"] += 1
        s["bytes"] += i.file_size
        on_disk = os.path.exists(os.path.join(ext_root, *parts))
        s["n_extracted"] += on_disk
        if rid in used:
            s["n_in_split"] += 1
        elif not on_disk:
            s["n_unused"] += 1
            s["bytes_unused"] += i.file_size
            unused.append({"rid": rid, "member": p, "bytes": i.file_size, "crc32": "%08x" % i.CRC})
    return {"zip_members_by_top": dict(tops), "scenarios_by_stratum": dict(scen),
            "unused": sorted(unused, key=lambda r: r["rid"])}


def road():
    sp = json.load(open(os.path.join(ROOT, "results", "WP2", "splits_road.json")))["splits"]
    used = set(sum(sp.values(), []))
    rows = []
    for sub in ("ambient", "attacks"):
        d = os.path.join(DX, "road", "road", sub)
        for f in sorted(os.listdir(d)):
            if f.endswith(".log"):
                n = f[:-4]
                rows.append({"capture": n, "folder": sub, "bytes": os.path.getsize(os.path.join(d, f)),
                             "in_v3_split": n in used})
    return rows


def kitti():
    rows = []
    for base in (os.path.join(DX, "kitti_raw"), os.path.join(os.path.dirname(ROOT), "codes", "data", "Depth")):
        for f in sorted(os.listdir(base)):
            if f.startswith("2011_"):
                rows.append({"drive": f, "base": os.path.relpath(base, os.path.dirname(ROOT))})
    return rows


def comma():
    d = os.path.join(DX, "D22_comma2k19", "Chunk_1")
    return sorted(x for x in os.listdir(d) if os.path.isdir(os.path.join(d, x)))


def main():
    os.makedirs(OUT, exist_ok=True)
    inv = {"v2aix": v2aix(), "road": road(), "kitti_on_disk": kitti(), "comma_chunk1_routes": comma()}
    tmp = os.path.join(OUT, "inventory.json.tmp")
    json.dump(inv, open(tmp, "w"), indent=1)
    os.replace(tmp, os.path.join(OUT, "inventory.json"))
    v = inv["v2aix"]
    print("v2aix tops", v["zip_members_by_top"])
    for k, s in sorted(v["scenarios_by_stratum"].items()):
        print(k, s)
    print("v2aix unused", len(v["unused"]), sum(r["bytes"] for r in v["unused"]) / 1e9, "GB")
    print("road unused", [r["capture"] for r in inv["road"] if not r["in_v3_split"]])
    print("kitti", len(inv["kitti_on_disk"]), "comma routes", len(inv["comma_chunk1_routes"]))


if __name__ == "__main__":
    sys.exit(main())
