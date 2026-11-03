"""WP8 S1: check the downloaded H31 / V31_val material against the S1 list and the locks, and fill the sha256 fields.

Usage (from codes_v3/): python -I -u -W ignore tools/WP8_S1_locks.py [--write]
Reads: results/WP8/S1/items/<id>.json (manifests written by tools/WP8_S1_fetch.py), locks/H31.json,
locks/V31_val.json, results/WP8/S0/S1_download_list.json.
Checks per KITTI drive: file count, bytes, velodyne scan count and oxts count vs the lock. Per comma chunk: routes
and segments vs the lock, route set equal to the lock. Civic decision (decision 3): are the V31_val Civic routes
on disk, and do they not overlap H31 routes? Writes results/WP8/S1/S1_check.json (committed).
--write fills the sha256 fields (drive = manifest_sha256; comma chunk = manifest_sha256) only when every check passed.
Stops (exit 1) without writing if any check fails.
"""
import datetime
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT.parent / "data_extra"
ITEMS = ROOT / "results" / "WP8" / "S1" / "items"
OUT = ROOT / "results" / "WP8" / "S1" / "S1_check.json"
LIST = ROOT / "results" / "WP8" / "S0" / "S1_download_list.json"
H31 = ROOT / "locks" / "H31.json"
V31 = ROOT / "locks" / "V31_val.json"
JOURNAL = ROOT / "notes" / "WP8_journal.md"
CIVIC_DONGLE = "99c94dc769b5d96e"


def journal(what, state):
    line = f"{datetime.datetime.now().astimezone().isoformat(timespec='seconds')} | S1 | {what} | {state}"
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)


def manifest(item_id):
    p = ITEMS / f"{item_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def norm_route(r):
    return r.replace("|", "_")


def check_kitti(drive, lock_drive, list_item, problems):
    m = manifest(drive)
    if m is None:
        problems.append(f"{drive}: no manifest (not downloaded)")
        return None
    files = m["files"]
    n = len(files)
    total = sum(f["bytes"] for f in files)
    velo = sum(1 for f in files if "/velodyne_points/data/" in f["path"] and f["path"].endswith(".bin"))
    oxts = sum(1 for f in files if "/oxts/data/" in f["path"] and f["path"].endswith(".txt"))
    res = {"drive": drive, "files": n, "bytes": total, "velodyne_bins": velo, "oxts_txt": oxts,
           "manifest_sha256": m["manifest_sha256"]}
    if n != lock_drive["n_members"]:
        problems.append(f"{drive}: files {n} != lock {lock_drive['n_members']}")
    if total != list_item["on_disk"]:
        problems.append(f"{drive}: bytes {total} != S1 list {list_item['on_disk']}")
    if velo != lock_drive["n_scans"]:
        problems.append(f"{drive}: velodyne scans {velo} != lock {lock_drive['n_scans']}")
    if oxts != lock_drive["n_oxts"]:
        problems.append(f"{drive}: oxts {oxts} != lock {lock_drive['n_oxts']}")
    return res


def check_comma(chunk, routes_lock, n_seg_lock, list_item, problems):
    m = manifest(chunk)
    if m is None:
        problems.append(f"{chunk}: no manifest (not downloaded)")
        return None
    files = m["files"]
    routes = {f["path"].split("/")[0] for f in files}
    segs = {tuple(f["path"].split("/")[:2]) for f in files}
    total = sum(f["bytes"] for f in files)
    res = {"chunk": chunk, "files": len(files), "bytes": total, "routes": len(routes), "segments": len(segs),
           "manifest_sha256": m["manifest_sha256"], "http_bytes": m.get("http_bytes")}
    want = {norm_route(r) for r in routes_lock}
    if routes != want:
        problems.append(f"{chunk}: route set differs from lock ({len(routes)} vs {len(want)})")
    if len(routes_lock) != len(routes):
        problems.append(f"{chunk}: routes {len(routes)} != lock {len(routes_lock)}")
    if len(segs) != n_seg_lock:
        problems.append(f"{chunk}: segments {len(segs)} != lock {n_seg_lock}")
    if total != list_item["on_disk"]:
        problems.append(f"{chunk}: bytes {total} != S1 list {list_item['on_disk']}")
    return res


def main():
    write = "--write" in sys.argv[1:]
    lst = json.loads(LIST.read_text(encoding="utf-8"))
    by_what = {}
    for it in lst["items"]:
        by_what.setdefault(it["what"], []).append(it)
    h31 = json.loads(H31.read_text(encoding="utf-8"))
    v31 = json.loads(V31.read_text(encoding="utf-8"))
    problems, results = [], {"kitti": [], "comma": [], "civic_decision": None, "v2aix": None}
    kitti_list = {it["url"].split("/")[-2]: it for it in lst["items"] if it["what"].startswith("KITTI 2011_")}
    sha_fill = {}

    for dr in h31["domains"]["kitti_vehicle_block"]["drives"]:
        drive = dr["drive"]
        r = check_kitti(drive, dr, kitti_list[drive], problems)
        if r:
            results["kitti"].append(r)
            sha_fill[("drive", drive)] = r["manifest_sha256"]

    comma_specs = {
        "Chunk_2": (h31["domains"]["comma_vehicle_block"]["rav4"], "rav4"),
        "Chunk_4": (h31["domains"]["comma_vehicle_block"]["civic"], "civic"),
        "Chunk_3": (v31["domains"]["comma"]["civic_chunk3"], "civic_chunk3"),
    }
    comma_list = {it["what"].split()[1]: it for it in lst["items"] if it["what"].startswith("comma2k19 Chunk_")}
    for chunk, (spec, key) in comma_specs.items():
        r = check_comma(chunk, spec["routes"], spec["n_segments"], comma_list[chunk], problems)
        if r:
            results["comma"].append(r)
            sha_fill[("comma", key)] = r["manifest_sha256"]

    # Decision 3 (Civic): is any comma Civic route in V31_val (on disk), and do H31 Civic routes avoid V31_val?
    civic_v31 = v31["domains"]["comma"]["civic_chunk3"]["routes"]
    civic_h31 = h31["domains"]["comma_vehicle_block"]["civic"]["routes"]
    m3 = manifest("Chunk_3")
    on_disk3 = {f["path"].split("/")[0] for f in m3["files"]} if m3 else set()
    v31_on_disk = [r for r in civic_v31 if norm_route(r) in on_disk3]
    overlap = set(civic_h31) & set(civic_v31)
    dongles = {r.split("|")[0] for r in civic_v31}
    decision = {
        "v31_val_civic_routes": len(civic_v31),
        "v31_val_civic_routes_on_disk": len(v31_on_disk),
        "v31_val_civic_dongles": sorted(dongles),
        "h31_civic_routes": len(civic_h31),
        "overlap_h31_v31_routes": sorted(overlap),
        "any_civic_route_in_v31_val": len(civic_v31) > 0 and len(v31_on_disk) == len(civic_v31),
        "dongle_is_civic": dongles == {CIVIC_DONGLE},
    }
    decision["outcome"] = ("no move: V31_val already holds Civic routes (Chunk_3, dongle " + CIVIC_DONGLE + ")"
                           if decision["any_civic_route_in_v31_val"] and not overlap and decision["dongle_is_civic"]
                           else "MOVE NEEDED (seeded 20%, seed 42) - not performed")
    if overlap:
        problems.append(f"H31 and V31_val share Civic routes: {sorted(overlap)}")
    if not decision["any_civic_route_in_v31_val"]:
        problems.append("V31_val Civic routes not all on disk")
    results["civic_decision"] = decision

    # V2AIX: the H31 recordings extracted to the data folder (manifest is not committed).
    v2 = DATA / "D13_v2aix" / "extracted_v31" / "_manifest_v31.json"
    if v2.exists():
        v2m = json.loads(v2.read_text(encoding="utf-8"))
        results["v2aix"] = {"recordings": v2m["n_files"], "members_sha256_ok": v2m["members_sha256_ok"]}
        if v2m["n_files"] != 674:
            problems.append(f"V2AIX: {v2m['n_files']} recordings != 674")
    else:
        problems.append("V2AIX: extraction manifest missing")

    disk = shutil.disk_usage(DATA)
    results["free_gb_now"] = round(disk.free / 1e9, 2)
    results["problems"] = problems
    results["calibration_zips"] = "not checked: stopped on size (list 4100 B, server 4068/4071/4073/4075 B)"
    results["date"] = datetime.date.today().isoformat()
    results["ok"] = not problems
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(json.dumps({k: results[k] for k in ("free_gb_now", "problems", "civic_decision", "v2aix")}, indent=1))
    print("kitti drives checked:", len(results["kitti"]), "comma chunks checked:", len(results["comma"]))
    if problems:
        print("CHECK FAILED: nothing written to locks")
        sys.exit(1)
    if write:
        for dr in h31["domains"]["kitti_vehicle_block"]["drives"]:
            dr["sha256"] = sha_fill[("drive", dr["drive"])]
            dr["sha256_note"] = ("sha256 of the per-file manifest results/WP8/S1/items/<drive>.json (lines "
                                 "path<TAB>bytes<TAB>file sha256, sorted); files: velodyne_points + oxts, "
                                 "bytes and CRC32 checked against the member list")
        h31["domains"]["comma_vehicle_block"]["rav4"]["sha256"] = sha_fill[("comma", "rav4")]
        h31["domains"]["comma_vehicle_block"]["civic"]["sha256"] = sha_fill[("comma", "civic")]
        for k in ("rav4", "civic"):
            h31["domains"]["comma_vehicle_block"][k]["sha256_note"] = (
                "sha256 of the per-file manifest results/WP8/S1/items/Chunk_<k>.json (same rule as the KITTI drives)")
        v31["domains"]["comma"]["civic_chunk3"]["sha256"] = sha_fill[("comma", "civic_chunk3")]
        v31["domains"]["comma"]["civic_chunk3"]["sha256_note"] = (
            "sha256 of the per-file manifest results/WP8/S1/items/Chunk_3.json (same rule as the KITTI drives)")
        # same layout as the committed locks: 1-space indent, LF line endings
        for path, obj in ((H31, h31), (V31, v31)):
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(obj, indent=1, ensure_ascii=False) + "\n")
        journal("locks filled", "H31.json drives + rav4 + civic sha256; V31_val civic_chunk3 sha256; "
                                "calibration zips left null (stopped)")


if __name__ == "__main__":
    main()
