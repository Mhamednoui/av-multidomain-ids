"""WP6 S1: fetch the small processed-log files of ONE comma2k19 chunk (D22, MIT) by HTTP range requests.

Purpose: comma2k19 Chunk_1.zip is 8.7 GB, almost all of it video (video.hevc, ~40 MB per minute) and raw logs.
WP6 needs only the processed numpy arrays (CAN speed / wheel speed / raw CAN, GNSS, IMU, global pose) of the
segments. Python's zipfile reads the central directory and the selected members through a seekable HTTP
file object, so only those bytes are transferred. The chunk is never executed: members are numpy arrays read
later with np.load(allow_pickle=False). Run with python -I.
Inputs: URL of the chunk on Hugging Face (commaai/comma2k19, raw_data/Chunk_<k>.zip).
Outputs: ../data_extra/D22_comma2k19/Chunk_<k>/<route>/<segment>/<file path>, plus manifest.json.
Usage: python -I -u tools/WP6_S1_comma_fetch.py list|fetch [chunk]
"""
import json
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT.parent / "data_extra" / "D22_comma2k19"
URL = "https://huggingface.co/datasets/commaai/comma2k19/resolve/main/raw_data/Chunk_{k}.zip"
KEEP = ("processed_log/CAN/", "processed_log/GNSS/", "processed_log/IMU/", "global_pose/")


class HttpFile:
    """Seekable read-only file over HTTP range requests (block cache)."""

    def __init__(self, url, block=1 << 20):
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
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = r.read()
                self.bytes += len(data)
                return data
            except Exception as e:                       # network hiccup: retry
                print("retry", a, e, flush=True)
                time.sleep(2 + 3 * attempt)
        raise IOError("range request failed")

    def read(self, n=-1):
        if n < 0:
            n = self.size - self.pos
        n = max(0, min(n, self.size - self.pos))
        if n > 4 * self.block:                           # big member: one direct request
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


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "list"
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    f = HttpFile(URL.format(k=k))
    z = zipfile.ZipFile(f)
    infos = z.infolist()
    print("chunk", k, "size GB", round(f.size / 1e9, 2), "members", len(infos), "dir bytes", f.bytes, flush=True)
    keep = [i for i in infos if any(s in i.filename for s in KEEP) and not i.is_dir()]
    print("kept members", len(keep), "MB", round(sum(i.file_size for i in keep) / 1e6, 1),
          "compressed MB", round(sum(i.compress_size for i in keep) / 1e6, 1), flush=True)
    if mode == "list":
        for i in infos[:60]:
            print(i.filename, i.file_size, i.compress_type)
        return
    dest = OUT / f"Chunk_{k}"
    t0 = time.time()
    done = 0
    for i in keep:
        rel = i.filename.split("/", 1)[1] if i.filename.startswith(f"Chunk_{k}/") else i.filename
        p = dest / rel.replace("|", "_")             # "|" (dongle|route) is not allowed in Windows file names
        if p.exists() and p.stat().st_size == i.file_size:
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(z.read(i))
        done += 1
        if done % 200 == 0:
            print(done, "files", round(f.bytes / 1e6), "MB transferred", round(time.time() - t0), "s", flush=True)
    man = {"chunk": k, "url": URL.format(k=k), "licence": "MIT", "chunk_bytes": f.size, "members_kept": len(keep),
           "bytes_kept": sum(i.file_size for i in keep), "bytes_transferred": f.bytes, "filter": KEEP,
           "date": time.strftime("%Y-%m-%d")}
    (dest / "manifest.json").write_text(json.dumps(man, indent=1))
    print("done", man, flush=True)


if __name__ == "__main__":
    main()
