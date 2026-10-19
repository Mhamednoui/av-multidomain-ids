"""Tampa BSM (D14): remove duplicate receptions, link per-RSU ids into physical vehicles, cut passages (WP5 S1b).

Purpose: in the public Tampa sample coreData_id is assigned per RSU, so one over-the-air BSM that several RSUs heard appears
once per RSU under different ids (S3 finding). This module (1) deduplicates the copies, (2) links ids into physical vehicles,
(3) cuts each vehicle into passages (silence > SILENCE_S) which are the grouping unit of the time-block split.
Inputs: the raw Tampa CSV (v2x.adapters.TAMPA_CSV). Outputs: tables / dicts used by adapters.load_tampa and tools/WP5_S1b_*.py.
Evidence for the rules (numbers in results/WP5/s1b_dedup_link.json):
 - msgCnt is a per-vehicle counter: between consecutive messages of one linked vehicle it advances by ~10 per second (99.4% within +-1),
   so it survives an id change and is a linking cue.
 - Linking is conservative: tier 1 = ids that share a bit-identical message (certain), tier 2 = unique mutual continuity candidate.
   Merging two different vehicles never leaks across a split (groups only get larger); a missed link is covered by the 30 s guard.
References: SAE J2735 BSM (msgCnt 0..127, secMark ms in the minute); notes/WP5_v2x.md 'S1b ... acceptance rule'.
Run readers with python -I on untrusted data.
"""
import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

GAP_MAX = 5.0          # s, same as the Tampa track-gap rule (adapters.TAMPA_GAP_S)
POS_TOL0, POS_TOL2 = 2.0, 0.5       # m: dead-reckoning tolerance 2 + 0.5 g^2
SPD_TOL0, SPD_TOL1 = 1.0, 1.5       # m/s: |dv| <= 1 + 1.5 g
HEAD_TOL_DEG = 20.0
V_HEAD_MIN = 3.0
MSGCNT_TOL = 2
RATE_HZ = 10.0
SILENCE_S = 120.0      # a vehicle silent for longer starts a new passage
TOL_DT, TOL_POS, TOL_SPD, TOL_HEAD = 0.002, 1.0, 0.1, 1.0     # tolerance variant of the copy rule (measurement only)
_M_PER_DEG = 111320.0
LAT0, LON0 = 27.95, -82.45

RAW_COLS = ["metadata_recordGeneratedAt", "metadata_RSUID", "coreData_id", "coreData_msgCnt", "coreData_secMark",
            "coreData_lat", "coreData_long", "coreData_accelset_yaw", "coreData_accelset_long", "coreData_speed",
            "coreData_heading"]
KEY = ["msgCnt", "t", "lat_i", "lon_i", "spd_i", "hd_i"]


def gen_time(rec, sec_mark_ms):
    """Generation time (s of the UTC day) from the RSU record time (integer s) and secMark (ms in the minute)."""
    rec_s = rec % 60
    sm = np.asarray(sec_mark_ms, float) / 1000.0
    gen = ((rec - rec_s) % 86400).to_numpy(dtype=float) + sm
    gen = np.where(sm - rec_s > 30, gen - 60, gen)       # message made just before the minute turned
    gen = np.where(rec_s - sm > 30, gen + 60, gen)
    return gen % 86400.0


def read_raw(path) -> pd.DataFrame:
    r = pd.read_csv(path, usecols=RAW_COLS)
    rec = pd.to_datetime(r["metadata_recordGeneratedAt"], utc=True).astype("int64") // 10 ** 9
    out = pd.DataFrame({
        "rsu": r["metadata_RSUID"].astype(str), "id": r["coreData_id"].astype(np.int64),
        "msgCnt": r["coreData_msgCnt"].astype(int), "t": gen_time(rec, r["coreData_secMark"]),
        "lat_i": r["coreData_lat"].astype(np.int64), "lon_i": r["coreData_long"].astype(np.int64),
        "spd_i": r["coreData_speed"].astype(int), "hd_i": r["coreData_heading"].astype(int),
        "acl_i": r["coreData_accelset_long"].astype(int), "yaw_i": r["coreData_accelset_yaw"].astype(int)})
    out["rec"] = rec.to_numpy(dtype=float) % 86400.0
    out["age_s"] = ((out["rec"] - out["t"] + 43200.0) % 86400.0) - 43200.0
    return out


def dedup(raw: pd.DataFrame):
    """Rows with the same transmitted message share a key. Returns (raw with column k, unique-message table).
    The kept copy is the one received first (rec, then RSU name). Adds n_copies, n_rsu, n_ids."""
    raw = raw.copy()
    raw["k"] = raw.groupby(KEY, sort=False).ngroup()
    g = raw.groupby("k")
    raw["n_copies"] = g["id"].transform("size")
    raw["n_ids"] = g["id"].transform("nunique")
    raw["n_rsu"] = g["rsu"].transform("nunique")
    u = raw.sort_values(["k", "rec", "rsu"], kind="stable").drop_duplicates("k").sort_values("t", kind="stable")
    return raw, u.reset_index(drop=True)


def copy_stats(raw: pd.DataFrame) -> dict:
    u = raw.drop_duplicates("k")
    ids_per = u["n_ids"]
    both = raw.groupby(["msgCnt", "t"])
    multi = both["id"].transform("nunique") > 1
    nun = raw[multi].groupby(["msgCnt", "t"])[["lat_i", "lon_i", "spd_i", "hd_i"]].nunique()
    return {"rows": int(len(raw)), "unique_messages": int(len(u)),
            "duplicate_rows": int(len(raw) - len(u)), "duplicate_fraction": float(1 - len(u) / len(raw)),
            "mean_copies_per_message": float(len(raw) / len(u)),
            "copies_histogram": {int(k): int(v) for k, v in u["n_copies"].value_counts().sort_index().items()},
            "messages_heard_by_more_than_one_rsu": int((u["n_rsu"] > 1).sum()),
            "id_repeated_inside_a_key": int(raw.duplicated(["k", "id"]).sum()),
            "msgCnt_t_groups_with_several_ids": int(len(nun)),
            "msgCnt_t_groups_with_several_ids_and_different_content": int((nun.max(axis=1) > 1).sum()) if len(nun) else 0,
            "copy_receive_time_spread_s": {int(k): int(v) for k, v in
                                           raw[raw["n_copies"] > 1].groupby("k")["rec"].agg(lambda s: s.max() - s.min())
                                           .round().value_counts().sort_index().items()}}


def tolerance_extra_merges(u: pd.DataFrame) -> dict:
    """Pairs of different unique messages that the tolerance rule would also call copies (same msgCnt, different id)."""
    u = u.sort_values(["msgCnt", "t"], kind="stable").reset_index(drop=True)
    a, b = u.iloc[:-1].reset_index(drop=True), u.iloc[1:].reset_index(drop=True)
    near = (a["msgCnt"].to_numpy() == b["msgCnt"].to_numpy()) & (np.abs(b["t"].to_numpy() - a["t"].to_numpy()) <= TOL_DT) \
        & (a["id"].to_numpy() != b["id"].to_numpy())
    dpos = np.hypot(a["lat_i"] - b["lat_i"], (a["lon_i"] - b["lon_i"]) * np.cos(np.radians(LAT0))) * 1e-7 * _M_PER_DEG
    dh = np.abs((a["hd_i"] - b["hd_i"]) * 0.0125)
    dh = np.minimum(dh, 360 - dh)
    ok = near & (dpos.to_numpy() <= TOL_POS) & (np.abs(a["spd_i"] - b["spd_i"]).to_numpy() * 0.02 <= TOL_SPD) & (dh.to_numpy() <= TOL_HEAD)
    return {"pairs_same_msgCnt_within_2ms_different_id": int(near.sum()), "extra_merges_by_tolerance_rule": int(ok.sum()),
            "extra_fraction_of_unique_messages": float(ok.sum() / len(u))}


def id_components(raw: pd.DataFrame):
    """Tier 1: ids connected by a shared bit-identical message. Returns (id -> component label Series, n components)."""
    ids = pd.Index(sorted(raw["id"].unique()))
    code = ids.get_indexer(raw["id"])
    a = pd.DataFrame({"k": raw["k"].to_numpy(), "i": code}).drop_duplicates(["k", "i"])
    first = a.groupby("k")["i"].transform("first").to_numpy()
    n = len(ids)
    m = coo_matrix((np.ones(len(a)), (a["i"].to_numpy(), first)), shape=(n, n))
    nc, lab = connected_components(m, directed=False)
    return pd.Series(lab, index=ids), int(nc)


# ------------------------------------------------------------------------------------------------------------------
def _xy(lat_i, lon_i):
    return ((np.asarray(lon_i, float) * 1e-7 - LON0) * _M_PER_DEG * np.cos(np.radians(LAT0)),
            (np.asarray(lat_i, float) * 1e-7 - LAT0) * _M_PER_DEG)


def _end_state(row):
    x, y = _xy(row["lat_i"], row["lon_i"])
    v = row["spd_i"] * 0.02
    h = np.pi / 2 - np.radians(row["hd_i"] * 0.0125)
    return dict(t=row["t"], x=float(x), y=float(y), v=float(v), h=float(h), hd=row["hd_i"] * 0.0125, cnt=int(row["msgCnt"]))


def endpoints(u: pd.DataFrame, label_col="lab"):
    """First and last unique message of every component, as dicts."""
    s = u.sort_values("t", kind="stable")
    first = s.groupby(label_col).head(1).set_index(label_col)
    last = s.groupby(label_col).tail(1).set_index(label_col)
    return ({l: _end_state(r) for l, r in first.iterrows()}, {l: _end_state(r) for l, r in last.iterrows()})


def gate(a_end: dict, b_start: dict) -> dict:
    """Continuity test between the last message of A and the first message of B. Returns the measures and `ok`."""
    g = b_start["t"] - a_end["t"]
    if not (0 < g <= GAP_MAX):
        return {"ok": False, "gap": g}
    px = a_end["x"] + a_end["v"] * np.cos(a_end["h"]) * g
    py = a_end["y"] + a_end["v"] * np.sin(a_end["h"]) * g
    err = float(np.hypot(b_start["x"] - px, b_start["y"] - py))
    dv = abs(b_start["v"] - a_end["v"])
    dh = abs(b_start["hd"] - a_end["hd"])
    dh = min(dh, 360 - dh)
    mc = ((b_start["cnt"] - a_end["cnt"] - round(g * RATE_HZ) + 64) % 128) - 64
    moving = a_end["v"] >= V_HEAD_MIN and b_start["v"] >= V_HEAD_MIN
    ok = (err <= POS_TOL0 + POS_TOL2 * g * g and dv <= SPD_TOL0 + SPD_TOL1 * g and (dh <= HEAD_TOL_DEG or not moving)
          and abs(mc) <= MSGCNT_TOL)
    return {"ok": bool(ok), "gap": float(g), "extrap_err_m": err, "dv": float(dv), "dhead_deg": float(dh), "msgcnt_err": int(mc)}


def candidate_table(ends: dict, starts: dict, skip=()):
    """All gate-passing (A end -> B start) pairs among components. Returns list of dicts."""
    out = []
    for a, ea in ends.items():
        for b, sb in starts.items():
            if a == b or a in skip or b in skip:
                continue
            r = gate(ea, sb)
            if r["ok"]:
                out.append({"a": a, "b": b, **r})
    return out


def mutual_unique(cands):
    """Candidates that are the only gate-passing one for their A end and for their B start."""
    ca, cb = {}, {}
    for c in cands:
        ca[c["a"]] = ca.get(c["a"], 0) + 1
        cb[c["b"]] = cb.get(c["b"], 0) + 1
    uniq = [c for c in cands if ca[c["a"]] == 1 and cb[c["b"]] == 1]
    return uniq, [c for c in cands if c not in uniq]


def link_continuity(u: pd.DataFrame, label_col="lab", max_pass=6):
    """Tier 2: repeatedly link unique mutual continuity candidates. Modifies u[label_col] (merged labels).
    Returns (links list with pass number, list of ambiguous candidate dicts of the last pass)."""
    links, amb = [], []
    for p in range(max_pass):
        starts, ends = endpoints(u, label_col)
        cands = candidate_table(ends, starts)
        uniq, amb = mutual_unique(cands)
        if not uniq:
            break
        remap = {}
        for c in uniq:
            remap[c["b"]] = c["a"]
            links.append({**c, "pass": p + 1})
        # chains within one pass: resolve a->b, b->c by following the map
        def root(l):
            while l in remap:
                l = remap[l]
            return l
        u[label_col] = [root(l) for l in u[label_col].to_numpy()]
    return links, amb


def passages(u: pd.DataFrame, label_col="vlab", silence=SILENCE_S):
    """Passage index per row: a new passage whenever a vehicle is silent for more than `silence` s. u sorted by t."""
    s = u.sort_values([label_col, "t"], kind="stable")
    new = (s.groupby(label_col)["t"].diff() > silence).astype(int)
    p = new.groupby(s[label_col]).cumsum()
    return p.reindex(u.index)


# ------------------------------------------------------------------------------------------------------------------
def build(path, link=True):
    """Full pipeline. Returns (messages, info): messages = unique messages with columns
    id, rsu, msgCnt, t, lat_i, lon_i, spd_i, hd_i, acl_i, yaw_i, age_s, n_copies, n_rsu, comp (tier 1), vlab (physical vehicle),
    passage (index), sender (passage id string)."""
    raw = read_raw(path)
    raw, u = dedup(raw)
    comp, nc = id_components(raw)
    u["lab"] = u["id"].map(comp).to_numpy()
    n_tier1 = int(u["lab"].nunique())
    u["comp"] = u["lab"]
    links, amb = (link_continuity(u) if link else ([], []))
    u["vlab"] = u["lab"]
    u["passage"] = passages(u).to_numpy().astype(int)
    order = {l: i for i, l in enumerate(u.groupby("vlab")["t"].min().sort_values().index)}
    u["sender"] = ["P%03d_%d" % (order[v], p) for v, p in zip(u["vlab"], u["passage"])]
    u["vehicle"] = ["V%03d" % order[v] for v in u["vlab"]]
    info = {"ids": int(raw["id"].nunique()), "tier1_components": n_tier1, "tier2_links": links,
            "n_tier2_links": len(links), "ambiguous_candidates_last_pass": amb,
            "physical_vehicles": int(u["vlab"].nunique()), "passages": int(u["sender"].nunique()),
            "copy_stats": copy_stats(raw), "tolerance_rule": tolerance_extra_merges(u)}
    return u, info
