"""WP9 B1: score the TEST segments ONCE with the model(s) frozen in results/WP9/B1_<tag>_selection.json.

Usage: python -u -W ignore tools/WP9_B1_test.py carhacking|road|d11 [set_0N]
Refuses to run if scores/B1/<tag>_test*.npz already exist (test is scored once). Reproduces the saved validation
scores of the frozen model first (consistency check), then scores test, saves per-window (and per-frame for F) scores,
writes results/WP9/B1_<tag>_test.json and registers exposure in results/WP9/B1_exposure.json.
Models scored: the chosen model (all datasets) and, for D11 only, the vehicle-agnostic secondary (pre-registered).
"""
import datetime
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import xgboost as xgb

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP9_B1_lib as L
import WP9_B1_fit as FIT
from common.metrics import budget_threshold

N_BOOT = 1000


def load_model(mdir, name, bundle):
    if name.startswith("W_rf"):
        return pickle.load(open(mdir / f"{name}.pkl", "rb"))
    b = xgb.Booster()
    b.load_model(str(mdir / f"{name}.ubj"))
    b.set_param({"nthread": 4})
    return b


def predict(model, X, K1):
    if hasattr(model, "predict_proba"):
        return model.predict_proba(np.nan_to_num(X, nan=-1)).astype(np.float32)
    out = np.empty((len(X), K1), np.float32)
    for a in range(0, len(X), 1_000_000):
        out[a:a + 1_000_000] = model.predict(xgb.DMatrix(X[a:a + 1_000_000]))
    return out


class Scorer:
    def __init__(self, bundle, mdir):
        self.b, self.mdir = bundle, mdir
        self.K1 = bundle["K1"]
        self.models = {}

    def get(self, name):
        if name not in self.models:
            self.models[name] = load_model(self.mdir, name, self.b)
        return self.models[name]

    def seg_scores(self, name, S, w, want_frames=False):
        """-> s, c over ALL windows of the segment (valid mask applied by the caller); frame arrays if F."""
        K1 = self.K1
        if name == "E":
            pF, pW = self.b["ensemble"]["parts"]
            sF, cF, fr = self.seg_scores(pF, S, w, want_frames)
            sW, cW, _ = self.seg_scores(pW, S, w)
            ref = self.b["ensemble"]["ref"]
            uF = np.searchsorted(ref[pF], sF, side="right") / len(ref[pF])
            uW = np.searchsorted(ref[pW], sW, side="right") / len(ref[pW])
            return ((uF + uW) / 2).astype(np.float32), np.where(uW >= uF, cW, cF), fr
        if name.startswith("W_"):
            sl = slice(0, self.b["ng"]) if self.b["fs"][name] == "generic" else slice(0, None)
            P = predict(self.get(name), w["W"][:, sl], K1)
            s, c = FIT.sc(P)
            return s, c, None
        cols = self.b["cols"][name]
        P = predict(self.get(name), L.frame_matrix(S, *self.pl, cols), K1)
        sf, cf = FIT.sc(P)
        sw, cw = L.window_scores_from_frames(w["wid"], w["W"].shape[0], sf, cf)
        return sw, cw, (sf, cf)


def run_segments(sc_, name, segs, pl, K1, frames=False):
    sc_.pl = pl
    out = []
    for i, S in segs:
        w = L.segment_windows(S, *pl, K1)
        s, c, fr = sc_.seg_scores(name, S, w, frames)
        v = w["valid"]
        d = {"seg": i["seg"], "group": i["group"], "y": w["y"][v], "s": s[v], "c": c[v], "wid": np.flatnonzero(v),
             "n_att": w["n_att"][v]}
        if fr is not None and frames:
            d["frame_s"] = fr[0].astype(np.float16)
            d["frame_y"] = S["cls"]
            d["frame_ok"] = S["ok"]
        out.append(d)
    return out


def cat(rs, key):
    return np.concatenate([r[key] for r in rs])


def frame_metrics(val_rs, test_rs):
    """Frame-level attack-vs-normal at the 1% validation frame budget (only when F is part of the model)."""
    vs = np.concatenate([r["frame_s"][r["frame_ok"] & (r["frame_y"] == 0)] for r in val_rs]).astype(np.float32)
    thr = budget_threshold(vs, 0.01)
    s = np.concatenate([r["frame_s"].astype(np.float32) for r in test_rs])
    y = np.concatenate([r["frame_y"] for r in test_rs])
    ok = np.concatenate([r["frame_ok"] for r in test_rs])
    m = ok | (y != 0)
    s, y = s[m], y[m]
    pos, neg = y != 0, y == 0
    s = s.astype(np.float64)
    tp, fp, fn = int(np.sum(pos & (s >= thr))), int(np.sum(neg & (s >= thr))), int(np.sum(pos & (s < thr)))
    pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
    return {"thr": thr, "recall": rc, "fpr": fp / max(neg.sum(), 1), "precision": pr, "f1": L.f1(pr, rc),
            "auc": L.auc_binary(pos.astype(int), s), "n_frames": int(len(y)), "n_attack_frames": int(pos.sum())}


def main():
    ds = sys.argv[1]
    sset = sys.argv[2] if len(sys.argv) > 2 else None
    tag = ds + (f"_{sset}" if sset else "")
    sel = json.load(open(L.OUT / f"B1_{tag}_selection.json"))
    if list(L.SCORES.glob(f"{tag}_test*.npz")):
        raise SystemExit(f"test already scored for {tag}: refusing (test is scored once)")
    classes, idx = FIT.cfg_for(ds, sset)
    K1 = len(classes)
    mdir = L.CACHE / "models" / tag
    bundle = pickle.load(open(mdir / "bundle.pkl", "rb"))
    pl = (*L.period_lookup(bundle["period"]), bundle["id_list"])
    names = [sel["chosen"]] + ([sel["chosen_vehicle_agnostic"]] if ds == "d11" and sel["chosen_vehicle_agnostic"] != sel["chosen"] else [])
    L.journal(f"test {tag}: START scoring test once with {names} (selection json committed before)")
    sc_ = Scorer(bundle, mdir)
    # ---- consistency: reproduce validation window scores of the chosen model
    va = FIT.load_parts(ds, idx, ("val",))
    vr = {}
    for nm in names:
        vr[nm] = run_segments(sc_, nm, va, pl, K1, frames=True)
        z = np.load(L.SCORES / f"{tag}_val.npz")
        d = float(np.abs(cat(vr[nm], "s") - z[f"s_{nm}"]).max())
        print(f"val reproduction {nm}: max |ds| = {d:.2e}", flush=True)
        assert d < 5e-3, "validation scores not reproduced"
    # ---- test subsets
    subsets = {"carhacking": {"test_blocks": lambda i: i["part"] == "test" and i["kind"] == "block",
                              "normal_run_test": lambda i: i["part"] == "test" and i["kind"] == "normal_run"},
               "road": {"test": lambda i: i["part"] == "test", "unseen_family": lambda i: i["part"] == "test_unseen_family"},
               "d11": {f"test_0{k}": (lambda i, k=k: i["part"] == f"test_0{k}") for k in (1, 2, 3, 4)}}[ds]
    res = {"tag": tag, "models": {}, "classes": classes, "selection": str(L.OUT / f"B1_{tag}_selection.json")}
    store = {}
    for nm in names:
        thr = bundle["thr"][nm]
        r = {"thr_from_validation": thr, "subsets": {}}
        allv = {}
        for sub, f in subsets.items():
            segs = [(i, FIT.L.load_segment(ds, i["seg"])) for i in idx if f(i)]
            rs = run_segments(sc_, nm, segs, pl, K1, frames=True)
            allv[sub] = rs
            y, s, c, g = cat(rs, "y"), cat(rs, "s"), cat(rs, "c"), cat(rs, "group")
            seen = y >= 0
            seen_set = (sub != "unseen_family" and not (ds == "d11" and sub in ("test_03", "test_04")))
            if seen_set:
                m = seen
                smr = L.summarize(y[m], s[m], c[m], thr, groups=g[m], n_boot=N_BOOT,
                                  seen_idx=list(range(K1)) if sub not in ("normal_run_test",) else None)
                smr["row"] = "seen attack types"
            else:
                smr = L.summarize(y, s, c, thr, groups=g, n_boot=N_BOOT, seen_idx=[0])
                smr["row"] = "UNSEEN attack family"
            r["subsets"][sub] = smr
            r["subsets"][sub]["n_segments"] = len(segs)
            store[f"{nm}__{sub}"] = dict(y=y, s=s, c=c, group=g, seg=np.concatenate([[x["seg"]] * len(x["y"]) for x in rs]),
                                         wid=cat(rs, "wid"))
            if nm.startswith("F") or nm == "E":
                fr = [x for x in rs if "frame_s" in x]
                if fr and seen_set and sub != "normal_run_test":
                    r["subsets"][sub]["frame_level_val_budget"] = frame_metrics(vr[nm], fr)
                    store[f"{nm}__{sub}__frame_s"] = np.concatenate([x["frame_s"] for x in fr])
                    store[f"{nm}__{sub}__frame_y"] = np.concatenate([x["frame_y"] for x in fr])
            print(sub, nm, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in smr.items()
                            if k in ("macro_f1", "macro_f1_argmax", "fpr", "recall_any", "auc", "f1_attack_binary", "n_windows")}, flush=True)
        # ---- dataset-specific extras
        if ds == "carhacking":
            y = np.concatenate([cat(allv["test_blocks"], "y"), cat(allv["normal_run_test"], "y")])
            s = np.concatenate([cat(allv["test_blocks"], "s"), cat(allv["normal_run_test"], "s")])
            c = np.concatenate([cat(allv["test_blocks"], "c"), cat(allv["normal_run_test"], "c")])
            g = np.concatenate([cat(allv["test_blocks"], "group"), cat(allv["normal_run_test"], "group")])
            r["pooled_blocks_plus_normal_run"] = L.summarize(y, s, c, thr, groups=g, n_boot=N_BOOT)
        if ds == "road":
            ev = []
            for rr in allv["test"] + allv["unseen_family"]:
                lab = idx_lookup(idx, rr["seg"])
                if lab["interval"] is None:
                    continue
                m = rr["y"] != 0
                det = bool((rr["s"][m].astype(np.float64) >= thr).any()) if m.any() else None
                first = int(rr["wid"][m][np.argmax(rr["s"][m].astype(np.float64) >= thr)]) if det else None
                a = lab["interval"][0]
                ev.append({"capture": rr["seg"], "class": lab["attack_class"], "attack_windows": int(m.sum()),
                           "detected": det, "first_alarm_window": first,
                           "delay_s": (None if first is None else float(first - np.floor(a)))})
            r["event_level"] = ev
            ambient = [rr for rr in allv["test"] if idx_lookup(idx, rr["seg"])["kind"] == "ambient"]
            att_norm = np.concatenate([rr["s"][rr["y"] == 0] for rr in allv["test"] if idx_lookup(idx, rr["seg"])["kind"] != "ambient"]).astype(np.float64)
            amb_norm = np.concatenate([rr["s"][rr["y"] == 0] for rr in ambient]).astype(np.float64)
            r["fpr_context"] = {"ambient_captures": float(np.mean(amb_norm >= thr)), "n_ambient_windows": int(len(amb_norm)),
                                "normal_windows_in_attack_captures": float(np.mean(att_norm >= thr)),
                                "n_attack_capture_normal_windows": int(len(att_norm))}
            r["ambient_fpr_by_capture"] = {rr["seg"]: float(np.mean(rr["s"][rr["y"] == 0].astype(np.float64) >= thr)) for rr in ambient}
        res["models"][nm] = r
    # ---- save scores + results + exposure
    np.savez_compressed(L.SCORES / f"{tag}_test.npz", **store)
    L.jd(res, L.OUT / f"B1_{tag}_test.json")
    ex_p = L.OUT / "B1_exposure.json"
    ex = json.load(open(ex_p)) if ex_p.exists() else {}
    ex[tag] = {"scored_on": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "models": names,
               "test_subsets": {k: [i["seg"] for i in idx if f(i)] for k, f in subsets.items()},
               "times_scored_by_B1": 1, "selection_json": f"results/WP9/B1_{tag}_selection.json",
               "scores": f"results/WP9/scores/B1/{tag}_test.npz", "results": f"results/WP9/B1_{tag}_test.json"}
    L.jd(ex, ex_p)
    L.journal(f"test {tag}: DONE results/WP9/B1_{tag}_test.json; exposure registered")


def idx_lookup(idx, seg):
    return next(i for i in idx if i["seg"] == seg)


if __name__ == "__main__":
    main()
