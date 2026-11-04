"""WP8 S7: verify the H31 files against locks/H31.json before they are scored (G1 / S1 rule: bytes and sha256). Reads (hashes) H31 files; run only after the freeze commit.
KITTI drives and comma Chunk_2 / Chunk_4: every file of the S1 manifest (results/WP8/S1/items/<id>.json: path, bytes, sha256) is re-hashed and the canonical manifest hash must equal the lock's sha256;
CAN (ROAD test + accelerator), network D10 test CSVs, VeReMi test files, V2AIX zip: file sha256 against the lock; V2AIX extracted recordings counted (674).
Output: results/WP8/S7/h31_verify.json (resumable per item: items already verified are kept). Run: python -u -W ignore tools/WP8_S7_verify.py"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S7_lib as S7

OUTF = S7.OUT / "h31_verify.json"


def manifest_ok(item_id, root, lock_sha):
    z = json.loads((S7.ROOT / "results" / "WP8" / "S1" / "items" / f"{item_id}.json").read_text())
    bad, rows = [], []
    for r in z["files"]:
        p = Path(root) / r["path"]
        if not p.exists() or p.stat().st_size != r["bytes"] or S7.sha256(p) != r["sha256"]:
            bad.append(r["path"])
        rows.append(r)
    rows.sort(key=lambda r: r["path"])
    canon = "".join(f"{r['path']}\t{r['bytes']}\t{r['sha256']}\n" for r in rows)
    man = hashlib.sha256(canon.encode("utf-8")).hexdigest()
    return {"files": len(rows), "bad_files": bad[:5], "n_bad": len(bad), "manifest_sha256": man, "lock_sha256": lock_sha, "ok": bool(not bad and man == lock_sha)}


def file_ok(rel, lock_sha, nbytes=None):
    p = (S7.ROOT / rel).resolve()
    if not p.exists():
        return {"path": rel, "ok": False, "error": "missing"}
    sha = S7.sha256(p)
    return {"path": rel, "ok": bool(sha == lock_sha and (nbytes is None or p.stat().st_size == nbytes)), "sha256": sha, "lock_sha256": lock_sha}


def main():
    res = json.loads(OUTF.read_text()) if OUTF.exists() else {}
    D = S7.h31()["domains"]
    S7.journal("S7", "verify H31 files against locks/H31.json: start", "tools/WP8_S7_verify.py; result results/WP8/S7/h31_verify.json")

    def do(key, fn):
        if key in res and res[key].get("ok"):
            print("skip", key, flush=True)
            return
        res[key] = fn()
        S7.write_json(res, OUTF)
        print(key, res[key].get("ok"), flush=True)
    for dr in D["kitti_vehicle_block"]["drives"]:
        name = dr["drive"]
        do("kitti/" + name, lambda name=name, dr=dr: manifest_ok(name, S7.D04B, dr["sha256"]))
    for side, chunk in (("rav4", "Chunk_2"), ("civic", "Chunk_4")):
        c = D["comma_vehicle_block"][side]
        do("comma/" + chunk, lambda chunk=chunk, c=c: manifest_ok(chunk, S7.DATA_EXTRA / "D22_comma2k19" / chunk, c["sha256"]))
    for x in D["can"]["reused"]["road_test"] + D["can"]["fresh"]["road_accelerator"]["files"]:
        do("can/" + Path(x["path"]).name, lambda x=x: file_ok(x["path"], x["sha256"], x["bytes"]))
    for x in D["network"]["d10_test"]["files"]:
        do("d10/" + Path(x["path"]).name, lambda x=x: file_ok(x["path"], x["sha256"], x["bytes"]))
    for x in D["v2x"]["reused"]["veremi_test"]["files"]:
        do("veremi/" + Path(x["path"]).name, lambda x=x: file_ok(x["path"], x["sha256"], x["bytes"]))
    z = D["v2x"]["fresh"]["v2aix"]["zip"]
    do("v2aix/zip", lambda: file_ok(z["path"], z["sha256"], z["bytes"]))
    ext = S7.DATA_EXTRA / "D13_v2aix" / "extracted_v31" / "json"
    n = sum(1 for _ in ext.rglob("*.json")) if ext.exists() else 0
    res["v2aix/extracted_recordings"] = {"count": n, "expected": len(D["v2x"]["fresh"]["v2aix"]["recordings"]), "ok": n == len(D["v2x"]["fresh"]["v2aix"]["recordings"])}
    res["all_ok"] = all(v.get("ok") for k, v in res.items() if isinstance(v, dict))
    S7.write_json(res, OUTF)
    S7.journal("S7", "verify H31 files: done", f"all_ok={res['all_ok']}, {len(res) - 1} items")


if __name__ == "__main__":
    main()
