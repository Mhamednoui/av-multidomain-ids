"""WP2 S3: L2a clock-skew layer on D11 (can-train-and-test), both calibration regimes, on top of the S2 L1 rules.

Called by tools/WP2_S3_run.py d11 set_0N. Same structure as WP2_S2_run.run_d11 (regime A zero-shot: statistics and thresholds from
the training vehicle; regime B on-vehicle: first 30 s -> statistics, 30-60 s -> thresholds, scored from 60 s), plus the skew
layer. D11 timestamps have a synthetic epoch and inversions near injected frames: dt_clipped only (never the sign).
Output: results/WP2/s3_d11_<set>.json (resumable per set).
"""
import json
import time

import numpy as np

import WP2_S3_run as R3
from WP2_S2_run import (BUDGET, D11_CAL_S, D11_PROFILE_S, D11_SKIP_S, MIN_ELIGIBLE, Experiment, dump, fit_profile)
from can import l1 as L
from can import l1_exp as E
from can import l2a_exp as X
from can import l2a_skew as K
from common.config import RESULTS

OUT = RESULTS / "WP2"


def run_d11(set_name):
    t0 = time.time()
    outp = OUT / f"s3_d11_{set_name}.json"
    if outp.exists():
        print("skip", set_name, "done")
        return
    sp = json.load(open(OUT / "splits_d11.json"))["splits"][set_name]
    vehicles = json.load(open(OUT / "s1_d11_vehicles.json"))
    codes = E.AttCodes()
    ex = Experiment(f"d11_{set_name}")
    all_caps = sorted({c for k, v in sp.items() if k != "excluded_duplicates" for c in v})
    ex.groups = {i: c for i, c in enumerate(all_caps)}
    base_of = {c: i for i, c in enumerate(all_caps)}
    ex.codes = codes
    ALLV = R3.ALLV

    def cname(c):
        return c.replace("/", "__")

    def loadF(c, role_fn, windows=True):
        raw = E.load_cached("d11", cname(c))
        clean = E.lead_clean(raw["t"], raw["label"])
        tm = np.maximum.accumulate(raw["t"])
        return raw, E.make_F(raw, codes, base_of[c], role_fn(tm), clean, windows)

    const = lambda r: (lambda tm: np.full(len(tm), r, np.int8))

    def fit_loader_A():
        for c in sp["train"]:
            raw = E.load_cached("d11", cname(c))
            yield L.make_features(raw["t"], raw["id"], raw["dlc"], windows=False), E.lead_clean(raw["t"], raw["label"])

    fit_items = []
    for c in sp["train"]:
        raw = E.load_cached("d11", cname(c))
        fit_items.append((raw, E.lead_clean(raw["t"], raw["label"])))
    profA = fit_profile(fit_items)
    del fit_items
    skA = X.fit_skew(profA, fit_loader_A)
    print(f"{set_name} profiles L1 {profA.summary()} skew {skA[0].summary()} ({time.time() - t0:.0f}s)", flush=True)
    store = E.Store()
    for c in sp["val"]:
        _, F = loadF(c, const(E.ROLE_VAL))
        raws = E.raw_frames(profA, F, range(len(L.VARIANTS)))
        raws.update(X.skew_raws(skA, F, ALLV))
        store.add(F, raws, E.ROLE_VAL)
    store.done()
    sel = E.select_variant(profA, store, codes)
    k = sel["chosen"]
    selS = X.select_skew(store, codes, ALLV, only_masquerade=False)
    v = selS["chosen"]
    print(f"{set_name} L1 variant {k} skew variant {K.VARIANT_NAMES[v]}",
          {K.VARIANT_NAMES[int(kk)]: round(x["mean_recall"], 3) for kk, x in selS["variants"].items()},
          f"({time.time() - t0:.0f}s)", flush=True)
    baseA = E.build_regime("A", profA, store, k, BUDGET)
    regA = X.Regime2(baseA, store, skA[v], v, BUDGET)
    val_tbl = X.store_table2(store, ex.groups, k, v)
    res = {"experiment": f"d11_{set_name}", "l1_variant_selection": sel, "skew_variant_selection": selS,
           "profile_A": profA.summary(), "skew_profile_A": R3.skew_profile_info(skA, v),
           "vehicle_train": vehicles[sp["train"][0]]["vehicle"], "subsets": {}, "budget": BUDGET,
           "cal_regime_b": {"profile_s": D11_PROFILE_S, "threshold_s": D11_CAL_S - D11_PROFILE_S,
                            "scored_from_s": D11_SKIP_S, "min_eligible_files": MIN_ELIGIBLE}}
    for sub in ("test_01", "test_02", "test_03", "test_04"):
        files = sp[sub]
        veh = sorted({vehicles[c]["vehicle"] for c in files})
        elig = []
        for c in files:
            raw = E.load_cached("d11", cname(c))
            fi = E.first_injected(raw)
            if fi is None or fi >= D11_SKIP_S:
                elig.append(c)
        regimes = {"A": regA}
        info = {"vehicle": veh, "n_files": len(files), "n_eligible": len(elig), "eligible": elig}
        valB = None
        if len(elig) >= MIN_ELIGIBLE:
            def fit_loader_B():
                for c in elig:
                    raw = E.load_cached("d11", cname(c))
                    tm = np.maximum.accumulate(raw["t"])
                    yield (L.make_features(raw["t"], raw["id"], raw["dlc"], windows=False),
                           E.lead_clean(raw["t"], raw["label"]) & (tm < D11_PROFILE_S))

            items = []
            for F, m in fit_loader_B():
                items.append(({"t": F["t"], "id": F["id"], "dlc": F["dlc"]}, m))
            profB = fit_profile(items)
            del items
            skB = X.fit_skew(profB, fit_loader_B, [v])
            stB = E.Store()
            for c in elig:
                def rolefn(tm):
                    r = np.full(len(tm), E.ROLE_NONE, np.int8)
                    r[(tm >= D11_PROFILE_S) & (tm < D11_CAL_S)] = E.ROLE_VAL
                    return r
                _, F = loadF(c, rolefn)
                raws = E.raw_frames(profB, F, [k])
                raws.update(X.skew_raws(skB, F, [v]))
                stB.add(F, raws, E.ROLE_VAL)
            stB.done()
            baseB = E.build_regime("B", profB, stB, k, BUDGET)
            regimes["B"] = X.Regime2(baseB, stB, skB[v], v, BUDGET)
            valB = X.store_table2(stB, ex.groups, k, v)
            info["profile_B"] = profB.summary()
            info["skew_profile_B"] = R3.skew_profile_info(skB, v)
            info["cal_B"] = {"frames": int(len(stB.mf["clean"])), "clean_frames": int(stB.mf["clean"].sum()),
                             "windows": int(len(stB.mw["clean"])), "clean_windows": int(stB.mw["clean"].sum())}
            print(f"{set_name} {sub} B calibrated on {info['cal_B']}, skew {skB[v].summary()} ({time.time() - t0:.0f}s)", flush=True)
        tallies = {rn: E.Tally(r.names) for rn, r in regimes.items()}
        wrows = {rn: [] for rn in regimes}
        elig_set = set(elig)
        cover = {"frames": 0, "frames_on_scored_ids": 0}
        for c in files:
            def rolefn_t(tm, c=c):
                r = np.full(len(tm), E.ROLE_TEST, np.int8)
                if c in elig_set:
                    r[tm < D11_SKIP_S] = E.ROLE_NONE
                return r
            _, F = loadF(c, rolefn_t)
            for rn, R in regimes.items():
                X.score_file2(R, F, c, tallies[rn], wrows[rn], codes)
            cv = X.coverage(skA, F, F["role"] == E.ROLE_TEST, v)
            cover["frames"] += cv["frames"]
            cover["frames_on_scored_ids"] += cv["frames_on_scored_ids"]
            print(f"  {c} ({time.time() - t0:.0f}s)", flush=True)
        info["coverage_A"] = cover
        info["regimes"] = {}
        for rn, R in regimes.items():
            vt = val_tbl if rn == "A" else valB
            first_inj = {g: f["first_inj_t"] for g, f in tallies[rn].files.items()}
            ev, _ = R3.regime_report(ex, R, tallies[rn], wrows[rn], vt, first_inj, f"d11_{set_name}_{sub}_{rn}", BUDGET,
                                     "auto" if rn == "A" else "noisy_or")
            info["regimes"][rn] = ev
        res["subsets"][sub] = info
    res["attack_names"] = codes.names
    res["seconds"] = time.time() - t0
    dump(skA[v].to_dict(), R3.PROFILES / f"d11_{set_name}_A.json")
    dump(res, outp)
    print("done", set_name, f"({time.time() - t0:.0f}s)", flush=True)
