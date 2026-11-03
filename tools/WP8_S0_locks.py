"""WP8 S0: write locks/H31.json (fresh / re-used hold-out of v3.1) and locks/V31_val.json (v3.1 validation).

Purpose: freeze, before any v3.1 result, which material is the v3.1 hold-out (scored once, in S7) and
which is validation (all S2-S6 choices). Files already on disk get size + sha256 (V2AIX hold-out
recordings: sha256 of each zip member, streamed from the zip, nothing extracted); files still to
download get URL + expected sizes + member CRC32 (from results/WP8/S0/remote/*.json), sha256 = null
until S1. Data is untrusted: run with python -I; nothing in the data folders is written or executed.
Inputs: ../data_extra, ../codes/data (read only), results/WP*/splits*.json, results/WP8/S0/{inventory,remote}.
Outputs: locks/H31.json, locks/V31_val.json, results/WP8/S0/sha256_cache.json (resumable hash cache).
Usage: python -I -u -W ignore tools/WP8_S0_locks.py
"""
import hashlib
import json
import os
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PFE = os.path.dirname(ROOT)
DX = os.path.join(PFE, "data_extra")
S0 = os.path.join(ROOT, "results", "WP8", "S0")
CACHE = os.path.join(S0, "sha256_cache.json")
KBASE = "https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data"

# ---- pre-registered group choices (S0, 2026-11-03; reasons in notes/WP8_v31.md) ----
K_H31_SAMEDAY = {"0009": "city", "0056": "city", "0084": "city", "0093": "city",
                 "0023": "residential", "0061": "residential", "0064": "residential",
                 "0032": "road", "0101": "road"}
K_H31_OTHERDAY = {"2011_09_29_drive_0004": "road", "2011_09_29_drive_0026": "city",
                  "2011_09_30_drive_0016": "road", "2011_10_03_drive_0047": "road"}
CALIB_DAYS = ["2011_09_26", "2011_09_29", "2011_09_30", "2011_10_03"]
COMMA_H31 = {"rav4": 2, "civic": 4}          # chunk numbers; Civic Chunk_3 = V31_val (calibration only)
COMMA_VAL_CIVIC = 3
ROAD_ACCEL_H31 = ["accelerator_attack_drive_2", "accelerator_attack_reverse_2"]
ROAD_ACCEL_VAL = ["accelerator_attack_drive_1", "accelerator_attack_reverse_1"]
OTIDS = ["Attack_free_dataset.txt", "DoS_attack_dataset.txt", "Fuzzy_attack_dataset.txt",
         "Impersonation_attack_dataset.txt"]
OTIDS_VAL_FRACTION = 0.30                    # first 30% (time order) of Attack_free = per-deployment fit


def rel(p):
    return os.path.relpath(p, ROOT).replace("\\", "/")


def load_cache():
    return json.load(open(CACHE)) if os.path.exists(CACHE) else {}


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)


def sha_file(path, cache):
    st = os.stat(path)
    key = rel(path)
    c = cache.get(key)
    if c and c["bytes"] == st.st_size and c["mtime"] == int(st.st_mtime):
        return c
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    c = {"bytes": st.st_size, "mtime": int(st.st_mtime), "sha256": h.hexdigest()}
    cache[key] = c
    save_json(CACHE, cache)
    print("sha", key, st.st_size, flush=True)
    return c


def fentry(path, cache, **kw):
    c = sha_file(path, cache)
    return dict(path=rel(path), bytes=c["bytes"], sha256=c["sha256"], **kw)


def fsummary(path):
    """Size-only lock for big folders (v3 KITTI drives as validation): file count and total bytes."""
    n, b = 0, 0
    for dp, _, fs in os.walk(path):
        for f in fs:
            n += 1
            b += os.path.getsize(os.path.join(dp, f))
    return {"path": rel(path), "n_files": n, "bytes": b}


def remote(name):
    p = os.path.join(S0, "remote", name + ".json")
    d = json.load(open(p))
    return d, p


def kitti_remote(drive, scene, stratum, cache):
    d, p = remote(drive)
    return {"drive": drive, "scene": scene, "stratum": stratum, "url": d["url"], "zip_bytes": d["zip_bytes"],
            "keep": "velodyne_points/ + oxts/ members only (HTTP range requests)",
            "n_scans": d["n_scans"], "n_oxts": d["n_oxts"], "n_members": d["n_members_kept"],
            "bytes_on_disk": d["kept_uncompressed"], "bytes_transfer": d["kept_compressed"],
            "member_list": rel(p), "member_list_sha256": sha_file(p, cache)["sha256"],
            "sha256": None, "sha256_note": "per-member sha256 filled in S1 (CRC32 per member in member_list)"}


def comma_remote(k, car, role, cache):
    d, p = remote("comma_Chunk_%d" % k)
    return {"chunk": k, "car": car, "url": d["url"], "zip_bytes": d["zip_bytes"],
            "keep": "processed_log/CAN, processed_log/GNSS, processed_log/IMU, global_pose (as WP6 S1)",
            "routes": sorted(d["routes"]), "n_routes": len(d["routes"]),
            "n_segments": sum(v["n_segments"] for v in d["routes"].values()),
            "n_members": len(d["members"]),
            "bytes_on_disk": sum(v["kept_uncompressed"] for v in d["routes"].values()),
            "bytes_transfer": sum(v["kept_compressed"] for v in d["routes"].values()),
            "member_list": rel(p), "member_list_sha256": sha_file(p, cache)["sha256"],
            "role": role, "sha256": None, "sha256_note": "per-member sha256 filled in S1"}


def v2aix_h31(cache):
    inv = json.load(open(os.path.join(S0, "inventory.json")))["v2aix"]["unused"]
    zp = os.path.join(DX, "D13_v2aix", "v2aix_json.zip")
    zc = sha_file(zp, cache)
    z = zipfile.ZipFile(zp)
    out = []
    for r in inv:
        key = "zipmember:" + r["member"]
        c = cache.get(key)
        if not c:
            h = hashlib.sha256()
            with z.open(r["member"]) as f:
                for b in iter(lambda: f.read(1 << 22), b""):
                    h.update(b)
            c = {"bytes": r["bytes"], "sha256": h.hexdigest()}
            cache[key] = c
            if len(cache) % 50 == 0:
                save_json(CACHE, cache)
        out.append({"rid": r["rid"], "member": r["member"], "bytes": r["bytes"], "crc32": r["crc32"],
                    "sha256": c["sha256"]})
    save_json(CACHE, cache)
    return {"zip": dict(path=rel(zp), bytes=zc["bytes"], sha256=zc["sha256"]), "recordings": out}


def splits():
    j = lambda *p: json.load(open(os.path.join(ROOT, "results", *p)))
    return {"wp1": j("WP1", "splits.json"), "road": j("WP2", "splits_road.json")["splits"],
            "d11": j("WP2", "splits_d11.json")["splits"], "v2aix": j("WP5", "splits_v2aix.json")}


def d11_files(sp, part):
    base = os.path.join(DX, "D11_can-train-and-test", "can-train-and-test")
    out = []
    for s, parts in sorted(sp.items()):
        for k, lst in parts.items():
            if (part == "test" and k.startswith("test_")) or k == part:
                out += [os.path.join(base, x + ".csv") for x in lst]
    return out


def road_file(name):
    for sub in ("ambient", "attacks"):
        p = os.path.join(DX, "road", "road", sub, name + ".log")
        if os.path.exists(p):
            return p
    raise FileNotFoundError(name)


def main():
    t0 = time.time()
    cache = load_cache()
    sp = splits()
    kd = sp["wp1"]["kitti_drives"]
    comma_routes = sorted(os.listdir(os.path.join(DX, "D22_comma2k19", "Chunk_1")))
    comma_routes = [r for r in comma_routes if os.path.isdir(os.path.join(DX, "D22_comma2k19", "Chunk_1", r))]
    n = len(comma_routes)
    ntr, nva = int(round(0.6 * n)), max(1, int(round(0.2 * n)))
    c1 = {"train": comma_routes[:ntr], "val": comma_routes[ntr:ntr + nva], "test": comma_routes[ntr + nva:]}
    ch = os.path.join(PFE, "codes", "data")

    h31 = {
        "_note": "v3.1 hold-out H31 (WP8 S0, 2026-11-03). Scored ONCE, in S7, by v3 (frozen) and v3.1 side by side. "
                 "Nothing listed here may be read by any S2-S6 fit, choice, threshold or diagnostic. "
                 "status fresh = v3 never scored it; reused = v3 test material, S7 number labelled 're-used test, exposure n+1'. "
                 "sha256 null = still to download (S1 fills it and must match bytes / CRC32 given here).",
        "created": "2026-11-03", "step": "WP8.S0",
        "domains": {}}
    D = h31["domains"]
    D["kitti_vehicle_block"] = {
        "used_by": ["gps", "lidar", "cross", "system K"], "status": "fresh", "group": "drive",
        "licence": "CC BY-NC-SA 3.0 (KITTI raw)",
        "strata": {"same_day_2011_09_26": "primary (same day / calibration as v3 train)",
                   "other_day": "secondary, reported separately (new calibration day, same car / sensors)"},
        "drives": [kitti_remote("2011_09_26_drive_" + d, s, "same_day_2011_09_26", cache)
                   for d, s in sorted(K_H31_SAMEDAY.items())]
                  + [kitti_remote(d, s, "other_day", cache) for d, s in sorted(K_H31_OTHERDAY.items())],
        "calibration_zips": [{"url": "%s/%s_calib.zip" % (KBASE, c), "sha256": None} for c in CALIB_DAYS],
        "attack_seeds": "GPS runs: gps/stream.py generator, 10 phase offsets per drive, seed [31, int(drive)]; "
                        "LiDAR: lidar.phantom (single_return=True), PointDrop, IntensitySpoof, episodes, seed [31, 3, int(drive)]; "
                        "cross / system composites seed [31, 7, int(drive), ord(family[0])]"}
    D["comma_vehicle_block"] = {
        "used_by": ["gps (GNSS)", "cross", "system C"], "status": "fresh", "group": "route", "licence": "MIT",
        "rav4": comma_remote(COMMA_H31["rav4"], "Toyota RAV4 (dongle b0c9d2329ad1606b, same car as v3 Chunk_1)",
                             "H31 primary C (routes after every v3 route in time)", cache),
        "civic": comma_remote(COMMA_H31["civic"], "Honda Civic (dongle 99c94dc769b5d96e, car never seen by v3)",
                              "H31 cross-vehicle stratum (zero-shot primary; per-deployment calibrated variant from V31_val Chunk_3)",
                              cache),
        "note": "Civic CAN wheel speed is not at 0xAA (Toyota decoder in crossdomain/comma.py): the Civic decoder must be written "
                "on V31_val Chunk_3 only; if it cannot be verified there, the Civic stratum reports GNSS / IMU / CAN-speed edges only."}
    D["can"] = {
        "status": "mixed", "group": "capture",
        "reused": {"exposure_after_S7": {"road_test": 7, "carhacking_test_blocks": "4 (at least)", "d11_test": "5 (at least)"},
                   "road_test": [fentry(road_file(x), cache) for x in sp["road"]["test"]],
                   "carhacking": "test blocks of results/WP2/splits_carhacking.json in "
                                 + ", ".join(fentry(os.path.join(ch, f), cache)["path"] + " sha256 " + fentry(os.path.join(ch, f), cache)["sha256"][:16]
                                             for f in ("DoS_dataset.csv", "Fuzzy_dataset.csv", "RPM_dataset.csv", "gear_dataset.csv")),
                   "d11_test": [fentry(p, cache) for p in d11_files(sp["d11"], "test")]},
        "fresh": {
            "road_accelerator": {"files": [fentry(road_file(x), cache) for x in ROAD_ACCEL_H31],
                                 "metric": "capture level (no injected frames, compromised-ECU state for the whole capture)"},
            "carhacking_normal_run": {"files": [fentry(os.path.join(ch, "normal_run_data.txt"), cache)],
                                      "metric": "clean false alarms on the Car-Hacking vehicle (Hyundai YF Sonata), never scored by v3"},
            "otids_kia_soul": {"files": [fentry(os.path.join(ch, f), cache) for f in OTIDS],
                               "hold_out_part": "Attack_free: frames after the first %d%% in time order; DoS / Fuzzy / Impersonation: whole captures"
                                                % int(OTIDS_VAL_FRACTION * 100),
                               "metric": "capture level and clean FA; per-frame labels are NOT available (derived labels would be circular)",
                               "licence": "HCRL dataset terms (research use, cite Lee et al. 2017 OTIDS); on disk since v1, not in DATASETS.md yet"}},
        "not_usable": {"CICIoV2024 (../codes/data/CICIoV2024)": "no timestamps: v3 CAN windows cannot be built"}}
    D["network"] = {
        "status": "reused", "group": "time block (10 min) inside the v3 time split",
        "exposure_after_S7": {"d10_test": 7, "d23": "4 (at least)"},
        "d10_test": {"split": "split == 'test' of the WP4 S1 time split (stage stream, 585,951 flows)",
                     "files": [fentry(os.path.join(DX, "D10_cicids2017_generated_flows", "extracted", "TrafficLabelling", f), cache)
                               for f in sorted(os.listdir(os.path.join(DX, "D10_cicids2017_generated_flows", "extracted", "TrafficLabelling")))]},
        "d23": {"split": "whole dataset (external zero-shot test, as v3)",
                "files": [fentry(os.path.join(DX, "D23_cse-cic-ids2018", "raw", f), cache)
                          for f in sorted(os.listdir(os.path.join(DX, "D23_cse-cic-ids2018", "raw")))]},
        "why_no_fresh": "no unscored CIC-format traffic with IPs / ports / timestamps on disk or downloadable without login "
                        "(UNB site restricted 2026-10-21; CSE-CIC-IDS2018 CSVs without IPs except Tue-20-02; re-extractions of the "
                        "same pcaps, e.g. Engelen et al. 2021, are the same traffic, not fresh)"}
    D["v2x"] = {
        "status": "mixed",
        "fresh": {"v2aix": dict(v2aix_h31(cache), group="recording (as v3; 672 of 674 share site + day with a v3 train recording)",
                                licence="non-commercial research, no redistribution: never commit data or per-message derived files",
                                metric="genuine FA per message / per receiver-hour + injected attacks (v2x/v2aix_inject.py, seed [31, recording index])")},
        "reused": {"veremi_test": {"split": "test of results/WP5/splits_veremi.json (10 time blocks)", "exposure_after_S7": 3,
                                   "files": [fentry(os.path.join(DX, "D12_veremi_extension", "mixalldata_clean.csv"), cache)]},
                   "tampa_test": {"split": "test of results/WP5/splits_tampa_v2.json (3 vehicles, illustration)",
                                  "files": [fentry(os.path.join(DX, "D14_tampa_bsm", "bsm_sample.csv"), cache)]}}}
    D["system_simulation"] = {
        "status": "partially fresh",
        "K": "vehicle block (GPS, IMU, LiDAR, simulated CAN wheel speed) from kitti_vehicle_block (fresh); CAN stream from ROAD test, "
             "network from D10 test, V2X from VeReMi test ego view (re-used, exposure n+1); M3 construction (tools/WP7_S2_*), "
             "16 clean timelines, every episode, seeds [31, ...]",
        "C": "comma RAV4 Chunk_2 routes (fresh) with the same re-used CAN / NET / V2X streams; Civic Chunk_4 = separate C2 rows",
        "label": "'vehicle block fresh, CAN / network / V2X streams re-used test (exposure n+1)'"}

    val = {
        "_note": "v3.1 validation V31_val (WP8 S0, 2026-11-03): every S2-S6 fit, threshold, hyper-parameter, combiner and tie-break "
                 "is decided on this material only (plus v3 train). v3 TEST material whose domain has a fresh H31 moves here "
                 "(it is no longer an independent test of anything); v3 test material that stays in H31 (CAN, network, VeReMi, Tampa) "
                 "is NOT validation.",
        "created": "2026-11-03", "step": "WP8.S0", "domains": {}}
    V = val["domains"]
    V["kitti_vehicle_block"] = {
        "group": "drive", "train": kd["train"], "val": sorted(kd["val"] + kd["test"]),
        "from_v3": {"v3_val": kd["val"], "v3_test": kd["test"]},
        "drives": [fsummary(os.path.join(DX, "kitti_raw", "2011_09_26_drive_%s_sync" % d))
                   if os.path.exists(os.path.join(DX, "kitti_raw", "2011_09_26_drive_%s_sync" % d))
                   else fsummary(os.path.join(PFE, "codes", "data", "Depth", "2011_09_26_drive_%s_sync" % d))
                   for d in sorted(kd["val"] + kd["test"])]}
    V["comma"] = {"group": "route", "rav4_chunk1": {"train": c1["train"], "val": c1["val"] + c1["test"],
                                                   "from_v3": {"v3_val": c1["val"], "v3_test": c1["test"]}},
                  "civic_chunk3": comma_remote(COMMA_VAL_CIVIC, "Honda Civic (99c94dc769b5d96e)",
                                               "clean calibration / decoder development for the Civic stratum only (labels never used)",
                                               cache)}
    V["can"] = {"group": "capture", "road_val": [fentry(road_file(x), cache) for x in sp["road"]["val"]],
                "road_loco": "the v3 LOCO clean folds of the ROAD train captures (M1-CAN)",
                "road_accelerator": [fentry(road_file(x), cache) for x in ROAD_ACCEL_VAL],
                "carhacking": "val blocks of results/WP2/splits_carhacking.json",
                "d11_val": [fentry(p, cache) for p in d11_files(sp["d11"], "val")],
                "otids_kia_soul": {"part": "Attack_free_dataset.txt, first %d%% of frames in time order (clean, per-deployment fit)"
                                           % int(OTIDS_VAL_FRACTION * 100),
                                   "file": fentry(os.path.join(ch, "Attack_free_dataset.txt"), cache)}}
    V["network"] = {"group": "10-min time block", "d10_val": "split == 'val' of the WP4 S1 time split (same CSV files as H31 d10_test)",
                    "d23": "none (D23 is entirely H31)"}
    V["v2x"] = {"group": "recording / time block",
                "v2aix": {"val": sorted(sp["v2aix"]["val"] + sp["v2aix"]["test"]), "train": "train of results/WP5/splits_v2aix.json",
                          "from_v3": {"n_v3_val": len(sp["v2aix"]["val"]), "n_v3_test": len(sp["v2aix"]["test"])}},
                "veremi": "val of results/WP5/splits_veremi.json", "tampa": "val of results/WP5/splits_tampa_v2.json"}
    V["system_simulation"] = {"K": "vehicle block on the 10 V31_val KITTI drives; CAN / NET / V2X streams from their VAL splits only",
                              "C": "RAV4 Chunk_1 val + test routes (8); CAN / NET / V2X from VAL splits",
                              "clean_timelines": "16 K + 16 C, M3 construction, seeds [31, 100 + i]"}
    save_json(os.path.join(ROOT, "locks", "H31.json"), h31)
    save_json(os.path.join(ROOT, "locks", "V31_val.json"), val)
    print("done in %.0f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
