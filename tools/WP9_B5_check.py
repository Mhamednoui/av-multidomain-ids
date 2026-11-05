"""WP9 B5 consistency check: re-read every number of the master table from its source JSON and assert equality.

Purpose: guarantee that results/WP9/B5_master.json, reports/WP9_final.md (and the figures' presence) agree with the
approved result files. Independent resolver (does not import the builder).
Checks: (1) every field value == value re-read from its source file/path (means/min/max recomputed);
(2) every field text == fmt(value); (3) every cell / claim re-rendered from its template == stored text;
(4) every stored cell appears in reports/WP9_final.md; (5) verdict words allowed, 'better' only when all flags are true;
(6) bar probes (numbers quoted from B0 / reports) occur in the named source; (7) figures and their CSVs exist.
Run: python tools/WP9_B5_check.py   (exit code 0 = pass).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from WP9_B5_lib import ALLOWED_VERDICTS, fmt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
errors = []
n_checked = 0


def err(msg):
    errors.append(msg)


def read_json(rel):
    with open(os.path.join(ROOT, rel), "r", encoding="utf-8") as fh:
        return json.load(fh)


_c = {}


def src(rel):
    if rel not in _c:
        _c[rel] = read_json(rel)
    return _c[rel]


def walk(o, path):
    for e in path:
        if isinstance(e, dict):
            hits = [x for x in o if all(x.get(k) == v for k, v in e.items())]
            if len(hits) != 1:
                raise KeyError(f"selector {e} matched {len(hits)}")
            o = hits[0]
        else:
            o = o[e]
    return o


def reread(spec):
    if spec["kind"] == "path":
        return walk(src(spec["file"]), spec["path"])
    vals = [walk(src(s["file"]), s["path"]) for s in spec["srcs"]]
    return {"mean": lambda v: sum(v) / len(v), "min": min, "max": max}[spec["kind"]](vals)


def same(a, b):
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def check_fields(owner, fields):
    global n_checked
    texts = {}
    for name, f in fields.items():
        try:
            v = reread(f["spec"])
        except Exception as ex:  # noqa: BLE001
            err(f"{owner}.{name}: cannot re-read source ({ex})")
            continue
        n_checked += 1
        if not same(v, f["value"]):
            err(f"{owner}.{name}: source {v!r} != master {f['value']!r}")
        t = fmt(f["spec"]["fmt"], v)
        if t != f["text"]:
            err(f"{owner}.{name}: text {t!r} != master text {f['text']!r}")
        texts[name] = t
    return texts


class Obj:
    def __init__(self, d):
        self.__dict__.update(d)


def main():
    m = read_json("results/WP9/B5_master.json")
    with open(os.path.join(ROOT, "reports/WP9_final.md"), "r", encoding="utf-8") as fh:
        report = fh.read()
    esc = lambda s: s.replace("|", "/")  # noqa: E731
    TX = {}
    b0 = src("results/WP9/B0_literature.json")["rows"]

    for r in m["rows"]:
        tx = check_fields(r["id"], r["fields"])
        TX[r["id"]] = Obj(tx)
        for k in ("ours", "op", "caveats"):
            rendered = r["templates"][k].format(**tx)
            if rendered != r["cells"][k]:
                err(f"{r['id']}.{k}: re-rendered cell differs from master")
            if esc(rendered) not in report:
                err(f"{r['id']}.{k}: cell not found in reports/WP9_final.md")
        if r["verdict"] not in ALLOWED_VERDICTS:
            err(f"{r['id']}: verdict {r['verdict']!r} not allowed")
        if r["verdict"] == "better" and not all(r["flags"].values()):
            err(f"{r['id']}: verdict 'better' without all flags (same data, same-or-stricter split, CI excludes bar)")
        if f"**{r['verdict']}**" not in report:
            err(f"{r['id']}: verdict not in report")
        if esc(r["bar"]["text"]) not in report:
            err(f"{r['id']}: bar text not in report")
        for rel, idx, probe in r["bar"]["probes"]:
            if idx is None:
                with open(os.path.join(ROOT, rel), "r", encoding="utf-8") as fh:
                    blob = fh.read()
            else:
                blob = json.dumps(src(rel)["rows"][idx])
            if probe not in blob:
                err(f"{r['id']}: bar probe {probe!r} not found in {rel}[{idx}]")
        for i in r["bar"]["b0"]:
            if i >= len(b0):
                err(f"{r['id']}: B0 row {i} does not exist")
    for r in m["table2"]:
        tx = check_fields(r["id"], r["fields"])
        TX[r["id"]] = Obj(tx)
        for k in ("v3", "v31", "diff", "note"):
            if r["group"] == "meta" and k != "v3":
                continue
            rendered = r["templates"][k].format(**tx)
            if rendered != r["cells"][k]:
                err(f"{r['id']}.{k}: re-rendered cell differs from master")
            if esc(rendered) not in report:
                err(f"{r['id']}.{k}: cell not found in report")
        if r["group"] == "2b" and "NOT fresh" not in r["exposure"]:
            err(f"{r['id']}: S8 row must be labelled NOT fresh")
    for kind in ("claims", "cannot"):
        for c in m[kind]:
            rendered = c["template"].format(**TX)
            if rendered != c["text"]:
                err(f"{kind} {c['row']}: re-rendered text differs from master")
            if rendered not in report:
                err(f"{kind} {c['row']}: text not in report")
    # overstating words only where the verdict is better
    any_better = any(r["verdict"] == "better" for r in m["rows"])
    allowed_ctx = ("cannot claim", "matches the best published", "no row has the verdict", "equal rows are worded", "we cannot claim")
    for w in ("state of the art", "state-of-the-art", "best", "outperform", "better than"):
        for line in report.splitlines():
            low = line.lower()
            if w in low and not any_better and not any(c in low for c in allowed_ctx):
                err(f"overstating word {w!r} in: {line[:140]}")
    for f in m["figures"]:
        for rel in (f[0], f[2]):
            if not os.path.exists(os.path.join(ROOT, "results/WP9/B5/figures", rel)):
                err(f"figure file missing: {rel}")
    print(f"fields checked: {n_checked}; rows: {len(m['rows'])}; table2 rows: {len(m['table2'])}; claims: {len(m['claims'])}; cannot: {len(m['cannot'])}")
    if errors:
        print("FAIL")
        for e in errors:
            print(" -", e)
        return 1
    print("PASS: every master-table number equals its source JSON value; all cells present in reports/WP9_final.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
