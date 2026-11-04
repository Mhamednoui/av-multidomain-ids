"""WP8 S7 per-domain H31 rows, detection-vs-FA curves and ROC AUC with group-bootstrap CIs (M4-15), from the saved H31 scores. No threshold, calibration or model is changed here: operating
points are the FROZEN alarm rules of v3 and v3.1 (stars on the curves); curves and AUC use the saved continuous scores; AUC / detection@FA CIs resample groups (drive / capture / 10-min block /
ego block / composite group; B = 1000, seed 31, histogram bootstrap with 4096 quantile bins). Every row carries its exposure label.
Domains: gps, cross (K, vehicle block), lidar (v3 vs v3.1), can (ROAD test + accelerator), network (v3 / F1 / RC5), v2x (VeReMi test ego ticks), system (fused tick score, K and C, v3 vs v3.1).
Output: results/WP8/S7/domains.json, results/WP8/S7/curves/<domain>_*.{png,pdf,csv,md}. Run: python -u -W ignore tools/WP8_S7_domains.py [gps cross lidar can network v2x system]"""
import json
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S7_lib as S7

import numpy as np
import pandas as pd

import WP8_P1_curves as P1

CURVES = S7.OUT / "curves"
NB, SEED, NBIN = 1000, 31, 4096
BUD = (0.001, 0.005, 0.01, 0.02, 0.05, 0.10)
P1.LABEL = "H31 scoring (frozen v3 vs frozen v3.1, one run)"
P1.BUDGETS = BUD


# ------------------------------------------------------------------------------------------------ histogram bootstrap
def _hist(x, edges):
    return np.bincount(np.clip(np.searchsorted(edges, x, side="right") - 1, 0, len(edges) - 2), minlength=len(edges) - 1).astype(np.float64)


def _stats(hn, hp):
    """AUC and detection at the BUD false-alarm budgets from the negative / positive histograms (bins ascending)."""
    N, Pn = hn.sum(), hp.sum()
    if N == 0 or Pn == 0:
        return np.nan, [np.nan] * len(BUD)
    cn_below = np.cumsum(hn) - hn
    auc = float((hp * (cn_below + 0.5 * hn)).sum() / (N * Pn))
    n_above = N - np.cumsum(hn)                     # negatives strictly above bin b
    p_above = Pn - np.cumsum(hp)
    det = []
    for b in BUD:
        ok = np.flatnonzero(n_above <= b * N)
        k = ok[0] if len(ok) else len(hn) - 1       # first bin whose strict-above negatives are within the budget
        det.append(float(p_above[k] / Pn))
    return auc, det


def boot_ci(neg, gneg, pos, gpos, reps=NB, seed=SEED):
    neg, pos = np.asarray(neg, float), np.asarray(pos, float)
    gneg, gpos = np.asarray(gneg).astype(str), np.asarray(gpos).astype(str)
    allv = np.concatenate([neg, pos])
    edges = np.unique(np.quantile(allv, np.linspace(0, 1, NBIN + 1)))
    edges[0], edges[-1] = -np.inf, np.inf
    hn = {g: _hist(neg[gneg == g], edges) for g in np.unique(gneg)}
    hp = {g: _hist(pos[gpos == g], edges) for g in np.unique(gpos)}
    gn, gp = set(hn), set(hp)
    kinds = [sorted(gn & gp), sorted(gn - gp), sorted(gp - gn)]
    rng = np.random.default_rng(seed)
    aucs, dets = [], []
    for _ in range(reps):
        sn, sp = np.zeros(len(edges) - 1), np.zeros(len(edges) - 1)
        for gl in kinds:
            if gl:
                for j in rng.integers(0, len(gl), len(gl)):
                    g = gl[j]
                    if g in hn:
                        sn += hn[g]
                    if g in hp:
                        sp += hp[g]
        a, d = _stats(sn, sp)
        if not np.isnan(a):
            aucs.append(a)
            dets.append(d)
    q = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if len(v) else [np.nan, np.nan]
    dets = np.array(dets)
    return {"auc_ci": q(aucs), "det_ci": [q(dets[:, i]) for i in range(len(BUD))]}


def row(name, neg, gneg, pos, gpos, exposure, op=None, note="", ci=True):
    neg, pos = np.asarray(neg, float), np.asarray(pos, float)
    if len(neg) < 10 or len(pos) < 3:
        return {"subset": name, "exposure": exposure, "n_pos": int(len(pos)), "n_neg": int(len(neg)), "note": "too few samples"}
    r = {"subset": name, "exposure": exposure, "n_pos": int(len(pos)), "n_neg": int(len(neg)), "auc": P1.auc_np(neg, pos)}
    for b in BUD:
        r[f"det@{b:.1%}"] = P1.det_at_fa(neg, pos, b)
    if ci:
        c = boot_ci(neg, gneg, pos, gpos)
        r["auc_ci"] = c["auc_ci"]
        for b, v in zip(BUD, c["det_ci"]):
            r[f"det@{b:.1%}_ci"] = v
    if op is not None:
        r["op_fa"], r["op_det"] = op
    if note:
        r["note"] = note
    return r


def plot(dom, title, curves, op_stars, note=""):
    CURVES.mkdir(parents=True, exist_ok=True)
    cs = []
    pts = []
    for lab, neg, pos, lw in curves:
        fpr, tpr = P1.roc_points(np.asarray(neg, float), np.asarray(pos, float))
        cs.append((lab, (fpr, tpr), lw))
        pts += [{"curve": lab, "fpr": a, "tpr": b} for a, b in zip(fpr, tpr)]
    P1.plot_roc(CURVES / f"{dom}_roc", title, cs, op_stars[0] if op_stars else None, note)
    pd.DataFrame(pts).to_csv(CURVES / f"{dom}_curve_points.csv", index=False)


def fmt_md(rows, cols=None):
    cols = cols or ["subset", "exposure", "n_pos", "n_neg", "auc", "det@1.0%", "det@2.0%", "op_fa", "op_det"]
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        cells = []
        for c in cols:
            v = r.get(c)
            if isinstance(v, float):
                ci = r.get(c + "_ci") or (r.get("auc_ci") if c == "auc" else None)
                cells.append(f"{v:.3f}" + (f" [{ci[0]:.3f}, {ci[1]:.3f}]" if ci and not np.isnan(ci[0]) else ""))
            else:
                cells.append("" if v is None else str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def save_table(dom, rows, cols=None):
    CURVES.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(CURVES / f"{dom}_table.csv", index=False)
    (CURVES / f"{dom}_table.md").write_text(f"# {dom} (H31, {P1.LABEL})\n\n" + fmt_md(rows, cols) + "\n", encoding="utf-8")


# ------------------------------------------------------------------------------------------------ GPS / cross (K vehicle block)
def load_kveh():
    k = pickle.load(open(S7.CACHE / "kveh.pkl", "rb"))["series"]
    strata = {d: v[1] for d, v in S7.kitti_drives().items()}
    return k, strata


GPS_FAMS = ["drift", "accel_drift", "doppler_spoof", "meaconing", "gps_can"]
CROSS_FAMS = ["lidar_scale", "lidar_bias", "lidar_yaw", "can_scale", "can_offset", "can_freeze", "gps_can", "drift", "accel_drift", "doppler_spoof", "meaconing"]


def vehicle_rows(dom, score_key, alarm_key, fams):
    k, strata = load_kveh()
    out, stars = [], []
    for stratum in ("all", "same_day_2011_09_26", "other_day"):
        keys = [x for x in k if stratum == "all" or strata[x[0]] == stratum]
        neg = np.concatenate([k[x][score_key] for x in keys if x[2] == "none"])
        gneg = np.concatenate([[x[0]] * k[x]["n"] for x in keys if x[2] == "none"])
        al_neg = np.concatenate([k[x][alarm_key] for x in keys if x[2] == "none"])
        fa = float(al_neg.mean())
        pos_all, g_all, a_all = [], [], []
        for f in fams:
            ks = [x for x in keys if x[2] == f]
            if not ks:
                continue
            pos = np.concatenate([k[x][score_key][k[x]["label"]] for x in ks])
            gp = np.concatenate([[x[0]] * int(k[x]["label"].sum()) for x in ks])
            al = np.concatenate([k[x][alarm_key][k[x]["label"]] for x in ks])
            runs = float(np.mean([bool(k[x][alarm_key][k[x]["label"]].any()) for x in ks]))
            if f in ("drift", "accel_drift", "doppler_spoof", "meaconing", "gps_can") or dom == "cross":
                pos_all.append(pos)
                g_all.append(gp)
                a_all.append(al)
            r = row(f"{dom} {f} [{stratum}]", neg, gneg, pos, gp, S7.EXPOSURE["fresh"] + f" ({stratum})", op=(fa, float(al.mean())), ci=(stratum == "all"))
            r["run_level_detection"], r["runs"] = runs, len(ks)
            out.append(r)
            if stratum == "all":
                stars.append((fa, float(al.mean())))
        r = row(f"{dom} pooled attacks [{stratum}]", neg, gneg, np.concatenate(pos_all), np.concatenate(g_all), S7.EXPOSURE["fresh"] + f" ({stratum})", op=(fa, float(np.concatenate(a_all).mean())),
                ci=(stratum == "all"))
        r["clean_tick_fa"] = fa
        out.append(r)
        if stratum == "all":
            curves = [("pooled attacks", neg, np.concatenate(pos_all), 2.4)]
            for f in fams:
                ks = [x for x in keys if x[2] == f]
                if ks:
                    curves.append((f, neg, np.concatenate([k[x][score_key][k[x]["label"]] for x in ks]), 1.1))
            plot(dom, f"{dom} (KITTI H31 vehicle block, frozen v3 = v3.1)", curves, [(float(fa), float(np.concatenate(a_all).mean()))], "stratum all")
    # drift of the clean FA relative to V31_val
    s2 = pickle.load(open(S7.DATA_EXTRA / "cache_v3" / "WP8" / "S2" / "kveh.pkl", "rb"))["series"]
    fa_val = float(np.concatenate([s[alarm_key] for x, s in s2.items() if x[2] == "none"]).mean())
    return out, {"clean_tick_fa_h31": float(np.concatenate([k[x][alarm_key] for x in k if x[2] == "none"]).mean()), "clean_tick_fa_V31_val": fa_val}


# ------------------------------------------------------------------------------------------------ LiDAR
def lidar_rows():
    lid = pickle.load(open(S7.CACHE / "lidar.pkl", "rb"))
    out, curves, stars = [], [], {}
    frames = {d: r["frame"] for d, r in lid["drives"].items()}
    df = pd.concat([f.assign(drive=d) for d, f in frames.items()], ignore_index=True)
    clean = df[df["kind"] == "clean"]
    paired = {}
    rng = np.random.default_rng(SEED)
    drives = sorted(frames)
    for tag in ("v3", "v31"):
        neg = clean[f"{tag}_score"].to_numpy(float)
        gneg = clean["drive"].to_numpy()
        fa = float(clean[f"{tag}_alarm"].mean())
        out.append({"subset": f"{tag} clean scans (FA)", "exposure": S7.EXPOSURE["fresh"], "n_neg": int(len(clean)), "op_fa": fa,
                    "per_stratum": {s: float(clean[clean["drive"].isin([d for d in drives if lid["drives"][d]["stratum"] == s])][f"{tag}_alarm"].mean()) for s in sorted({lid["drives"][d]["stratum"] for d in drives})}})
        kinds = list(lid["kinds"]) + ["cmp_boxcloud", "cmp_mradd_near", "cmp_mradd_far"]
        pooled = []
        for kd in kinds + ["ep_PointDrop"]:
            sel = df[(df["attack"] == kd)]
            if kd == "ep_PointDrop":
                sel_steps = {"ep_PointDrop onset (step 1)": sel[sel["step"] == 1], "ep_PointDrop later steps (2-30)": sel[sel["step"] >= 2]}
            else:
                sel_steps = {kd: sel}
            for nm, s in sel_steps.items():
                if not len(s):
                    continue
                r = row(f"{tag} {nm}", neg, gneg, s[f"{tag}_score"].to_numpy(float), s["drive"].to_numpy(), S7.EXPOSURE["fresh"], op=(fa, float(s[f"{tag}_alarm"].mean())))
                out.append(r)
                if kd in lid["kinds"] and kd != "ep_PointDrop":
                    pooled.append(s)
        pp = pd.concat(pooled)
        out.append(row(f"{tag} pooled 6 headline kinds", neg, gneg, pp[f"{tag}_score"].to_numpy(float), pp["drive"].to_numpy(), S7.EXPOSURE["fresh"], op=(fa, float(pp[f"{tag}_alarm"].mean()))))
        curves.append((f"{tag} pooled headline kinds", neg, pp[f"{tag}_score"].to_numpy(float), 2.4 if tag == "v31" else 1.4))
        pd_ = df[df["attack"] == "PointDrop"]
        curves.append((f"{tag} PointDrop", neg, pd_[f"{tag}_score"].to_numpy(float), 1.1 if tag == "v31" else 0.8))
        stars[tag] = (fa, float(pp[f"{tag}_alarm"].mean()))
    # paired scan-level detection difference v3.1 - v3 per kind, bootstrap over drives
    for kd in list(lid["kinds"]) + ["cmp_boxcloud", "cmp_mradd_near", "cmp_mradd_far"]:
        s = df[df["attack"] == kd]
        a = {d: (s[s["drive"] == d]["v31_alarm"].astype(float).to_numpy(), s[s["drive"] == d]["v3_alarm"].astype(float).to_numpy()) for d in drives if (s["drive"] == d).any()}
        est = float(s["v31_alarm"].mean() - s["v3_alarm"].mean())
        bs = []
        ds = sorted(a)
        for _ in range(NB):
            pick = [ds[j] for j in rng.integers(0, len(ds), len(ds))]
            x = np.concatenate([a[d][0] for d in pick])
            y = np.concatenate([a[d][1] for d in pick])
            bs.append(x.mean() - y.mean())
        paired[kd] = {"diff_points": est * 100, "ci_points": [float(np.percentile(bs, 2.5) * 100), float(np.percentile(bs, 97.5) * 100)], "v31": float(s["v31_alarm"].mean()), "v3": float(s["v3_alarm"].mean()), "n": int(len(s))}
    clean_pair = {"v31_fa": float(clean["v31_alarm"].mean()), "v3_fa": float(clean["v3_alarm"].mean())}
    plot("lidar", "LiDAR (KITTI H31): frozen v3 stack vs frozen v3.1 union", [(l, n, p, w) for l, n, p, w in curves], [stars["v31"], stars["v3"]], "stars: v3.1 (first), v3")
    return out, {"paired_scan_level_v31_minus_v3": paired, "clean": clean_pair}


# ------------------------------------------------------------------------------------------------ CAN
def can_rows():
    names = sorted(p.name for p in S7.SCORES.glob("can_test_*.npz"))
    out, neg_all, gneg_all, pos_all, gpos_all, stars = [], [], [], [], [], []
    per = []
    for fn in names:
        z = np.load(S7.SCORES / fn)
        name = fn[len("can_test_"):-4]
        s, y, al = z["score"], z["y"] > 0, z["alarm"]
        acc = "accelerator" in name
        exposure = S7.EXPOSURE["fresh"] if acc else S7.EXPOSURE["reused"]
        rec = {"subset": name, "exposure": exposure, "windows": int(len(s)), "label_windows": int(y.sum()), "alarm_rate_clean_windows": float(al[~y].mean()) if (~y).any() else None,
               "alarm_rate_label_windows": float(al[y].mean()) if y.any() else None, "capture_level_alarm_rate": float(al.mean()) if acc else None}
        per.append(rec)
        if acc:
            continue
        neg_all.append(s[~y])
        gneg_all.append(np.full((~y).sum(), name))
        if y.any():
            pos_all.append(s[y])
            gpos_all.append(np.full(y.sum(), name))
    neg, gneg, pos, gpos = np.concatenate(neg_all), np.concatenate(gneg_all), np.concatenate(pos_all), np.concatenate(gpos_all)
    fa = float(np.concatenate([np.load(S7.SCORES / fn)["alarm"][np.load(S7.SCORES / fn)["y"] == 0] for fn in names if "accelerator" not in fn]).mean())
    det = float(np.concatenate([np.load(S7.SCORES / fn)["alarm"][np.load(S7.SCORES / fn)["y"] > 0] for fn in names if "accelerator" not in fn]).mean())
    out.append(row("CAN ROAD test windows, pooled attacks (v3 = v3.1: same frozen object)", neg, gneg, pos, gpos, S7.EXPOSURE["reused"], op=(fa, det)))
    plot("can", "CAN (ROAD test, re-used; v3 = v3.1)", [("pooled attacks", neg, pos, 2.4)], [(fa, det)])
    return out, {"per_capture": per}


# ------------------------------------------------------------------------------------------------ network
def network_rows():
    z = np.load(S7.SCORES / "network_test.npz", allow_pickle=True)
    fam, aud, blk, t = z["fam"], z["audit"], z["block"], z["t"]
    g = np.array([f"{b}|{int(x // 600)}" for b, x in zip(blk, t)])
    ben = (fam == "BENIGN") & ~aud
    EVAL = ["Bot", "DDoS-LOIC-HTTP", "DoS-GoldenEye", "DoS-Hulk", "DoS-SlowHTTPTest", "DoS-Slowloris", "FTP-Patator", "SSH-Patator", "PortScan", "Web-BruteForce", "Web-XSS"]
    out, curves, stars = [], [], {}
    for tag in ("v3", "F1", "RC5"):
        s, a = z[f"{tag}_score"].astype(float), z[f"{tag}_alarm"]
        fa = float(a[ben].mean())
        atk = np.isin(fam, EVAL)
        rr = []
        for f in EVAL:
            m = fam == f
            if m.sum() < 10:
                continue
            r = row(f"{tag} {f}", s[ben], g[ben], s[m], g[m], S7.EXPOSURE["reused"], op=(fa, float(a[m].mean())), ci=False)
            rr.append(r)
        out += rr
        out.append(row(f"{tag} pooled 11 families", s[ben], g[ben], s[atk], g[atk], S7.EXPOSURE["reused"], op=(fa, float(np.mean([r["op_det"] for r in rr])))))
        curves.append((f"{tag} pooled", s[ben], s[atk], 2.4 if tag == "F1" else 1.4))
        stars[tag] = (fa, float(np.mean([r["op_det"] for r in rr])))
    plot("network", "Network stack H (D10 test, re-used): v3 vs F1 vs RC5", curves, [stars["F1"], stars["v3"], stars["RC5"]], "stars: F1, v3, RC5")
    return out, {}


# ------------------------------------------------------------------------------------------------ V2X (VeReMi ego ticks)
def v2x_rows():
    v = pickle.load(open(S7.CACHE / "v2x.pkl", "rb"))["series"]
    neg = np.concatenate([s["score"][s["count"] > 0] for s in v if s["kind"] == "clean"])
    gneg = np.concatenate([[s["group"]] * int((s["count"] > 0).sum()) for s in v if s["kind"] == "clean"])
    al_neg = np.concatenate([s["dom_alarm"][s["count"] > 0] for s in v if s["kind"] == "clean"])
    fa = float(al_neg.mean())
    fams = sorted({f for s in v if s["kind"] == "attack" for f in set(s["fam"]) if f})
    out, curves, pos_all, g_all, a_all = [], [], [], [], []
    for f in fams:
        ps, gs, als = [], [], []
        for s in v:
            if s["kind"] != "attack":
                continue
            m = (s["fam"] == f) & (s["count"] > 0)
            ps.append(s["score"][m])
            gs.append([s["group"]] * int(m.sum()))
            als.append(s["dom_alarm"][m])
        p, gp, al = np.concatenate(ps), np.concatenate([np.asarray(x) for x in gs]), np.concatenate(als)
        if len(p) < 3:
            continue
        out.append(row(f"V2X {f}", neg, gneg, p, gp, S7.EXPOSURE["reused"], op=(fa, float(al.mean())), ci=False))
        pos_all.append(p)
        g_all.append(gp)
        a_all.append(al)
        curves.append((f, neg, p, 1.0))
    P = np.concatenate(pos_all)
    out.append(row("V2X pooled attack types", neg, gneg, P, np.concatenate(g_all), S7.EXPOSURE["reused"], op=(fa, float(np.concatenate(a_all).mean()))))
    curves.insert(0, ("pooled", neg, P, 2.4))
    plot("v2x", "V2X (VeReMi test ego ticks, re-used; v3 = v3.1)", curves, [(fa, float(np.concatenate(a_all).mean()))])
    return out, {"clean_tick_fa": fa}


# ------------------------------------------------------------------------------------------------ system (fused tick score)
def system_rows():
    out, extra = [], {}
    for fam in ("K", "C"):
        curves, stars = [], {}
        for run, lab in (("v3", "v3"), ("v31", "v3.1")):
            try:
                c = np.load(S7.SCORES / f"system_{fam}_clean_h31_{run}.npz")
                a = np.load(S7.SCORES / f"system_{fam}_attack_h31_{run}.npz")
            except FileNotFoundError:
                continue
            neg = c["score"].astype(float)
            gneg = np.repeat(c["groups"], c["lens"])
            pos_m = a["label"]
            pos = a["score"].astype(float)[pos_m]
            gpos = np.repeat(a["groups"], a["lens"])[pos_m]
            fa = float(c["alarm"].mean())
            det = float(a["alarm"][pos_m].mean())
            out.append(row(f"system {fam} {lab}: all attacked ticks", neg, gneg, pos, gpos, S7.EXPOSURE["mixed"], op=(fa, det)))
            curves.append((f"{lab} all attacked ticks", neg, pos, 2.4 if lab == "v3.1" else 1.4))
            stars[lab] = (fa, det)
            ids = np.repeat(a["ids"], a["lens"])[pos_m]
            for sc in ("veh", "lidar", "can", "v2x", "net", "multi"):
                m = np.array([f"-{sc}" in x or x.endswith(sc) for x in ids])
                if m.sum() >= 20:
                    out.append(row(f"system {fam} {lab}: {sc} composites", neg, gneg, pos[m], gpos[m], S7.EXPOSURE["mixed"], op=(fa, float(a["alarm"][pos_m][m].mean())), ci=False))
        if curves:
            plot(f"system_{fam}", f"System {fam}: fused tick score, v3 vs v3.1 (H31 composites)", curves, [stars.get("v3.1"), stars.get("v3")] if stars else None, "stars: v3.1, v3")
    return out, extra


STAGES = {"gps": lambda: vehicle_rows("gps", "gps_score", "gps_alarm", GPS_FAMS), "cross": lambda: vehicle_rows("cross", "cross_score", "cross_alarm", CROSS_FAMS), "lidar": lidar_rows, "can": can_rows,
          "network": network_rows, "v2x": v2x_rows, "system": system_rows}


def main():
    names = sys.argv[1:] or list(STAGES)
    f = S7.OUT / "domains.json"
    res = json.loads(f.read_text()) if f.exists() else {}
    for n in names:
        S7.journal("S7", f"domain rows {n}: start", "tools/WP8_S7_domains.py")
        rows, extra = STAGES[n]()
        res[n] = {"rows": rows, **extra}
        save_table(n, [r for r in rows if "auc" in r or "op_fa" in r])
        S7.write_json(res, f)
        S7.journal("S7", f"domain rows {n}: done", f"{len(rows)} rows")


if __name__ == "__main__":
    main()
