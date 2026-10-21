"""WP2 S2: experiment machinery for the L1 rules (profile -> variant -> calibration -> test tallies -> windows).

Purpose: one code path for ROAD, Car-Hacking and D11. A capture is turned into a feature dict F
(can/l1.make_features) with per-frame `role` (0 fit, 1 val/calibration, 2 test, 3 unused) and `clean` (attack-free
traffic). Steps: (1) Profile from clean fit frames; (2) `Store` of raw scores on val-role frames (frame and window
unit, 4 tolerance variants of the period rule); (3) `select_variant` on validation attack windows;
(4) `build_regime`: rules calibrated on clean val frames / windows (tie-safe 1% budget at each unit);
(5) test files scored one at a time into tallies (frame level) and a window table (window level);
(6) `eval_windows`: common harness (per layer, combined, ablation) + per-capture detection / delay / false alerts.
Nothing here reads test labels to choose anything: labels enter only through the val store (variant choice) and the
final tallies.
Inputs: cached captures (tools/WP2_S2_cache.py). Outputs: dicts / DataFrames for results/WP2/s2_*.json.
"""
import numpy as np
import pandas as pd

from can import l1 as L
from common.combiner import DomainCombiner
from common.config import DATA_EXTRA
from common.evaluate import EvalSet, evaluate_domain
from common.metrics import budget_threshold

CACHE = DATA_EXTRA / "WP2_S2_cache"
ROLE_FIT, ROLE_VAL, ROLE_TEST, ROLE_NONE = 0, 1, 2, 3
PERIOD = L.PeriodPerId.name
RULE_NAMES = [c.name for c in L.RULE_CLASSES]


# ------------------------------------------------------------------ loading
class AttCodes:
    """Attack name <-> int code (0 = normal)."""

    def __init__(self):
        self.names = ["normal"]

    def map(self, att_names, att_codes) -> np.ndarray:
        lut = np.zeros(len(att_names), np.int16)
        for i, u in enumerate(att_names):
            if str(u) == "normal":
                continue
            if str(u) not in self.names:
                self.names.append(str(u))
            lut[i] = self.names.index(str(u))
        return lut[np.asarray(att_codes)]


def load_cached(dataset: str, name: str) -> dict:
    d = np.load(CACHE / dataset / (name + ".npz"))
    return {k: d[k] for k in d.files}


def lead_clean(t, label, margin: float = 1.0) -> np.ndarray:
    """Attack-free traffic of one capture: everything if no injected frame, else the frames before the first
    injected frame (and more than `margin` s earlier)."""
    idx = np.flatnonzero(label)
    c = np.ones(len(t), bool)
    if len(idx):
        c[idx[0]:] = False
        c[:idx[0]] = t[:idx[0]] < t[idx[0]] - margin
    return c


def first_injected(raw: dict):
    idx = np.flatnonzero(raw["label"])
    return float(raw["t"][idx[0]]) if len(idx) else None


def make_F(raw: dict, codes: AttCodes, base: int, role, clean, windows=True) -> dict:
    """Feature dict of one capture. role / clean: arrays per frame. Window key = (base * 4 + role) * WIN_SPAN + sec."""
    role = np.asarray(role, np.int8)
    att = codes.map(raw["att_names"], raw["att_codes"])
    F = L.make_features(raw["t"], raw["id"], raw["dlc"], raw["label"], att, clean,
                        group_code=base * 4 + role.astype(np.int64), windows=windows)
    F["role"] = role
    return F


def window_meta(F: dict) -> dict:
    wk = F["wkeys"]
    return {"y": L.window_reduce(F, F["label"]).astype(np.int8),
            "att": L.window_reduce(F, np.where(F["label"] > 0, F["att"], 0)).astype(np.int16),
            "clean": L.window_reduce(F, F["clean"].astype(np.int8), "min").astype(bool),
            "role": ((wk // L.WIN_SPAN) % 4).astype(np.int8), "base": (wk // L.WIN_SPAN // 4).astype(np.int64),
            "w_end": F["w_end"], "wkey": wk}


# ------------------------------------------------------------------ raw scores
def raw_frames(profile: L.Profile, F: dict, variants=None) -> dict:
    """name -> float32 frame raw scores. With `variants`, the period rule is computed once per tolerance variant
    (names 'can.l1_period#k'); the profile's own variant is restored afterwards."""
    out = {}
    keep = profile.variant
    for c in L.RULE_CLASSES:
        if c is L.PeriodPerId and variants is not None:
            for k in variants:
                profile.set_variant(k)
                out[f"{c.name}#{k}"] = c(profile).frame_raw(F).astype(np.float32)
            profile.set_variant(keep)
        else:
            out[c.name] = c(profile).frame_raw(F).astype(np.float32)
    return out


class Store:
    """Raw scores (frame and window unit) and labels of the frames / windows of one role, many captures."""

    def __init__(self):
        self.fr, self.wr, self.mf, self.mw = {}, {}, {}, {}

    def add(self, F: dict, raws: dict, role: int):
        fm = F["role"] == role
        wmeta = window_meta(F)
        wm = wmeta["role"] == role
        for n, r in raws.items():
            self.fr.setdefault(n, []).append(r[fm])
            self.wr.setdefault(n, []).append(L.window_reduce(F, r)[wm])
        for k in ("label", "att", "clean"):
            self.mf.setdefault(k, []).append(F[k][fm])
        for k, v in wmeta.items():
            self.mw.setdefault(k, []).append(v[wm])
        return self

    def done(self):
        for d in (self.fr, self.wr, self.mf, self.mw):
            for k in list(d):
                d[k] = np.concatenate(d[k]) if len(d[k]) else np.zeros(0)
        return self


def select_variant(profile: L.Profile, store: Store, codes: AttCodes, variants=range(len(L.VARIANTS)),
                   budget: float = 0.01) -> dict:
    """Tolerance variant with the highest mean window recall (period rule alone, non-masquerade attack types) at
    the window budget calibrated on clean validation windows. Ties -> first variant."""
    y, att, clean = store.mw["y"] == 1, store.mw["att"], store.mw["clean"]
    types = sorted({int(a) for a in np.unique(att[y]) if "masquerade" not in codes.names[int(a)]})
    res = {}
    for k in variants:
        raw = store.wr[f"{PERIOD}#{k}"]
        r = L.PeriodPerId(profile, "window").calibrate_from_raw(raw[clean], budget)
        al = r.alarms(raw)
        rec = {codes.names[a]: float(al[y & (att == a)].mean()) for a in types}
        res[k] = {"variant": list(L.VARIANTS[k]), "mean_recall": float(np.mean(list(rec.values()))) if rec else 0.0,
                  "recall": rec, "val_fa_rate_clean_windows": float(al[clean].mean())}
    best = max(res, key=lambda k: (res[k]["mean_recall"], -k))
    return {"chosen": int(best), "variants": {str(k): v for k, v in res.items()}}


class Regime:
    def __init__(self, name, profile, fr, wr, thr_comb):
        self.name, self.profile, self.fr, self.wr, self.thr_comb = name, profile, fr, wr, thr_comb


def build_regime(name: str, profile: L.Profile, store: Store, variant: int, budget: float = 0.01) -> Regime:
    """Rules (frame and window unit) calibrated on the CLEAN val frames / windows of `store`."""
    profile.set_variant(variant)
    fr, wr = L.build_rules(profile, "frame"), L.build_rules(profile, "window")
    fc, wc = store.mf["clean"], store.mw["clean"]
    cal = []
    for n in RULE_NAMES:
        key = f"{n}#{variant}" if f"{n}#{variant}" in store.fr else n
        fr[n].calibrate_from_raw(store.fr[key][fc], budget)
        wr[n].calibrate_from_raw(store.wr[key][wc], budget)
        cal.append(fr[n].calibrated(store.fr[key][fc]))
    thr = budget_threshold(L.noisy_or(cal), budget)
    return Regime(name, profile, fr, wr, thr)


# ------------------------------------------------------------------ test scoring
class Tally:
    """Frame-level counts per layer (+ combined): injected frames per attack, clean / all normal frames,
    per-file first-alarm delay."""

    def __init__(self, names):
        self.layers = list(names) + ["combined"]
        self.inj = {n: {} for n in self.layers}
        self.clean = {n: [0, 0] for n in self.layers}
        self.normal = {n: [0, 0] for n in self.layers}
        self.files = {}

    def add(self, gname, F, fm, alarms: dict, codes: AttCodes):
        lab, att, clean = F["label"][fm], F["att"][fm], F["clean"][fm]
        t, tm = F["t"][fm], F["tm"][fm]
        inj = np.flatnonzero(lab)
        fi = {"n_frames": int(fm.sum()), "n_injected": int(len(inj)),
              "first_inj_t": float(t[inj[0]]) if len(inj) else None, "frame_delay": {}}
        nm = lab == 0
        for n in self.layers:
            a = alarms[n]
            for code in (np.unique(att[inj]) if len(inj) else []):
                m = (lab == 1) & (att == code)
                d = self.inj[n].setdefault(codes.names[int(code)], [0, 0])
                d[0] += int(m.sum())
                d[1] += int(a[m].sum())
            self.clean[n][0] += int((nm & clean).sum())
            self.clean[n][1] += int((a & nm & clean).sum())
            self.normal[n][0] += int(nm.sum())
            self.normal[n][1] += int((a & nm).sum())
            if len(inj):
                hit = np.flatnonzero(a[inj])
                fi["frame_delay"][n] = float(tm[inj[hit[0]]] - t[inj[0]]) if len(hit) else None
        self.files[gname] = fi

    def to_dict(self):
        return {"inj": self.inj, "clean": self.clean, "normal": self.normal, "files": self.files}


def score_file(regimes: dict, F: dict, gname: str, tallies: dict, wrows: dict, codes: AttCodes):
    """Score one test file under every regime: frame tallies and window rows (raw per rule)."""
    fm = F["role"] == ROLE_TEST
    wmeta = window_meta(F)
    wm = wmeta["role"] == ROLE_TEST
    for rn, R in regimes.items():
        raws = {n: R.fr[n].frame_raw(F).astype(np.float32) for n in RULE_NAMES}
        cal = {n: R.fr[n].calibrated(raws[n][fm]) for n in RULE_NAMES}
        comb = L.noisy_or(list(cal.values()))
        alarms = {n: cal[n] >= R.fr[n].threshold for n in RULE_NAMES}
        alarms["combined"] = comb >= R.thr_comb
        tallies[rn].add(gname, F, fm, alarms, codes)
        rows = {k: v[wm] for k, v in wmeta.items()}
        rows["group"] = np.full(int(wm.sum()), gname, dtype=object)
        for n in RULE_NAMES:
            rows[f"raw_{n}"] = L.window_reduce(F, raws[n])[wm]
        wrows[rn].append(pd.DataFrame(rows))


def window_table(parts) -> pd.DataFrame:
    return pd.concat(parts, ignore_index=True) if len(parts) else pd.DataFrame()


def store_table(store: Store, groups: dict, variant: int) -> pd.DataFrame:
    """Val store windows as a table like the test rows (group name from base code via `groups`)."""
    d = {k: v for k, v in store.mw.items()}
    d["group"] = np.array([groups[int(b)] for b in store.mw["base"]], dtype=object)
    for n in RULE_NAMES:
        key = f"{n}#{variant}" if f"{n}#{variant}" in store.wr else n
        d[f"raw_{n}"] = store.wr[key]
    return pd.DataFrame(d)


# ------------------------------------------------------------------ window evaluation
def _evidence(regime: Regime, tbl: pd.DataFrame, rows=None) -> dict:
    sub = tbl if rows is None else tbl[rows]
    return {n: regime.wr[n].evidence(sub[f"raw_{n}"].to_numpy(), sub["w_end"].to_numpy(), sub["wkey"].to_numpy())
            for n in RULE_NAMES}


def _evalset(regime, tbl, codes) -> EvalSet:
    keep = ((tbl["y"] == 1) | tbl["clean"]).to_numpy()
    sub = tbl[keep]
    at = np.array([codes.names[int(a)] if y else "normal" for a, y in zip(sub["att"], sub["y"])], dtype=object)
    return EvalSet(evidence=_evidence(regime, tbl, keep), y=sub["y"].to_numpy(), attack_type=at,
                   group=sub["group"].to_numpy(), t=sub["w_end"].to_numpy())


def per_group(tbl: pd.DataFrame, alarms: dict, first_inj: dict, codes: AttCodes) -> dict:
    """Per capture and layer: attack windows, window recall, detected, delay (end of the first alarmed attack
    window minus the first injected frame), false alerts on clean windows and on other normal windows."""
    out = {}
    y = (tbl["y"] == 1).to_numpy()
    clean = tbl["clean"].to_numpy()
    we_all, att_all = tbl["w_end"].to_numpy(), tbl["att"].to_numpy()
    for g, idx in tbl.groupby("group", sort=False).indices.items():
        gy, gc, we, att = y[idx], clean[idx], we_all[idx], att_all[idx]
        rec = {"attack_windows": int(gy.sum()), "clean_windows": int((gc & ~gy).sum()),
               "other_normal_windows": int((~gc & ~gy).sum()),
               "attack": sorted({codes.names[int(a)] for a in att[gy]}), "layers": {}}
        for n, a in alarms.items():
            ga = a[idx]
            hit = np.flatnonzero(ga & gy)
            fi = first_inj.get(g)
            rec["layers"][n] = {
                "recall": float(ga[gy].mean()) if gy.any() else None,
                "detected": bool(len(hit)) if gy.any() else None,
                "delay_s": float(we[hit[0]] - fi) if len(hit) and fi is not None else None,
                "false_alerts_clean": int((ga & gc & ~gy).sum()),
                "false_alerts_other_normal": int((ga & ~gc & ~gy).sum())}
        out[str(g)] = rec
    return out


def eval_windows(regime: Regime, val_tbl: pd.DataFrame, test_tbl: pd.DataFrame, codes: AttCodes, first_inj: dict,
                 name: str, out_dir, budget: float = 0.01, method: str = "auto") -> dict:
    """Common-harness evaluation (per layer, combined, ablation) on clean + attack windows, plus per-capture detail
    and false alerts on ALL test windows. Val for the harness = clean + attack windows of the val table."""
    vs, ts = _evalset(regime, val_tbl, codes), _evalset(regime, test_tbl, codes)
    res = evaluate_domain(name, vs, ts, wp="WP2", budget=budget, method=method, out_dir=out_dir)
    comb = DomainCombiner(method=res["combined"]["method"], budget=budget).fit(vs.evidence, vs.y, vs.group)
    ev_all = _evidence(regime, test_tbl)
    cev = comb.combine(ev_all)
    alarms = {n: np.array([e.alarm for e in ev_all[n]]) for n in RULE_NAMES}
    alarms["combined"] = np.array([e.alarm for e in cev])
    pg = per_group(test_tbl, alarms, first_inj, codes)
    y = (test_tbl["y"] == 1).to_numpy()
    clean = test_tbl["clean"].to_numpy() & ~y
    other = ~test_tbl["clean"].to_numpy() & ~y
    hours = clean.sum() / 3600.0
    summ = {}
    for n, a in alarms.items():
        summ[n] = {"fa_clean_rate": float(a[clean].mean()) if clean.any() else None,
                   "false_alerts_per_hour_clean": float(a[clean].sum() / hours) if hours else None,
                   "fa_other_normal_rate": float(a[other].mean()) if other.any() else None,
                   "attack_window_recall": float(a[y].mean()) if y.any() else None}
    return {"harness": res, "per_capture": pg, "summary": summ,
            "n_windows": {"clean": int(clean.sum()), "attack": int(y.sum()), "other_normal": int(other.sum())},
            "combined_method": comb.method}
