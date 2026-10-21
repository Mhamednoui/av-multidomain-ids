"""WP2 S2: run the L1 specification rules on ROAD, Car-Hacking and D11 (both calibration regimes).

Usage (from codes_v3/): python -u -W ignore tools/WP2_S2_run.py road|carhacking|d11 [set_01 ...]
Outputs: results/WP2/s2_road.json, s2_carhacking.json, s2_d11_<set>.json (resumable: a finished set is skipped),
results/WP2/s2_harness/*.json|md (common-harness tables), results/WP2/s2_profiles/*.json.
Protocol: notes/WP2_can.md, section "S2 start" (acceptance rule and design fixed before any result).
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from can import adapters as A
from can import l1 as L
from can import l1_exp as E
from can.splits import block_index
from common.config import RESULTS

OUT = RESULTS / "WP2"
HARNESS = OUT / "s2_harness"
PROFILES = OUT / "s2_profiles"
BUDGET = 0.01
D11_PROFILE_S, D11_CAL_S, D11_SKIP_S = 30.0, 60.0, 60.0     # fixed before results (notes, S2 start)
MIN_ELIGIBLE = 3


def dump(obj, path):
    def conv(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (np.bool_,)):
            return bool(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        raise TypeError(type(o))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=1, default=conv))


def fit_profile(frames) -> L.Profile:
    """frames: iterable of (raw dict, fit-frame mask). Clean fit frames only."""
    b = L.ProfileBuilder()
    for raw, m in frames:
        F = L.make_features(raw["t"], raw["id"], raw["dlc"], windows=False)
        b.add(F["id"][m], F["dlc"][m], F["dt_id"][m])
    return b.finish()


def frame_summary(tally: dict, layers) -> dict:
    """Frame-level numbers from a Tally dict: recall per attack, FA on clean / all normal frames."""
    out = {}
    for n in layers:
        out[n] = {"recall_by_attack": {a: (v[1] / v[0] if v[0] else None) for a, v in tally["inj"][n].items()},
                  "fa_clean": tally["clean"][n][1] / tally["clean"][n][0] if tally["clean"][n][0] else None,
                  "fa_all_normal": tally["normal"][n][1] / tally["normal"][n][0] if tally["normal"][n][0] else None}
    return out


class Experiment:
    """Holds the shared state of one fit / val / test run (ROAD, Car-Hacking, one D11 set)."""

    def __init__(self, name):
        self.name, self.codes = name, E.AttCodes()
        self.groups = {}

    def regime_report(self, regimes, tallies, wrows, val_tbl, first_inj, method, tag):
        res = {}
        for rn, R in regimes.items():
            tbl = E.window_table(wrows[rn])
            ev = E.eval_windows(R, val_tbl[rn] if isinstance(val_tbl, dict) else val_tbl, tbl, self.codes,
                                first_inj[rn], f"{tag}_{rn}", HARNESS, BUDGET if "b" not in rn else float(rn.split("b")[1]),
                                method if not isinstance(method, dict) else method[rn])
            ev["frame"] = frame_summary(tallies[rn].to_dict(), E.RULE_NAMES + ["combined"])
            ev["frame_tally"] = tallies[rn].to_dict()
            ev["thresholds"] = {"window": {n: R.wr[n].threshold for n in E.RULE_NAMES},
                                "frame": {n: R.fr[n].threshold for n in E.RULE_NAMES}, "frame_combined": R.thr_comb}
            res[rn] = ev
        return res


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

    fit_items = []
    for i in caps.index[caps["part"] == "train"]:
        raw = E.load_cached("road", caps.loc[i, "name"])
        fit_items.append((raw, E.lead_clean(raw["t"], raw["label"])))
    profile = fit_profile(fit_items)
    del fit_items
    print(f"profile {profile.summary()} ({time.time() - t0:.0f}s)", flush=True)

    store = E.Store()
    for i in caps.index[caps["part"] == "val"]:
        _, F = loadF(i)
        store.add(F, E.raw_frames(profile, F, range(len(L.VARIANTS))), E.ROLE_VAL)
    store.done()
    sel = E.select_variant(profile, store, ex.codes)
    k = sel["chosen"]
    print("variant", sel["chosen"], {kk: round(v["mean_recall"], 3) for kk, v in sel["variants"].items()},
          f"({time.time() - t0:.0f}s)", flush=True)
    regimes = {"A": E.build_regime("A", profile, store, k, 0.01)}
    # extra operating point: 0.1% (thresholds still from validation; with ~600 clean val windows this is the max)
    prof2 = L.Profile.from_dict(profile.to_dict())
    regimes["Ab0.001"] = E.build_regime("Ab0.001", prof2, store, k, 0.001)
    tallies = {rn: E.Tally(E.RULE_NAMES) for rn in regimes}
    wrows = {rn: [] for rn in regimes}
    for i in caps.index[caps["part"] == "test"]:
        _, F = loadF(i)
        E.score_file(regimes, F, caps.loc[i, "name"], tallies, wrows, ex.codes)
        print(f"  scored {caps.loc[i, 'name']} ({time.time() - t0:.0f}s)", flush=True)
    val_tbl = E.store_table(store, ex.groups, k)
    first_inj = {rn: {g: f["first_inj_t"] for g, f in tallies[rn].files.items()} for rn in regimes}
    res = ex.regime_report(regimes, tallies, wrows, val_tbl, first_inj, "auto", "road")
    out = {"experiment": "road", "variant_selection": sel, "profile": profile.summary(), "regimes": res,
           "attack_names": ex.codes.names, "budget": BUDGET, "seconds": time.time() - t0}
    dump(out, OUT / "s2_road.json")
    dump(profile.to_dict(), PROFILES / "road.json")
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

    fit_items = []
    for i in range(len(names)):
        raw, F = loadF(i, windows=False)
        fit_items.append((raw, (F["role"] == E.ROLE_FIT) & F["clean"]))
    profile = fit_profile(fit_items)
    del fit_items
    print(f"profile {profile.summary()} ({time.time() - t0:.0f}s)", flush=True)
    store = E.Store()
    for i in range(len(names)):
        _, F = loadF(i)
        store.add(F, E.raw_frames(profile, F, range(len(L.VARIANTS))), E.ROLE_VAL)
    store.done()
    sel = E.select_variant(profile, store, ex.codes)
    k = sel["chosen"]
    print("variant", k, {kk: round(v["mean_recall"], 3) for kk, v in sel["variants"].items()}, flush=True)
    regimes = {"A": E.build_regime("A", profile, store, k, 0.01)}
    tallies = {"A": E.Tally(E.RULE_NAMES)}
    wrows = {"A": []}
    for i in range(len(names)):
        _, F = loadF(i)
        E.score_file(regimes, F, names[i], tallies, wrows, ex.codes)
        print(f"  scored {names[i]} ({time.time() - t0:.0f}s)", flush=True)
    val_tbl = E.store_table(store, ex.groups, k)
    first_inj = {"A": {g: f["first_inj_t"] for g, f in tallies["A"].files.items()}}
    res = ex.regime_report(regimes, tallies, wrows, val_tbl, first_inj, "auto", "carhacking")
    out = {"experiment": "carhacking", "variant_selection": sel, "profile": profile.summary(), "regimes": res,
           "attack_names": ex.codes.names, "budget": BUDGET, "seconds": time.time() - t0,
           "note": "test frames are interleaved time blocks: delay fields are not onset delays"}
    dump(out, OUT / "s2_carhacking.json")
    dump(profile.to_dict(), PROFILES / "carhacking.json")
    print("done carhacking", flush=True)


# ------------------------------------------------------------------ D11
def run_d11(set_name):
    t0 = time.time()
    outp = OUT / f"s2_d11_{set_name}.json"
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

    def cname(c):
        return c.replace("/", "__")

    def loadF(c, role_fn, windows=True):
        raw = E.load_cached("d11", cname(c))
        clean = E.lead_clean(raw["t"], raw["label"])
        tm = np.maximum.accumulate(raw["t"])
        return raw, E.make_F(raw, codes, base_of[c], role_fn(tm), clean, windows)

    const = lambda r: (lambda tm: np.full(len(tm), r, np.int8))
    # --- regime A: profile from train files, thresholds from the val hold-out files
    fit_items = []
    for c in sp["train"]:
        raw = E.load_cached("d11", cname(c))
        fit_items.append((raw, E.lead_clean(raw["t"], raw["label"])))
    profA = fit_profile(fit_items)
    del fit_items
    print(f"{set_name} profile A {profA.summary()} ({time.time() - t0:.0f}s)", flush=True)
    store = E.Store()
    for c in sp["val"]:
        _, F = loadF(c, const(E.ROLE_VAL))
        store.add(F, E.raw_frames(profA, F, range(len(L.VARIANTS))), E.ROLE_VAL)
    store.done()
    sel = E.select_variant(profA, store, codes)
    k = sel["chosen"]
    print(f"{set_name} variant {k}", {kk: round(v["mean_recall"], 3) for kk, v in sel["variants"].items()},
          f"({time.time() - t0:.0f}s)", flush=True)
    regA = E.build_regime("A", profA, store, k, BUDGET)
    val_tbl = E.store_table(store, ex.groups, k)
    res = {"experiment": f"d11_{set_name}", "variant_selection": sel, "profile_A": profA.summary(),
           "vehicle_train": vehicles[sp["train"][0]]["vehicle"], "subsets": {}, "budget": BUDGET,
           "cal_regime_b": {"profile_s": D11_PROFILE_S, "threshold_s": D11_CAL_S - D11_PROFILE_S,
                            "scored_from_s": D11_SKIP_S, "min_eligible_files": MIN_ELIGIBLE}}
    # --- test subsets: regime A and regime B (on-vehicle clean calibration) scored on the same frames
    for sub in ("test_01", "test_02", "test_03", "test_04"):
        files = sp[sub]
        veh = sorted({vehicles[c]["vehicle"] for c in files})
        elig = []
        for c in files:
            raw = E.load_cached("d11", cname(c))
            fi = E.first_injected(raw)
            if fi is None or fi >= D11_SKIP_S:
                elig.append(c)
        # tests with injection-free files: eligible means >= 60 s of clean lead; files with no injection too
        regimes = {"A": regA}
        info = {"vehicle": veh, "n_files": len(files), "n_eligible": len(elig), "eligible": elig}
        if len(elig) >= MIN_ELIGIBLE:
            items = []
            for c in elig:
                raw = E.load_cached("d11", cname(c))
                tm = np.maximum.accumulate(raw["t"])
                items.append((raw, E.lead_clean(raw["t"], raw["label"]) & (tm < D11_PROFILE_S)))
            profB = fit_profile(items)
            del items
            stB = E.Store()
            for c in elig:
                def rolefn(tm):
                    r = np.full(len(tm), E.ROLE_NONE, np.int8)
                    r[(tm >= D11_PROFILE_S) & (tm < D11_CAL_S)] = E.ROLE_VAL
                    return r
                _, F = loadF(c, rolefn)
                stB.add(F, E.raw_frames(profB, F, [k]), E.ROLE_VAL)
            stB.done()
            regimes["B"] = E.build_regime("B", profB, stB, k, BUDGET)
            valB = E.store_table(stB, ex.groups, k)
            info["profile_B"] = profB.summary()
            info["cal_B"] = {"frames": int(len(stB.mf["clean"])), "clean_frames": int(stB.mf["clean"].sum()),
                             "windows": int(len(stB.mw["clean"])), "clean_windows": int(stB.mw["clean"].sum())}
            print(f"{set_name} {sub} B calibrated on {info['cal_B']} ({time.time() - t0:.0f}s)", flush=True)
        tallies = {rn: E.Tally(E.RULE_NAMES) for rn in regimes}
        wrows = {rn: [] for rn in regimes}
        elig_set = set(elig)
        for c in files:
            def rolefn_t(tm, c=c):
                r = np.full(len(tm), E.ROLE_TEST, np.int8)
                if c in elig_set:
                    r[tm < D11_SKIP_S] = E.ROLE_NONE
                return r
            _, F = loadF(c, rolefn_t)
            E.score_file(regimes, F, c, tallies, wrows, codes)
            print(f"  {c} ({time.time() - t0:.0f}s)", flush=True)
        vt = {"A": val_tbl}
        meth = {"A": "auto"}
        if "B" in regimes:
            vt["B"], meth["B"] = valB, "noisy_or"
        first_inj = {rn: {g: f["first_inj_t"] for g, f in tallies[rn].files.items()} for rn in regimes}
        info["regimes"] = ex.regime_report(regimes, tallies, wrows, vt, first_inj, meth, f"d11_{set_name}_{sub}")
        res["subsets"][sub] = info
    res["attack_names"] = codes.names
    res["seconds"] = time.time() - t0
    dump(profA.to_dict(), PROFILES / f"d11_{set_name}_A.json")
    dump(res, outp)
    print("done", set_name, f"({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    which = sys.argv[1]
    if which == "road":
        run_road()
    elif which == "carhacking":
        run_carhacking()
    elif which == "d11":
        for s in sys.argv[2:]:
            run_d11(s)
