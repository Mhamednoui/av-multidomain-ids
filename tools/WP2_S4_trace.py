"""WP2 S4 diagnostic (TRAIN/VAL ambient only): which checks fire on a held-out clean capture. Usage: python tools/WP2_S4_trace.py <held-out capture> [variant]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP2_S4_run as R
from can import l2b_signals as Z

c = sys.argv[1]
h = int(sys.argv[2]) if len(sys.argv) > 2 else 1
st, maps, codes = R.get_stats()
M = R.fit(st, codes, maps, [n for n in R.AMB if n != c], h)
tm, ids, _, dec = R.load_capture(c)
Z.TRACE = {}
Z.score_frames(M, tm, dec, len(tm))
nm = lambda k: f"{k[0]:#x}.{k[1]}"
rows = []
for tag, (n, v) in Z.TRACE.items():
    if v:
        key = tag[0] + ":" + (nm(R.CAT.keys[tag[1]]) if isinstance(tag[1], int) else nm(tag[1]) + "~" + nm(tag[2]))
        rows.append((v / max(n, 1), v, n, key))
rows.sort(reverse=True)
by = {}
for fr, v, n, key in rows:
    by.setdefault(key.split(":")[0], []).append((round(fr, 3), n, key))
for t, lst in by.items():
    print(t, len(lst), "checks fire;", sum(1 for x in lst if x[0] > 0.5), "with >50% of their frames;", lst[:12])
