"""WP8 S0: list the central directory of public remote zips (no data members are downloaded).

Purpose: exact member counts / sizes / CRC32 for the S1 download list and locks/H31.json, for
KITTI raw drives (velodyne_points + oxts members only) and comma2k19 chunks (processed_log CAN /
GNSS / IMU + global_pose members only; route and dongle = car id). Only the zip directory bytes are
read (HTTP range requests, HttpFile copied from tools/WP6_S1_comma_fetch.py). Run with python -I.
Inputs: URLs (KITTI avg-kitti S3 bucket, Hugging Face commaai/comma2k19).
Outputs: results/WP8/S0/remote/<name>.json (one per zip, resumable: existing files are skipped).
Usage: python -I -u -W ignore tools/WP8_S0_remote_list.py kitti|comma
"""
import json
import os
import sys
import time
import urllib.request
import zipfile
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "WP8", "S0", "remote")
KITTI_BASE = "https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data"
KITTI = (["2011_09_26_drive_%s" % d for d in
          "0009 0014 0018 0022 0023 0032 0036 0051 0056 0057 0059 0061 0064 0084 0086 0087 0091 0093 "
          "0096 0101 0104 0117".split()]
         + ["2011_09_29_drive_%s" % d for d in "0004 0026 0071".split()]
         + ["2011_09_30_drive_%s" % d for d in "0016 0018 0020 0027 0028 0033 0034".split()]
         + ["2011_10_03_drive_%s" % d for d in "0027 0034 0042 0047".split()]
         + ["2011_09_28_drive_%s" % d for d in "0001 0002".split()])
COMMA = "https://huggingface.co/datasets/commaai/comma2k19/resolve/main/raw_data/Chunk_{k}.zip"
COMMA_KEEP = ("processed_log/CAN/", "processed_log/GNSS/", "processed_log/IMU/", "global_pose/")


class HttpFile:
    """Seekable read-only file over HTTP range requests (block cache). Copy of WP6_S1_comma_fetch.HttpFile."""

    def __init__(self, url, block=1 << 20):
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=60) as r:
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
                req = urllib.request.Request(self.url, headers={"Range": "bytes=%d-%d" % (a, b - 1)})
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = r.read()
                self.bytes += len(data)
                return data
            except Exception as e:
                print("retry", a, e, flush=True)
                time.sleep(2 + 3 * attempt)
        raise IOError("range request failed")

    def read(self, n=-1):
        if n < 0:
            n = self.size - self.pos
        n = max(0, min(n, self.size - self.pos))
        out, p, end = [], self.pos, self.pos + n
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


def save(name, obj):
    os.makedirs(OUT, exist_ok=True)
    tmp = os.path.join(OUT, name + ".json.tmp")
    json.dump(obj, open(tmp, "w"), indent=1)
    os.replace(tmp, os.path.join(OUT, name + ".json"))


def kitti():
    for d in KITTI:
        if os.path.exists(os.path.join(OUT, d + ".json")):
            continue
        url = "%s/%s/%s_sync.zip" % (KITTI_BASE, d, d)
        f = HttpFile(url)
        z = zipfile.ZipFile(f)
        keep = [i for i in z.infolist() if not i.is_dir()
                and ("/velodyne_points/" in i.filename or "/oxts/" in i.filename)]
        velo = [i for i in keep if i.filename.endswith(".bin")]
        oxts = [i for i in keep if "/oxts/data/" in i.filename and i.filename.endswith(".txt")]
        save(d, {"url": url, "zip_bytes": f.size, "dir_bytes_read": f.bytes,
                 "n_members_kept": len(keep), "n_scans": len(velo), "n_oxts": len(oxts),
                 "kept_compressed": sum(i.compress_size for i in keep),
                 "kept_uncompressed": sum(i.file_size for i in keep),
                 "members": [[i.filename, i.file_size, i.compress_size, "%08x" % i.CRC] for i in keep]})
        print(d, len(velo), "scans", sum(i.file_size for i in keep) / 1e6, "MB kept", flush=True)


def comma():
    for k in range(2, 11):
        name = "comma_Chunk_%d" % k
        if os.path.exists(os.path.join(OUT, name + ".json")):
            continue
        url = COMMA.format(k=k)
        f = HttpFile(url)
        z = zipfile.ZipFile(f)
        routes = defaultdict(lambda: {"segments": set(), "kept_compressed": 0, "kept_uncompressed": 0, "n": 0})
        members = []
        for i in z.infolist():
            if i.is_dir() or not any(s in i.filename for s in COMMA_KEEP):
                continue
            parts = i.filename.split("/")
            r = routes[parts[1]]
            r["segments"].add(parts[2])
            r["kept_compressed"] += i.compress_size
            r["kept_uncompressed"] += i.file_size
            r["n"] += 1
            members.append([i.filename, i.file_size, i.compress_size, "%08x" % i.CRC])
        rs = {n: {"dongle": n.split("|")[0], "n_segments": len(v["segments"]), "n_members": v["n"],
                  "kept_compressed": v["kept_compressed"], "kept_uncompressed": v["kept_uncompressed"]}
              for n, v in sorted(routes.items())}
        save(name, {"url": url, "zip_bytes": f.size, "dir_bytes_read": f.bytes, "routes": rs,
                    "members": members})
        print(name, len(rs), "routes", sorted({v["dongle"] for v in rs.values()}),
              sum(v["kept_uncompressed"] for v in rs.values()) / 1e9, "GB kept", flush=True)


if __name__ == "__main__":
    {"kitti": kitti, "comma": comma}[sys.argv[1]]()
