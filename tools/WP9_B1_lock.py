"""WP9 B1: parse + dedup every capture and write locks/WP9_<dataset>.json (BEFORE any training).

Usage: python -u -W ignore tools/WP9_B1_lock.py carhacking|road|d11
Resumable: per-capture parsed arrays + report are cached in data_extra/cache_v3/WP9/B1/parsed/<ds>/ (no feature, no model).
Lock content: file list with sha256, rows, dedup counts, split part per capture / per block, segment row ranges,
class lists, protocol decisions. Nothing here reads a model output.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP9_B1_lib as L
from can import adapters as A
from can import splits as SP
from common.config import SEED

PARSED = L.CACHE / "parsed"


def pp(ds, cap):
    d = PARSED / ds
    d.mkdir(parents=True, exist_ok=True)
    s = cap.replace("/", "__")
    return d / (s + ".npz"), d / (s + ".json")


def parse_cached(ds, cap, parse_fn, path):
    npz, js = pp(ds, cap)
    if npz.exists() and js.exists():
        return json.load(open(js))
    d = parse_fn()
    d, rep = L.dedup(d)
    rep["sha256"] = L.sha256_file(path) if path else None
    rep["t_last"] = float(d["t"][-1] - d["t"][0])
    rep["injected"] = int(d["lab"].sum())
    tmp = npz.with_name(npz.stem + ".tmp.npz")
    np.savez(tmp, t=d["t"], id=d["id"], dlc=d["dlc"], B=d["B"], lab=d["lab"])
    tmp.replace(npz)
    json.dump(rep, open(js, "w"))
    return rep


def load_parsed(ds, cap):
    z = np.load(pp(ds, cap)[0])
    return {k: z[k] for k in z.files}


# ------------------------------------------------------------------ Car-Hacking
def lock_carhacking():
    reps, labs = {}, {}
    for name in A.CARHACKING_FILES:
        L.journal(f"lock carhacking: parse {name}")
        reps[name] = parse_cached("carhacking", name, lambda n=name: L.parse_carhacking(n), L.DATA / A.CARHACKING_FILES[name])
        labs[name] = load_parsed("carhacking", name)["lab"]
    blocks = SP.carhacking_blocks(labs)           # v2 / WP2 S1 interleaved block assignment (same seed, same order)
    out = {"files": {}}
    for name in A.CARHACKING_FILES:
        d = load_parsed("carhacking", name)
        n = len(d["t"])
        bi = SP.block_index(n)
        parts = np.array(blocks[name], dtype=object)[bi]
        t = d["t"]
        # runs of equal part
        change = np.flatnonzero(parts[1:] != parts[:-1]) + 1
        starts = np.r_[0, change]
        ends = np.r_[change, n]
        segs = []
        for k, (a, b) in enumerate(zip(starts, ends)):
            lo = t[a] + (L.GAP if a > 0 else 0.0)            # drop GAP seconds after a boundary
            hi = t[b - 1] - (L.GAP if b < n else 0.0)        # and before the next boundary
            ia = int(np.searchsorted(t[a:b], lo, side="left")) + a
            ib = int(np.searchsorted(t[a:b], hi, side="right")) + a
            if ib - ia > 1000:
                segs.append({"seg": f"{name}/{k:03d}", "part": str(parts[a]), "row_start": int(ia), "row_end": int(ib),
                             "t_start": float(t[ia]), "t_end": float(t[ib - 1]), "injected": int(d["lab"][ia:ib].sum())})
        out["files"][name] = {"path": str(L.DATA / A.CARHACKING_FILES[name]), **reps[name],
                              "blocks": [str(x) for x in blocks[name]], "segments": segs,
                              "dropped_gap_rows": int(n - sum(s["row_end"] - s["row_start"] for s in segs))}
    L.journal("lock carhacking: parse normal_run")
    nr_rep = parse_cached("carhacking", "normal_run", L.parse_carhacking_normal, L.DATA / "normal_run_data.txt")
    d = load_parsed("carhacking", "normal_run")
    t = d["t"]
    mid = t[-1] / 2
    ia = int(np.searchsorted(t, mid - L.GAP / 2)); ib = int(np.searchsorted(t, mid + L.GAP / 2))
    out["normal_run"] = {"path": str(L.DATA / "normal_run_data.txt"), **nr_rep, "gap_s": L.GAP,
                         "segments": [{"seg": "normal_run/val", "part": "val", "row_start": 0, "row_end": ia,
                                       "injected": 0},
                                      {"seg": "normal_run/test", "part": "test", "row_start": ib, "row_end": len(t),
                                       "injected": 0}]}
    out.update({"dataset": "Car-Hacking (HCRL, D02) + normal_run (D02n)", "classes": L.CH_CLASSES, "unit": "1 s window",
                "seed": SEED, "gap_s": L.GAP, "window_s": L.WIN,
                "protocol": ("v2 / WP2 S1 interleaved time-block split (100 blocks per file; attack-bearing and attack-free "
                             "blocks each cut 70/15/15 train/val/test), 1 s dropped on both sides of every boundary between "
                             "different parts, windows and causal features built inside each segment after the split. "
                             "normal_run: first half val, second half test, 1 s gap (pure-benign false-alarm data)."),
                "dedup": "rows identical in (t, id, dlc, payload) dropped, first kept; counts per file above",
                "caveat": "single vehicle; attack and attack-free blocks of one file differ in context (parked vehicle, Lampe & Meng)"})
    return out


# ------------------------------------------------------------------ ROAD
def lock_road():
    caps = A.road_captures()
    out = {"captures": {}}
    for _, r in caps.iterrows():
        name = r["name"]
        if not r["usable"]:
            out["captures"][name] = {"part": "excluded_no_labels", "family": r["family"], "kind": r["kind"],
                                     "sha256": L.sha256_file(r["path"])}
            continue
        L.journal(f"lock road: parse {name}")
        rep = parse_cached("road", name, lambda n=name: L.parse_road(n, caps), r["path"])
        part = r["part"]
        fam = r["family"]
        base = name.replace("_masquerade", "")
        entry = {"part": part, "family": fam, "kind": r["kind"], "base": base, **rep, "path": str(r["path"]),
                 "injection_interval": (r["meta"]["injection_interval"] if r["meta"] is not None else None)}
        if fam == "max_engine_coolant_temp":
            entry["part"] = "test_unseen_family"
            entry["note"] = "attack only in test; family unseen in train: unseen-family row only"
        key = (fam + ("_masquerade" if r["kind"] == "masquerade" else "")) if fam != "ambient" else "normal"
        entry["attack_class"] = key
        out["captures"][name] = entry
    out.update({"dataset": "ROAD (ORNL, D05)", "classes": L.ROAD_CLASSES, "unseen_classes": L.ROAD_UNSEEN, "unit": "1 s window",
                "seed": SEED, "window_s": L.WIN,
                "protocol": ("WP2 S1 / v2 capture-level split (results/WP2/s1_road.json): attack instance 1 train, 2 val, 3 test, "
                             "masquerade copies with their original; ambient test/val lists fixed by v2. Accelerator captures "
                             "have no labels: excluded. max_engine_coolant_temp: attack only in test, unseen-family row only."),
                "window_rule": ("window label = class of injected frames inside it; normal window = no injected frame and "
                                "no frame in [interval start - 1 s, interval end + 1 s] of an attack capture; windows with "
                                "non-injected frames inside that interval and no injected frame are excluded"),
                "dedup": "rows identical in (t, id, dlc, payload) dropped, first kept"})
    return out


# ------------------------------------------------------------------ D11
def lock_d11():
    spl = json.load(open(L.RESULTS / "WP2" / "splits_d11.json"))
    table = A.d11_file_table().set_index("capture")
    out = {"sets": {}}
    for s, parts in spl["splits"].items():
        fams = sorted({table.loc[c, "attack_family"] for c in parts["train"] + parts["val"]
                       if not table.loc[c, "no_attack_family"]})
        entry = {"classes": ["Normal"] + fams, "parts": {}}
        for part, lst in parts.items():
            if part == "excluded_duplicates":
                entry["excluded_duplicates"] = lst
                continue
            caps = []
            for c in lst:
                L.journal(f"lock d11: parse {c}")
                rep = parse_cached("d11", c, lambda c=c: L.parse_d11(c, table.loc[c, "path"]), table.loc[c, "path"])
                fam = table.loc[c, "attack_family"]
                caps.append({"capture": c, "family": fam, "no_attack": bool(table.loc[c, "no_attack_family"]),
                             "vehicle": table.loc[c, "vehicle"], "path": str(table.loc[c, "path"]), **rep,
                             "class": ("Normal" if table.loc[c, "no_attack_family"] else
                                       fam if fam in fams else "UNSEEN")})
            entry["parts"][part] = caps
        # consistency: test_01 / test_02 families seen in train; test_03 / test_04 unseen
        for tp in ("test_01", "test_02"):
            bad = [c["capture"] for c in entry["parts"][tp] if c["class"] == "UNSEEN"]
            entry[f"{tp}_unseen_families"] = bad
        out["sets"][s] = entry
    out.update({"dataset": "can-train-and-test (DTU, D11)", "unit": "1 s window", "seed": SEED, "window_s": L.WIN,
                "protocol": ("results/WP2/splits_d11.json: train_01 minus val hold-out (highest-numbered capture of each attack "
                             "family with >= 2 captures), test_01..04 as published; byte-identical files kept once. "
                             "Seen-attack rows = test_01 (known vehicle) and test_02 (unknown vehicle) because their attack "
                             "families are those of train; test_03 / test_04 contain families absent from train: unseen-attack "
                             "rows (CORRECTION of B0_splits_proposal.md, which called test_03 a seen-attack row)."),
                "dedup": "rows identical in (t, id, dlc, payload) dropped, first kept; sha256 of every file"})
    return out


if __name__ == "__main__":
    ds = sys.argv[1]
    lock = {"carhacking": lock_carhacking, "road": lock_road, "d11": lock_d11}[ds]()
    lock["wp"] = "WP9 B1"
    L.LOCKS.mkdir(exist_ok=True)
    L.jd(lock, L.LOCKS / f"WP9_{ds}.json")
    L.journal(f"lock {ds}: written locks/WP9_{ds}.json")
    print("done", ds)
