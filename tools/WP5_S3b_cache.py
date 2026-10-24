"""WP5 S3b: rebuild the V2AIX per-recording caches with the reception-time column recv_s (adapter change of S3b). Caches stay in ../data_extra (licence).
Run from codes_v3/: python -I -u -W ignore tools/WP5_S3b_cache.py     Reads json with plain parsing (untrusted data)."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.dont_write_bytecode = True
from v2x import v2aix

t0 = time.time()
paths = v2aix.list_recordings()
n = 0
for i, p in enumerate(paths):
    df = v2aix.load_recording(p)
    n += len(df)
    if i % 100 == 0:
        print(i, len(paths), n, f"{time.time() - t0:.0f}s", flush=True)
print("done", len(paths), n, f"{time.time() - t0:.0f}s")
