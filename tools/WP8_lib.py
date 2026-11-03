"""WP8 (v3.1) shared helpers. Written in WP8 S1.

assert_not_h31(items): the G1 guard of notes/WP8_v31.md. Every S2-S6 tool calls it on its inputs before it reads or
fits anything, so that nothing in locks/H31.json reaches a fit, a threshold, a choice or a diagnostic.
Input items are H31 group ids (KITTI drive "2011_09_26_drive_0009", comma route "b0c9...|2018-08-18--18-20-55"
or its folder form "b0c9..._2018-08-18--18-20-55", V2AIX recording "Mobile/V2X-only/Highway/<timestamp>"), file
paths, or any string containing one of these tokens (a folder path, for example). Items whose id or path is listed
in locks/V31_val.json are never blocked, even if the same string also appears in H31 (shared material).
Raises H31Leak.

Known limit (stated in notes/WP8_v31.md): files that H31 and V31_val share by time or frame split (CICIDS2017 D10
CSVs, the VeReMi CSV, the Kia Soul OTIDS Attack_free file, the V2AIX zip) are NOT blocked at file level. The split
code must select only V31_val time blocks, frames or recordings; tests/v31 checks the split functions. The guard
is a tripwire, not a proof.

Stdlib only.
"""
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
H31_LOCK = ROOT / "locks" / "H31.json"
V31_LOCK = ROOT / "locks" / "V31_val.json"
DROP_KEYS = {"_note", "note", "metric", "sha256_note", "keep", "licence", "label", "K", "C", "why_no_fresh",
             "description", "split", "role", "car", "scene", "stratum", "attack_seeds", "hold_out_part"}
EXT = (".csv", ".log", ".txt", ".json", ".zip", ".pcap", ".bin")


class H31Leak(RuntimeError):
    """An input item belongs to the hold-out H31 (locks/H31.json)."""


def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _strings(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k not in DROP_KEYS:
                yield from _strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v)
    elif isinstance(o, str):
        yield o


def _dicts(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _dicts(v)
    elif isinstance(o, list):
        for v in o:
            yield from _dicts(v)


def _tokens(s):
    """Id tokens of a string: every path component, with '|' -> '_', '_sync' and data extensions removed."""
    out = set()
    for part in re.split(r"[\\/]", s):
        if not part:
            continue
        t = part.replace("|", "_")
        if t.endswith("_sync"):
            t = t[:-5]
        if t.lower().endswith(EXT):
            t = os.path.splitext(t)[0]
        out.add(t)
    return out


def _abs_path(p):
    return os.path.normcase(os.path.normpath(os.path.join(ROOT, p)))


def _h31_group_ids(h31):
    d = h31["domains"]
    ids = set()
    for dr in d["kitti_vehicle_block"]["drives"]:
        ids.add(dr["drive"])
    for side in ("rav4", "civic"):
        ids |= {r.replace("|", "_") for r in d["comma_vehicle_block"][side]["routes"]}
    for rec in d["v2x"]["fresh"]["v2aix"]["recordings"]:
        ids.add(rec["rid"])
        ids.add(rec["rid"].split("/")[-1])
    return ids


def _time_split_paths(h31):
    d = h31["domains"]
    out = {f["path"] for f in d["network"]["d10_test"]["files"]}
    out |= {f["path"] for f in d["v2x"]["reused"]["veremi_test"]["files"]}
    out.add(d["v2x"]["fresh"]["v2aix"]["zip"]["path"])
    return out


def _v31_ids_and_paths(v31):
    ids, paths = set(), set()
    for s in _strings(v31["domains"]):
        ids |= _tokens(s)
    for d in _dicts(v31["domains"]):
        p = d.get("path")
        if isinstance(p, str):
            paths.add(_abs_path(p))
    return ids, paths


def h31_only():
    """Return (ids, paths): the H31 groups and H31-only file paths that V31_val does not share."""
    h31, v31 = _load(H31_LOCK), _load(V31_LOCK)
    v_ids, v_paths = _v31_ids_and_paths(v31)
    ids = _h31_group_ids(h31) - v_ids
    h_paths = set()
    for d in _dicts(h31["domains"]):
        p = d.get("path")
        if isinstance(p, str) and p.startswith("../"):
            h_paths.add(p)
    time_split = _time_split_paths(h31)
    paths = {_abs_path(p) for p in h_paths if p not in time_split} - v_paths
    return ids, paths


def assert_not_h31(items):
    """Raise H31Leak if any input item is an H31 group or an H31-only file (G1)."""
    if isinstance(items, str):
        items = [items]
    ids, paths = h31_only()
    for it in items:
        s = str(it)
        if _abs_path(s) in paths:
            raise H31Leak(f"H31 file: {s}")
        hit = _tokens(s) & ids
        if hit:
            raise H31Leak(f"H31 group {sorted(hit)[0]} in input {s}")
    return True
