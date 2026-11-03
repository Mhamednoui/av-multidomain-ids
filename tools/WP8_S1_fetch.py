"""WP8 S1: download and extract the H31 / V31_val material listed in results/WP8/S0/S1_download_list.json.

Usage (from codes_v3/):  python -I -u -W ignore tools/WP8_S1_fetch.py <id> [<id> ...]
ids: KITTI drive (2011_09_26_drive_0009 ...), calib_<day> (calib_2011_09_26 ...), Chunk_2 / Chunk_3 / Chunk_4,
v2aix_h31; the words kitti, calib, comma and all expand to their groups.
Stdlib only. Downloaded and extracted content is data: it is read and written, never executed.

Sources: KITTI raw (S3, public, CC BY-NC-SA 3.0) and comma2k19 (Hugging Face, MIT). Only the listed members are
requested, by HTTP range requests through the zip directory (HttpFile is copied from tools/WP6_S1_comma_fetch.py).
V2AIX: members of the local zip data_extra/D13_v2aix/v2aix_json.zip (no download).
Checks: every member's size, compressed size and CRC32 must equal the member list (or the lock), and the
extracted file's sha256 must equal the lock for V2AIX. Any mismatch stops the item (nothing is substituted).
Resume: finished files are skipped; a partial file is <name>.part and is re-read. Disk: >= 15 GB stays free.
Outputs: data (data_extra, never committed); per-item manifests results/WP8/S1/items/<id>.json (names, bytes,
sha256 of each file; metadata only). The V2AIX manifest stays in the data folder (V2AIX-derived).
Journal: notes/WP8_journal.md, one line before and after each item.
"""
import datetime
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.request
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT.parent / "data_extra"
LIST = ROOT / "results" / "WP8" / "S0" / "S1_download_list.json"
LOCK_H31 = ROOT / "locks" / "H31.json"
ITEMS = ROOT / "results" / "WP8" / "S1" / "items"
JOURNAL = ROOT / "notes" / "WP8_journal.md"
KITTI_OUT = DATA / "D04b_kitti_raw_v31"
COMMA_OUT = DATA / "D22_comma2k19"
V2AIX_ZIP = DATA / "D13_v2aix" / "v2aix_json.zip"
V2AIX_OUT = DATA / "D13_v2aix" / "extracted_v31"
MIN_FREE = 15 * 10**9
CHUNK = 1 << 20


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def journal(what, state):
    line = f"{now()} | S1 | {what} | {state}"
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)


def stop(item, why):
    journal(f"STOP {item}", why)
    raise SystemExit(f"STOP {item}: {why}")


def check_space(nbytes):
    free = shutil.disk_usage(DATA).free
    if free - nbytes < MIN_FREE:
        raise SystemExit(f"STOP disk: free {free / 1e9:.1f} GB, file {nbytes / 1e9:.2f} GB, 15 GB must stay free")


class HttpFile:
    """Seekable read-only file over HTTP range requests (block cache). Copied from tools/WP6_S1_comma_fetch.py."""

    def __init__(self, url, block=CHUNK):
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req) as r:
            self.url, self.size = r.geturl(), int(r.headers["Content-Length"])
        self.pos, self.block, self.cache, self.bytes = 0, block, {}, 0

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def _get(self, a, b):
        for attempt in range(5):
            try:
                req = urllib.request.Request(self.url, headers={"Range": f"bytes={a}-{b - 1}"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    data = r.read()
                if len(data) != b - a:
                    raise IOError(f"short range read {len(data)} != {b - a}")
                self.bytes += len(data)
                return data
            except Exception as e:  # network hiccup: retry
                print("retry", a, e, flush=True)
                time.sleep(2 + 3 * attempt)
        raise IOError("range request failed")

    def read(self, n=-1):
        if n < 0:
            n = self.size - self.pos
        n = max(0, min(n, self.size - self.pos))
        if n > 4 * self.block:
            data = self._get(self.pos, self.pos + n)
        else:
            out = []
            p, end = self.pos, self.pos + n
            while p < end:
                b0 = p // self.block
                if b0 not in self.cache:
                    if len(self.cache) > 64:
                        self.cache.clear()
                    self.cache[b0] = self._get(b0 * self.block, min(self.size, (b0 + 1) * self.block))
                blk = self.cache[b0]
                o = p - b0 * self.block
                take = min(end - p, len(blk) - o)
                out.append(blk[o:o + take])
                p += take
            data = b"".join(out)
        self.pos += len(data)
        return data


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(CHUNK), b""):
            h.update(b)
    return h.hexdigest()


def download_resumable(url, dst):
    """curl -C - equivalent: continue a .part file with a Range request; restart if the server ignores Range."""
    part = dst.with_name(dst.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
            with urllib.request.urlopen(req, timeout=120) as r:
                mode = "ab" if (have and r.status == 206) else "wb"
                with open(part, mode) as f:
                    shutil.copyfileobj(r, f, CHUNK)
            os.replace(part, dst)
            return
        except Exception as e:
            print("retry download", e, flush=True)
            have = part.stat().st_size if part.exists() else 0
            time.sleep(3 + 3 * attempt)
    raise IOError("download failed")


def load_items():
    lst = json.loads(LIST.read_text(encoding="utf-8"))
    out = {}
    for it in lst["items"]:
        w = it["what"]
        if w.startswith("KITTI 2011_"):
            out[w.split()[1]] = it
        elif w == "KITTI calib":
            day = it["url"].rsplit("/", 1)[1].replace("_calib.zip", "")
            out["calib_" + day] = it
        elif w.startswith("comma2k19 Chunk_"):
            out[w.split()[1]] = it
        elif w.startswith("V2AIX"):
            out["v2aix_h31"] = it
    return out


def expand(args, items):
    ids = []
    for a in args:
        if a == "kitti":
            ids += [k for k in items if k.startswith("2011_")]
        elif a == "calib":
            ids += [k for k in items if k.startswith("calib_")]
        elif a == "comma":
            ids += ["Chunk_2", "Chunk_4", "Chunk_3"]
        elif a == "all":
            ids += [k for k in items if k.startswith("2011_") or k.startswith("calib_")] + ["Chunk_2", "Chunk_4", "Chunk_3", "v2aix_h31"]
        else:
            ids.append(a)
    return list(dict.fromkeys(ids))


def check_scope(scope, out_root, rels, item):
    """The folder of an item must be new: only files of this item may be inside (resume of our own files)."""
    if not scope.exists():
        return
    rel_set = set(rels)
    for p in scope.rglob("*"):
        if p.is_file() and not p.name.endswith(".part"):
            rel = p.relative_to(out_root).as_posix()
            if rel not in rel_set:
                stop(item, f"unexpected file in target folder: {rel}")


def write_manifest(item_id, out_root, rels, it, extra=None):
    rows = []
    for rel in sorted(rels):
        p = out_root / rel
        rows.append({"path": rel, "bytes": p.stat().st_size, "sha256": sha256_file(p)})
    canon = "".join(f"{r['path']}\t{r['bytes']}\t{r['sha256']}\n" for r in rows)
    man = {
        "id": item_id,
        "url": it["url"],
        "n_files": len(rows),
        "bytes": sum(r["bytes"] for r in rows),
        "manifest_sha256": hashlib.sha256(canon.encode("utf-8")).hexdigest(),
        "manifest_rule": "sha256 of lines 'path<TAB>bytes<TAB>file sha256' sorted by path, each ending in LF",
        "date": time.strftime("%Y-%m-%d"),
        "files": rows,
    }
    if extra:
        man.update(extra)
    return man


def save_manifest(man, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(man, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, path)


def fetch_members(item_id, it, out_root, rel_of, scope):
    """Range-fetch the listed members of one zip into out_root; manifest written in results/WP8/S1/items/."""
    members = json.loads((ROOT / it["member_list"]).read_text(encoding="utf-8"))["members"]
    n = len(members)
    u_total = sum(m[1] for m in members)
    c_total = sum(m[2] for m in members)
    if "n_members" in it and n != it["n_members"]:
        stop(item_id, f"member count {n} differs from list {it['n_members']}")
    if u_total != it["on_disk"] or c_total != it["transfer"]:
        stop(item_id, f"list totals (transfer {c_total}, on disk {u_total}) differ from S1 list "
                      f"(transfer {it['transfer']}, on disk {it['on_disk']})")
    rels = [rel_of(m[0]) for m in members]
    if len(set(rels)) != n:
        stop(item_id, "duplicate target paths")
    check_scope(scope, out_root, rels, item_id)
    journal(f"before {item_id} | {n} members, {u_total / 1e9:.3f} GB on disk, {c_total / 1e6:.1f} MB transfer | "
            f"{it['url']} -> {out_root}", "fetching (range requests)")
    f = HttpFile(it["url"])
    z = zipfile.ZipFile(f)
    infos = {i.filename: i for i in z.infolist()}
    done = present = 0
    t0 = time.time()
    for (name, fs, cs, crc), rel in zip(members, rels):
        dst = out_root / rel
        if dst.is_file() and dst.stat().st_size == fs:
            present += 1
            continue
        info = infos.get(name)
        if info is None or info.file_size != fs or info.compress_size != cs or f"{info.CRC:08x}" != crc:
            stop(item_id, f"member {name} differs from the member list / zip directory")
        check_space(fs)
        dst.parent.mkdir(parents=True, exist_ok=True)
        part = dst.with_name(dst.name + ".part")
        crc_run, written = 0, 0
        try:
            with z.open(info) as src, open(part, "wb") as out:
                while True:
                    b = src.read(CHUNK)
                    if not b:
                        break
                    out.write(b)
                    crc_run = zlib.crc32(b, crc_run)
                    written += len(b)
        except Exception as e:
            part.unlink(missing_ok=True)
            stop(item_id, f"read error on {name}: {e}")
        if written != fs or f"{crc_run & 0xffffffff:08x}" != crc:
            part.unlink(missing_ok=True)
            stop(item_id, f"size/CRC after write differs for {name}")
        os.replace(part, dst)
        done += 1
        if (done + present) % 500 == 0:
            print(f"{item_id}: {done} written, {present} present, {f.bytes / 1e6:.0f} MB http, "
                  f"{time.time() - t0:.0f} s", flush=True)
    journal(f"after {item_id} | written {done}, already present {present}, http bytes {f.bytes / 1e6:.1f} MB, "
            f"{time.time() - t0:.0f} s", "files on disk; manifest next")
    man = write_manifest(item_id, out_root, rels, it, {"members_listed": n, "members_written_now": done,
                                                       "http_bytes": f.bytes})
    save_manifest(man, ITEMS / f"{item_id}.json")
    journal(f"manifest {item_id} | {man['n_files']} files, {man['bytes'] / 1e9:.3f} GB, "
            f"manifest_sha256 {man['manifest_sha256']}", "written to results/WP8/S1/items")


def safe_parts(name):
    parts = name.replace("\\", "/").split("/")
    return not name.startswith("/") and all(p not in ("", ".", "..") and ":" not in p for p in parts)


def fetch_calib(item_id, it):
    day = item_id.split("_", 1)[1]
    out = KITTI_OUT / "calib" / day
    zip_path = out / Path(it["url"]).name
    standard = ["calib_cam_to_cam.txt", "calib_imu_to_velo.txt", "calib_velo_to_cam.txt"]
    check_scope(out, KITTI_OUT, [f"calib/{day}/{zip_path.name}"] + [f"calib/{day}/{s}" for s in standard], item_id)
    journal(f"before {item_id} | {it['url']} -> {out}", "downloading (resumable)")
    check_space(10 * 10**6)
    out.mkdir(parents=True, exist_ok=True)
    if not zip_path.exists():
        download_resumable(it["url"], zip_path)
    if zip_path.stat().st_size != it["on_disk"]:
        stop(item_id, f"zip size {zip_path.stat().st_size} differs from list {it['on_disk']}")
    z = zipfile.ZipFile(zip_path)
    names = []
    for info in z.infolist():
        if info.is_dir():
            continue
        if not safe_parts(info.filename):
            stop(item_id, f"unsafe member name {info.filename}")
        dst = out / info.filename
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            part = dst.with_name(dst.name + ".part")
            part.write_bytes(z.read(info))  # zipfile checks the CRC
            os.replace(part, dst)
        names.append(dst.relative_to(out).as_posix())
    rels = [f"calib/{day}/{zip_path.name}"] + [f"calib/{day}/{n}" for n in names]
    zsha = sha256_file(zip_path)
    man = write_manifest(item_id, KITTI_OUT, rels, it,
                         {"zip_sha256": zsha, "zip_bytes": zip_path.stat().st_size, "members": names})
    save_manifest(man, ITEMS / f"{item_id}.json")
    journal(f"after {item_id} | zip {zip_path.stat().st_size} B, sha256 {zsha}, members {names}",
            "extracted; manifest written")


def fetch_v2aix():
    item = "v2aix_h31"
    lock = json.loads(LOCK_H31.read_text(encoding="utf-8"))
    v = lock["domains"]["v2x"]["fresh"]["v2aix"]
    recs = v["recordings"]
    if len(recs) != 674:
        stop(item, f"lock has {len(recs)} recordings, expected 674")
    if not V2AIX_ZIP.exists() or V2AIX_ZIP.stat().st_size != v["zip"]["bytes"]:
        stop(item, "local V2AIX zip missing or size differs from lock")
    journal(f"before {item} | local zip {V2AIX_ZIP} (sha256 check) -> {V2AIX_OUT}, 674 recordings, "
            f"extraction only, never committed", "hashing zip")
    zsha = sha256_file(V2AIX_ZIP)
    if zsha != v["zip"]["sha256"]:
        stop(item, f"zip sha256 {zsha} differs from lock")
    z = zipfile.ZipFile(V2AIX_ZIP)
    infos = {i.filename: i for i in z.infolist()}
    done = present = 0
    t0 = time.time()
    for r in recs:
        info = infos.get(r["member"])
        if info is None or info.file_size != r["bytes"] or f"{info.CRC:08x}" != r["crc32"]:
            stop(item, f"recording {r['rid']} differs from the lock (size / CRC32)")
        dst = V2AIX_OUT / r["member"]
        if dst.is_file() and dst.stat().st_size == r["bytes"] and sha256_file(dst) == r["sha256"]:
            present += 1
            continue
        check_space(r["bytes"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        part = dst.with_name(dst.name + ".part")
        data = z.read(info)  # zipfile checks the CRC
        if hashlib.sha256(data).hexdigest() != r["sha256"]:
            stop(item, f"sha256 of {r['rid']} differs from the lock")
        part.write_bytes(data)
        os.replace(part, dst)
        done += 1
    journal(f"after {item} | extracted {done}, present {present}, {time.time() - t0:.0f} s", "checking manifest")
    rels = [r["member"] for r in recs]
    man = {"id": item, "n_files": len(rels), "rule": "lock sha256 per recording verified on extraction",
           "zip_sha256": zsha, "members_sha256_ok": True, "date": time.strftime("%Y-%m-%d")}
    save_manifest(man, V2AIX_OUT / "_manifest_v31.json")
    journal(f"manifest {item} | {len(rels)} recordings verified (sha256 + CRC32 vs lock), data folder only",
            "done")


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    items = load_items()
    ids = expand(args, items)
    journal(f"start fetch {' '.join(ids)}", "running")
    for item_id in ids:
        if item_id.startswith("calib_"):
            fetch_calib(item_id, items[item_id])
        elif item_id.startswith("2011_"):
            it = items[item_id]
            drive = f"{item_id}_sync"
            fetch_members(item_id, it, KITTI_OUT, lambda n: n.split("/", 1)[1], KITTI_OUT / drive)
        elif item_id.startswith("Chunk_"):
            it = items[item_id]
            out = COMMA_OUT / item_id
            fetch_members(item_id, it, out,
                          lambda n: n.split("/", 1)[1].replace("|", "_"), out)
        elif item_id == "v2aix_h31":
            fetch_v2aix()
        else:
            stop(item_id, "unknown id")
    journal(f"end fetch {' '.join(ids)}", "done")


if __name__ == "__main__":
    main()
