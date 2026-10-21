"""WP2 S3: L2a clock-skew layer (CIDS) on ROAD, Car-Hacking and D11, on top of the S2 L1 rules.

Usage (from codes_v3/): python -u -W ignore tools/WP2_S3_run.py road|carhacking|d11 [set_01 ...]
Outputs: results/WP2/s3_road.json, s3_carhacking.json, s3_d11_<set>.json, harness tables in results/WP2/s3_harness/,
window tables results/WP2/s3_*_windows_*.csv.gz, skew profiles results/WP2/s3_profiles/.
Protocol and acceptance rule: notes/WP2_can.md, "S3 start" (written before any result). Uses the cache of
tools/WP2_S2_cache.py (../data_extra/WP2_S2_cache, no new cache). Test files are scored once, after the choices on validation.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from can import adapters as A
from can import l1 as L
from can import l1_exp as E
from can import l2a_exp as X
from can import l2a_skew as K
from can.splits import block_index
from WP2_S2_run import (BUDGET, D11_CAL_S, D11_PROFILE_S, D11_SKIP_S, MIN_ELIGIBLE, Experiment, dump,
                        fit_profile, frame_summary)
from common.config import RESULTS

OUT = RESULTS / "WP2"
HARNESS = OUT / "s3_harness"
PROFILES = OUT / "s3_profiles"
ALLV = list(range(len(K.VARIANTS)))


def regime_report(ex, R, tally, wrows, val_tbl, first_inj, tag, budget, method):
    tbl = E.window_table(wrows)
    ev = X.eval_windows2(R, val_tbl, tbl, ex.codes, first_inj, tag, HARNESS, budget, method)
    ev["frame"] = frame_summary(tally.to_dict(), R.names + ["combined"])
    ev["frame_tally"] = tally.to_dict()
    ev["thresholds"] = {"window": {n: R.wr[n].threshold for n in R.names}, "frame": {n: R.fr[n].threshold for n in R.names},
                        "frame_combined": R.thr_comb}
    return ev, tbl


def skew_profile_info(profs, v):
    S = profs[v]
    return {"summary": S.summary(), "n_batches": S.n_batches.tolist(), "scored": S.scored.tolist(), "ids": S.ids.tolist(),
            "T": S.T.tolist()}


# ------------------------------------------------------------------ ROAD
def run_road():
    t0 = time.time()
    caps = A.road_captures()
    caps = caps[caps["usable"]].sort_values("name").reset_index(drop=True)
    role_of = {"train": E.ROLE_FIT, "val": E.ROLE_VAL, "test": E.ROLE_TEST}
    ex = Experiment("road")
    ex.groups = {i: n for i, n in enumerate(caps["name"])}

    def loadF(i, windows=True):
        n = caps.loc[i, "name"]
        raw = E.load_cached("road", n)
        clean = E.lead_clean(raw["t"], raw["label"])
        role = np.full(len(raw["t"]), role_of[caps.loc[i, "part"]], np.int8)
        return raw, E.make_F(raw, ex.codes, i, role, clean, windows)

    train_idx = list(caps.index[caps["part"] == "train"])

    def fit_loader():
        for i in train_idx:
            raw = E.load_cached("road", caps.loc[i, "name"])
            clean = E.lead_clean(raw["t"], raw["label"])
            yield L.make_features(raw["t"], raw["id"], raw["dlc"], windows=False), clean

    fit_items = []
    for i in train_idx:
        raw = E.load_cached("road", caps.loc[i, "name"])
        fit_items.append((raw, E.lead_clean(raw["t"], raw["label"])))
    profile = fit_profile(fit_items)
    del fit_items
    profs = X.fit_skew(profile, fit_loader)
    print(f"profiles L1 {profile.summary()} skew {profs[0].summary()} ({time.time() - t0:.0f}s)", flush=True)

    store = E.Store()
    for i in caps.index[caps["part"] == "val"]:
        _, F = loadF(i)
        raws = E.raw_frames(profile, F, range(len(L.VARIANTS)))
        raws.update(X.skew_raws(profs, F, ALLV))
        store.add(F, raws, E.ROLE_VAL)
        print(f"  val {caps.loc[i, 'name']} ({time.time() - t0:.0f}s)", flush=True)
    store.done()
    sel = E.select_variant(profile, store, ex.codes)
    k = sel["chosen"]
    selS = X.select_skew(store, ex.codes, ALLV)
    v = selS["chosen"]
    print("L1 variant", k, "skew variant", K.VARIANT_NAMES[v],
          {K.VARIANT_NAMES[int(kk)]: round(x["mean_recall"], 3) for kk, x in selS["variants"].items()}, flush=True)
    regimes = {}
    base = E.build_regime("A", profile, store, k, 0.01)
    regimes["A"] = (X.Regime2(base, store, profs[v], v, 0.01), 0.01)
    prof2 = L.Profile.from_dict(profile.to_dict())
    base2 = E.build_regime("Ab0.001", prof2, store, k, 0.001)
    regimes["Ab0.001"] = (X.Regime2(base2, store, profs[v], v, 0.001), 0.001)
    tallies = {rn: E.Tally(r[0].names) for rn, r in regimes.items()}
    wrows = {rn: [] for rn in regimes}
    for i in caps.index[caps["part"] == "test"]:
        _, F = loadF(i)
        for rn, (R, _) in regimes.items():
            X.score_file2(R, F, caps.loc[i, "name"], tallies[rn], wrows[rn], ex.codes)
        print(f"  scored {caps.loc[i, 'name']} ({time.time() - t0:.0f}s)", flush=True)
    val_tbl = X.store_table2(store, ex.groups, k, v)
    res = {}
    for rn, (R, b) in regimes.items():
        first_inj = {g: f["first_inj_t"] for g, f in tallies[rn].files.items()}
        res[rn], tbl = regime_report(ex, R, tallies[rn], wrows[rn], val_tbl, first_inj, f"road_{rn}", b, "auto")
        tbl.to_csv(OUT / f"s3_road_windows_test_{rn}.csv.gz", index=False)
    val_tbl.to_csv(OUT / "s3_road_windows_val.csv.gz", index=False)
    out = {"experiment": "road", "l1_variant_selection": sel, "skew_variant_selection": selS,
           "l1_profile": profile.summary(), "skew_profile": skew_profile_info(profs, v), "regimes": res,
           "attack_names": ex.codes.names, "seconds": time.time() - t0}
    dump(out, OUT / "s3_road.json")
    dump(profs[v].to_dict(), PROFILES / "road.json")
    print("done road", flush=True)


# ------------------------------------------------------------------ Car-Hacking
def run_carhacking():
    t0 = time.time()
    names = list(A.CARHACKING_FILES)
    blocks = json.load(open(OUT / "splits_carhacking.json"))["blocks"]
    lut = {"train": E.ROLE_FIT, "val": E.ROLE_VAL, "test": E.ROLE_TEST}
    ex = Experiment("carhacking")
    ex.groups = {i: n for i, n in enumerate(names)}

    def loadF(i, windows=True):
        n = names[i]
        raw = E.load_cached("carhacking", n)
        bi = block_index(len(raw["t"]))
        has = np.zeros(100, bool)
        has[np.unique(bi[raw["label"] != 0])] = True
        role = np.array([lut[p] for p in blocks[n]], np.int8)[bi]
        return raw, E.make_F(raw, ex.codes, i, role, ~has[bi], windows)

    def fit_loader():
        for i in range(len(names)):
            _, F = loadF(i, windows=False)
            yield F, (F["role"] == E.ROLE_FIT) & F["clean"]

    b1 = L.ProfileBuilder()
    for F, m in fit_loader():
        b1.add(F["id"][m], F["dlc"][m], F["dt_id"][m])
    profile = b1.finish()
    profs = X.fit_skew(profile, fit_loader)
    print(f"profiles L1 {profile.summary()} skew {profs[0].summary()} ({time.time() - t0:.0f}s)", flush=True)
    store = E.Store()
    for i in range(len(names)):
        _, F = loadF(i)
        raws = E.raw_frames(profile, F, range(len(L.VARIANTS)))
        raws.update(X.skew_raws(profs, F, ALLV))
        store.add(F, raws, E.ROLE_VAL)
    store.done()
    sel = E.select_variant(profile, store, ex.codes)
    k = sel["chosen"]
    selS = X.select_skew(store, ex.codes, ALLV, only_masquerade=False)
    v = selS["chosen"]
    print("L1 variant", k, "skew variant", K.VARIANT_NAMES[v],
          {K.VARIANT_NAMES[int(kk)]: round(x["mean_recall"], 3) for kk, x in selS["variants"].items()}, flush=True)
    base = E.build_regime("A", profile, store, k, 0.01)
    R = X.Regime2(base, store, profs[v], v, 0.01)
    tally = E.Tally(R.names)
    wrows = []
    for i in range(len(names)):
        _, F = loadF(i)
        X.score_file2(R, F, names[i], tally, wrows, ex.codes)
        print(f"  scored {names[i]} ({time.time() - t0:.0f}s)", flush=True)
    val_tbl = X.store_table2(store, ex.groups, k, v)
    first_inj = {g: f["first_inj_t"] for g, f in tally.files.items()}
    ev, tbl = regime_report(ex, R, tally, wrows, val_tbl, first_inj, "carhacking_A", 0.01, "auto")
    tbl.to_csv(OUT / "s3_carhacking_windows_test.csv.gz", index=False)
    out = {"experiment": "carhacking", "l1_variant_selection": sel, "skew_variant_selection": selS,
           "skew_profile": skew_profile_info(profs, v), "regimes": {"A": ev}, "attack_names": ex.codes.names,
           "seconds": time.time() - t0,
           "note": "test frames are interleaved time blocks; the skew filter runs continuously over each file"}
    dump(out, OUT / "s3_carhacking.json")
    dump(profs[v].to_dict(), PROFILES / "carhacking.json")
    print("done carhacking", flush=True)


if __name__ == "__main__":
    which = sys.argv[1]
    if which == "road":
        run_road()
    elif which == "carhacking":
        run_carhacking()
    elif which == "d11":
        import WP2_S3_d11
        for s in sys.argv[2:]:
            WP2_S3_d11.run_d11(s)
