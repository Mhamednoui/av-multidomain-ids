"""WP5 S0c: choose and extract whole V2AIX recordings (scenarios/<ts>.json) by the rule fixed in notes/WP5_v2x.md.
Rule: strata = path up to 'scenarios'; round-robin over strata (sorted), within a stratum seeded random order (SEED 42),
stop when the next file would exceed the 5 GB budget. Uses only archive paths and sizes. Writes extraction list to results/WP5/s0c_selection.json.
Extraction is plain byte copy by name (no path traversal: names are checked), nothing is executed."""
import json, random, sys, zipfile, os, shutil
zp, outdir, listing = sys.argv[1], sys.argv[2], sys.argv[3]
BUDGET = 5.0e9
rows = json.load(open(listing))
by = {}
for n, s, c in rows:
    p = n.split("/")
    if "scenarios" in p and n.endswith(".json"):
        by.setdefault("/".join(p[1:p.index("scenarios")]), []).append((n, s))
rng = random.Random(42)
for k in sorted(by):
    by[k].sort()
    rng.shuffle(by[k])
sel, tot, done = [], 0, False
keys = sorted(by)
i = 0
while not done and any(by[k] for k in keys):
    for k in keys:
        if not by[k]:
            continue
        n, s = by[k][0]
        if tot + s > BUDGET:
            done = True
            break
        by[k].pop(0); sel.append((k, n, s)); tot += s
print("selected", len(sel), "files", tot / 1e9, "GB")
z = zipfile.ZipFile(zp)
os.makedirs(outdir, exist_ok=True)
for k, n, s in sel + [("", "json/README.txt", 0)]:
    assert ".." not in n and not n.startswith("/")
    dst = os.path.join(outdir, *n.split("/"))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with z.open(n) as f, open(dst, "wb") as g:
        shutil.copyfileobj(f, g)
json.dump({"budget_bytes": BUDGET, "total_bytes": tot, "files": [{"stratum": k, "path": n, "bytes": s} for k, n, s in sel]},
          open(sys.argv[4], "w"), indent=1)
