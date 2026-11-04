"""WP9 B2: leak-free splits for a B2 flow table and the lock file locks/WP9_<table>.json (written BEFORE any training).

Protocols (all on deduplicated flows; definitions fixed in notes/WP9_B2.md before any result):
  T  time block: per period (attack window / benign stretch between, WP4 definition) in time order:
     train 0-50% | gap 1 min | val 50-65% | gap | test 65-80% | gap | reserve (last 20% = the v3/WP4/WP8 D10 test rows, never used by B2).
     Periods shorter than 5 min go to train.
  G  5-tuple group (Moczkodan & Ragab): hash of (src ip, dst ip, src port, dst port, protocol) -> 70 / 10 / 20, all days pooled.
  B  block group: per period, blocks of 5 min; blocks permuted by hash, then train / val / test (about 70/10/20, at least one test block
     when the period has >= 2 blocks and one val block when >= 4); flows within 1 min of an edge between blocks of different parts are 'gap'.
Part codes: 0 train, 1 val, 2 test, 3 gap, 4 reserve.
Also: bootstrap group id = (day, 10-minute block) for every row.
Run (codes_v3): python -u -W ignore -I tools/WP9_B2_splits.py <table>
"""
import hashlib, json, os, sys
import numpy as np, pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from network import flows as F

CACHE = os.path.join(ROOT, "..", "data_extra", "cache_v3", "WP9", "B2")
SALT = 20261104
PARTS = ["train", "val", "test", "gap", "reserve"]
GAP = np.timedelta64(60, "s")


def periods_of_day(ts, fam):
    """Period edges for one day (same construction as network.flows.time_split). Returns period id per row (-1 where ts is NaT)."""
    tsv = pd.Series(ts).reset_index(drop=True)
    per = np.full(len(tsv), -1, dtype=int)
    ok = tsv.notna().to_numpy()
    idx = np.where(ok)[0]
    tv = tsv[ok].to_numpy().astype("datetime64[ns]")
    wins = sorted(F.attack_windows(tv, np.asarray(fam)[ok]), key=lambda w: w[0])
    edges, cur = [], tv.min()
    for (a, b, f) in wins:
        a = max(a, cur)
        if b <= a:
            continue
        if a > cur:
            edges.append((cur, a))
        edges.append((a, b))
        cur = b
    end = tv.max() + np.timedelta64(1, "s")
    if end > cur:
        edges.append((cur, end))
    for pid, (a, b) in enumerate(edges):
        per[idx[(tv >= a) & (tv < b)]] = pid
    return per, edges


def split_T(d, per):
    part = np.full(len(d), 3, dtype=np.int8)
    ts = d["ts"].to_numpy().astype("datetime64[ns]")
    key = d["day"].astype(str).to_numpy()
    for day in np.unique(key):
        for p in np.unique(per[key == day]):
            if p < 0:
                continue
            ii = np.where((key == day) & (per == p))[0]
            tt = ts[ii]
            if (tt.max() - tt.min()) / np.timedelta64(1, "m") < 5:
                part[ii] = 0
                continue
            q = np.quantile(tt.astype("int64"), [0.5, 0.65, 0.8]).astype("int64")
            c1, c2, c3 = [np.datetime64(int(v), "ns") for v in q]
            s = np.full(len(tt), 3, dtype=np.int8)
            s[tt < c1 - GAP] = 0
            s[(tt >= c1) & (tt < c2 - GAP)] = 1
            s[(tt >= c2) & (tt < c3 - GAP)] = 2
            s[tt >= c3] = 4
            part[ii] = s
    return part


def hash_str(a):
    return pd.util.hash_array(np.asarray(a, dtype=object)).astype(np.uint64)


def split_G(d):
    k = d["src_ip"].astype(str) + "|" + d["dst_ip"].astype(str) + "|" + d["src_port"].astype(str) + "|" + d["dst_port"].astype(str) + "|" + d["protocol"].astype(str)
    h = (hash_str(k.to_numpy()) + np.uint64(SALT)) % np.uint64(100)
    h = (pd.util.hash_array(h.astype(np.int64)) % np.uint64(100)).astype(int)
    return np.where(h < 70, 0, np.where(h < 80, 1, 2)).astype(np.int8)


def split_B(d, per):
    part = np.full(len(d), 3, dtype=np.int8)
    ts = d["ts"].to_numpy().astype("datetime64[ns]")
    key = d["day"].astype(str).to_numpy()
    blk = np.timedelta64(5, "m")
    for day in np.unique(key):
        for p in np.unique(per[key == day]):
            if p < 0:
                continue
            ii = np.where((key == day) & (per == p))[0]
            tt = ts[ii]
            t0 = tt.min()
            b = ((tt - t0) // blk).astype(int)
            nb = b.max() + 1
            if nb == 1:
                part[ii] = 0
                continue
            rk = np.argsort(pd.util.hash_array(np.array(["%s|%s|%d" % (day, p, i) for i in range(nb)], dtype=object)) + np.uint64(SALT))
            n_te = max(1, int(round(0.2 * nb)))
            n_va = 0 if nb < 4 else max(1, int(round(0.1 * nb)))
            blockpart = np.zeros(nb, dtype=np.int8)
            blockpart[rk[:n_te]] = 2
            blockpart[rk[n_te:n_te + n_va]] = 1
            s = blockpart[b].astype(np.int8)
            # gap: within 1 min of an edge to a block of another part
            tb = (tt - t0) - b * blk
            nxt = np.clip(b + 1, 0, nb - 1)
            prv = np.clip(b - 1, 0, nb - 1)
            near_end = (blk - tb < GAP) & (blockpart[nxt] != s) & (b + 1 < nb)
            near_start = (tb < GAP) & (blockpart[prv] != s) & (b > 0)
            s[near_end | near_start] = 3
            part[ii] = s
    return part


def boot_group(d):
    t = d["ts"].dt.floor("10min").astype("int64").to_numpy()
    return pd.factorize(d["day"].astype(str) + "|" + pd.Series(t).astype(str))[0].astype(np.int32)


def summarise(d, part):
    out = {}
    for i, nm in enumerate(PARTS):
        m = part == i
        out[nm] = {"rows": int(m.sum()), "families": d["family"][m].value_counts().to_dict()}
    return out


def v3_overlap(d, part):
    """Rows of each B2 part by the v3 (WP4) split of the same flow (only D10o carries v3split)."""
    if "v3split" not in d or not (d["v3split"] != "").any():
        return None
    out = {}
    for i, nm in enumerate(PARTS):
        m = part == i
        out[nm] = d["v3split"][m].value_counts().to_dict()
    return out


def main(name):
    d = pd.read_pickle(os.path.join(CACHE, name + ".pkl"), compression="gzip")
    d = d.sort_values(["day", "ts"], kind="stable").reset_index(drop=True) if False else d
    per = np.full(len(d), -1, dtype=int)
    for day in d["day"].unique():
        m = (d["day"] == day).to_numpy()
        per[m], _ = periods_of_day(d["ts"][m], d["family"][m])
    prot = {"T": split_T(d, per), "G": split_G(d), "B": split_B(d, per)}
    lock = {"table": name, "rows": int(len(d)), "salt": SALT, "definition": "tools/WP9_B2_splits.py + notes/WP9_B2.md (2026-11-04)",
            "table_file_sha256": hashlib.sha256(open(os.path.join(CACHE, name + ".pkl"), "rb").read()).hexdigest(), "protocols": {}}
    np.savez_compressed(os.path.join(CACHE, name + "_parts.npz"), per=per, boot=boot_group(d), **prot)
    for k, part in prot.items():
        lock["protocols"][k] = {"parts": summarise(d, part), "part_sha256": hashlib.sha256(part.tobytes()).hexdigest(), "v3_split_overlap": v3_overlap(d, part)}
    lock["boot_group_sha256"] = hashlib.sha256(boot_group(d).tobytes()).hexdigest()
    lock["parts_file"] = "../data_extra/cache_v3/WP9/B2/%s_parts.npz" % name
    json.dump(lock, open(os.path.join(ROOT, "locks", "WP9_%s.json" % name), "w"), indent=1)
    for k in prot:
        print(k, {nm: lock["protocols"][k]["parts"][nm]["rows"] for nm in PARTS})


if __name__ == "__main__":
    main(sys.argv[1])
