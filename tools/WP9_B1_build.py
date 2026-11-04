"""WP9 B1: build the per-segment cache (causal stream features + class codes) from the locked splits.

Usage: python -u -W ignore tools/WP9_B1_build.py carhacking|road|d11
Reads locks/WP9_<ds>.json and the parsed cache written by WP9_B1_lock.py; writes data_extra/cache_v3/WP9/B1/<ds>/<seg>.npz
and <ds>/index.json (segment id, part, group, set). Resumable (skips written segments). No model, no label-based choice.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP9_B1_lib as L
from WP9_B1_lock import load_parsed


def finish(ds, seg, d, cls, ok=None):
    p = L.seg_path(ds, seg)
    if p.exists():
        return
    S = L.build_segment(d, cls, ok)
    L.save_atomic(p, **S)


def build_carhacking():
    lock = json.load(open(L.LOCKS / "WP9_carhacking.json"))
    idx = []
    for name, f in lock["files"].items():
        d = load_parsed("carhacking", name)
        code = L.CH_CLASSES.index(name)
        for s in f["segments"]:
            a, b = s["row_start"], s["row_end"]
            sl = {k: v[a:b] for k, v in d.items()}
            finish("carhacking", s["seg"], sl, (sl["lab"] * code).astype(np.int8))
            idx.append({"seg": s["seg"], "part": s["part"], "group": s["seg"], "file": name, "kind": "block"})
    d = load_parsed("carhacking", "normal_run")
    for s in lock["normal_run"]["segments"]:
        sl = {k: v[s["row_start"]:s["row_end"]] for k, v in d.items()}
        finish("carhacking", s["seg"], sl, np.zeros(len(sl["t"]), np.int8))
        idx.append({"seg": s["seg"], "part": s["part"], "group": s["seg"], "file": "normal_run", "kind": "normal_run"})
    return idx


def build_road():
    lock = json.load(open(L.LOCKS / "WP9_road.json"))
    idx = []
    for name, c in lock["captures"].items():
        if c["part"].startswith("excluded"):
            continue
        d = load_parsed("road", name)
        key = c["attack_class"]
        code = 0 if key == "normal" else (L.ROAD_CLASSES.index(key) if key in L.ROAD_CLASSES else -1)
        cls = (d["lab"] * code).astype(np.int8)
        ok = np.ones(len(d["t"]), bool)
        if c["injection_interval"] is not None:
            a, b = c["injection_interval"]
            ok = ~(((d["t"] >= a - 1.0) & (d["t"] <= b + 1.0)) & (d["lab"] == 0))
        finish("road", name, d, cls, ok)
        idx.append({"seg": name, "part": c["part"], "group": c["base"] if "base" in c else name,
                    "family": c["family"], "kind": c["kind"], "attack_class": key,
                    "interval": c["injection_interval"]})
    return idx


def build_d11():
    lock = json.load(open(L.LOCKS / "WP9_d11.json"))
    idx = []
    for s, e in lock["sets"].items():
        for part, caps in e["parts"].items():
            for c in caps:
                d = load_parsed("d11", c["capture"])
                if c["class"] == "Normal":
                    code = 0
                elif c["class"] == "UNSEEN":
                    code = -1
                else:
                    code = e["classes"].index(c["class"])
                finish("d11", c["capture"], d, (d["lab"] * code).astype(np.int8))
                idx.append({"seg": c["capture"], "set": s, "part": part, "group": c["capture"], "family": c["family"],
                            "class": c["class"]})
    return idx


if __name__ == "__main__":
    ds = sys.argv[1]
    L.journal(f"build {ds}: start (resumable)")
    idx = {"carhacking": build_carhacking, "road": build_road, "d11": build_d11}[ds]()
    L.jd(idx, L.CACHE / ds / "index.json")
    L.journal(f"build {ds}: done ({len(idx)} segments)")
    print("done", ds, len(idx))
