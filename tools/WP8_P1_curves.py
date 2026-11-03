"""WP8 P1: paper analysis of the SAVED v3 test scores (no refit, no new threshold, no new model, no test re-run).

Label on every output: "re-analysis of v3 test outputs (no refit)".
Per domain (resumable: a domain whose results/WP8/P1/<dom>_summary.json exists is skipped; --force redoes it):
  gps    results/WP1/cache/s8_raw.pkl (raw per-layer scores, KITTI test rows) + frozen calibrators
         results/WP1/frozen_gps (deterministic map raw -> calibrated -> noisy-or log statistic; checked against S8_kitti.json)
  lidar  results/WP3/S9/test_scores.csv.gz (per scan stack score and alarm); AUC cross-checked with S9/final.json
  can    results/WP2/s3_{road,carhacking}_windows_test*.csv.gz  (RAW L1 rule / L2a columns of the S3 window tables only;
         the final v3 CAN stack scores (L3c, L3d) lived in deleted caches: not available)
  net    results/WP4/s7_d10.json operating-point tables (seen: published test; unseen: leave-one-attack-out). No curves.
Not available without a re-run: network, V2X, fusion/system per-sample scores (see not_available.md).
Outputs: results/WP8/P1/<dom>_*.{csv,md,png,pdf,json}, summary.md, not_available.md.
Run from codes_v3/: python -u -W ignore tools/WP8_P1_curves.py [gps lidar can net summary] [--force]
Pre-registered operating point = the v3 frozen alarm rule, marked with a black star; detection "at FA x%" is READ off the saved test
curve (the threshold is the test-score quantile for that FA); it is not a new operating point and not a tuned choice.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "results" / "WP8" / "P1"
OUT.mkdir(parents=True, exist_ok=True)
LABEL = "re-analysis of v3 test outputs (no refit)"
BUDGETS = (0.005, 0.01, 0.02, 0.05)
NBOOT = 1000
SEED = 42
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


# ---------------------------------------------------------------------------------------------------------------- metrics
def auc_np(neg, pos):
    if len(neg) == 0 or len(pos) == 0:
        return np.nan
    r = rankdata(np.concatenate([neg, pos]))
    return float((r[len(neg):].sum() - len(pos) * (len(pos) + 1) / 2) / (len(neg) * len(pos)))


def det_at_fa(neg, pos, fa):
    """Detection at the largest threshold with (fraction of neg strictly above) <= fa; tie-safe."""
    if len(neg) == 0 or len(pos) == 0:
        return np.nan
    k = int(np.floor(fa * len(neg)))
    thr = np.sort(neg)[::-1][min(k, len(neg) - 1)]
    return float((pos > thr).mean())


def roc_points(neg, pos, n_max=400):
    allv = np.unique(np.concatenate([neg, pos]))[::-1]
    if len(allv) > n_max:
        allv = np.unique(np.quantile(np.concatenate([neg, pos]), np.linspace(0, 1, n_max)))[::-1]
    sn, sp = np.sort(neg), np.sort(pos)
    fpr = 1 - np.searchsorted(sn, allv, side="left") / len(sn)
    tpr = 1 - np.searchsorted(sp, allv, side="left") / len(sp)
    return np.r_[0.0, fpr, 1.0], np.r_[0.0, tpr, 1.0]


def group_bootstrap(neg, gneg, pos, gpos, reps=NBOOT, seed=SEED):
    """Resample groups (drive / capture) with replacement; groups holding only negatives and groups holding only positives are
    resampled within their own kind (so both classes always exist). Returns dict of arrays: auc, det@budgets."""
    rng = np.random.default_rng(seed)
    gn, gp = set(gneg), set(gpos)
    kinds = {"mixed": sorted(gn & gp, key=str), "neg": sorted(gn - gp, key=str), "pos": sorted(gp - gn, key=str)}
    idxn = {g: neg[gneg == g] for g in gn}
    idxp = {g: pos[gpos == g] for g in gp}
    out = {"auc": []}
    out.update({b: [] for b in BUDGETS})
    for _ in range(reps):
        ns, ps = [], []
        for kind, gl in kinds.items():
            if not gl:
                continue
            for g in rng.choice(len(gl), len(gl), replace=True):
                gg = gl[g]
                if gg in idxn:
                    ns.append(idxn[gg])
                if gg in idxp:
                    ps.append(idxp[gg])
        if not ns or not ps:
            continue
        n, p = np.concatenate(ns), np.concatenate(ps)
        if len(n) < 10 or len(p) < 3:
            continue
        out["auc"].append(auc_np(n, p))
        for b in BUDGETS:
            out[b].append(det_at_fa(n, p, b))
    return {k: np.array(v) for k, v in out.items()}


def ci(a):
    a = a[~np.isnan(a)]
    return (float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))) if len(a) else (np.nan, np.nan)


def subset_row(name, neg, gneg, pos, gpos, op=None, kind=""):
    bs = group_bootstrap(neg, gneg, pos, gpos)
    row = {"subset": name, "kind": kind, "n_pos": len(pos), "n_neg": len(neg), "auc": auc_np(neg, pos)}
    row["auc_lo"], row["auc_hi"] = ci(bs["auc"])
    for b in BUDGETS:
        row[f"det@{b:.1%}"] = det_at_fa(neg, pos, b)
        row[f"det@{b:.1%}_lo"], row[f"det@{b:.1%}_hi"] = ci(bs[b])
    if op is not None:
        row["op_fa"], row["op_det"] = op
    return row


def fmt_table(df, cols):
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            cells.append("" if (isinstance(v, float) and np.isnan(v)) else (f"{v:.3f}" if isinstance(v, float) else str(v)))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def md_main(df):
    """Compact markdown view: AUC [CI] and detection at the four budgets with CI."""
    lines = ["| subset | n pos / n neg | AUC [95% CI] | det@0.5% FA | det@1% FA | det@2% FA | det@5% FA | op. point (FA / det) |", "|---|---|---|---|---|---|---|---|"]
    for _, r in df.iterrows():
        cells = [r["subset"], f"{int(r['n_pos'])} / {int(r['n_neg'])}", f"{r['auc']:.3f} [{r['auc_lo']:.3f}, {r['auc_hi']:.3f}]"]
        for b in BUDGETS:
            k = f"det@{b:.1%}"
            cells.append(f"{r[k]:.1%} [{r[k + '_lo']:.0%}, {r[k + '_hi']:.0%}]")
        cells.append(f"{r['op_fa']:.2%} / {r['op_det']:.1%}" if "op_fa" in r and not pd.isna(r.get("op_fa", np.nan)) else "")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------------------------------- plots
def plot_roc(path, title, curves, op=None, note=""):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    styles = ["-", "--", "-.", ":", (0, (5, 1)), (0, (3, 1, 1, 1)), (0, (1, 1)), (0, (7, 2)), (0, (2, 1, 5, 1))]
    greys = ["0.0", "0.25", "0.45", "0.1", "0.35", "0.55", "0.15", "0.4", "0.3"]
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.6))
    for ax, xlog in zip(axs, (False, True)):
        for i, (lab, (fpr, tpr), lw) in enumerate(curves):
            ax.plot(np.maximum(fpr, 1e-4) if xlog else fpr, tpr, color=greys[i % 9], ls=styles[i % 9], lw=lw, label=lab)
        for b in BUDGETS:
            ax.axvline(b, color="0.75", lw=0.7, ls=":")
        if op is not None:
            ax.plot(max(op[0], 1e-4) if xlog else op[0], op[1], marker="*", ms=14, mfc="black", mec="white", mew=0.8, ls="none", label="v3 pre-registered operating point", zorder=5)
        if xlog:
            ax.set_xscale("log")
            ax.set_xlim(1e-3, 1)
            ax.set_xlabel("false-alarm rate (log scale; dotted: 0.5, 1, 2, 5%)")
        else:
            ax.set_xlim(0, 1)
            ax.plot([0, 1], [0, 1], color="0.8", lw=0.8)
            ax.set_xlabel("false-alarm rate")
        ax.set_ylim(0, 1.02)
        ax.set_ylabel("detection rate")
        ax.grid(alpha=0.25)
    axs[1].legend(fontsize=7, loc="lower right", frameon=True)
    fig.suptitle(f"{title}\n{LABEL}" + (f"; {note}" if note else ""), fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(path.with_suffix(".png"), dpi=170)
    fig.savefig(path.with_suffix(".pdf"))
    plt.close(fig)


def write_outputs(dom, df, curves_csv, summary, title, curves, op, note="", extra_md=""):
    df.to_csv(OUT / f"{dom}_table.csv", index=False)
    pd.DataFrame(curves_csv).to_csv(OUT / f"{dom}_curve_points.csv", index=False)
    md = [f"# {title}", "", f"**{LABEL}.** Source files: {summary['sources']}", "", md_main(df), "", extra_md]
    (OUT / f"{dom}_table.md").write_text("\n".join(md), encoding="utf-8")
    plot_roc(OUT / f"{dom}_roc", title, curves, op, note)
    summary["label"] = LABEL
    (OUT / f"{dom}_summary.json").write_text(json.dumps(summary, indent=1, default=float), encoding="utf-8")   # written last = done marker
    log(dom, "written")


def curves_for(neg, pos_by_name, pooled_pos=None, pooled_name="all attacks"):
    cs, pts = [], []
    if pooled_pos is not None:
        fpr, tpr = roc_points(neg, pooled_pos)
        cs.append((pooled_name, (fpr, tpr), 2.4))
        pts += [{"curve": pooled_name, "fpr": a, "tpr": b} for a, b in zip(fpr, tpr)]
    for n, p in pos_by_name.items():
        fpr, tpr = roc_points(neg, p)
        cs.append((n, (fpr, tpr), 1.2))
        pts += [{"curve": n, "fpr": a, "tpr": b} for a, b in zip(fpr, tpr)]
    return cs, pts


# ---------------------------------------------------------------------------------------------------------------- GPS
def run_gps():
    from gps import domain, stack
    raw = pd.read_pickle(ROOT / "results/WP1/cache/s8_raw.pkl")
    test = raw[raw["part"] == "test"].reset_index(drop=True)
    sel = json.loads((ROOT / "results/WP1/S8_dev.json").read_text())["cusum_selection"]["full_dev"]
    d = domain.GPSDomain.load(ROOT / "results/WP1/frozen_gps")
    colmap = {"gps.cusum_ekf": sel["ekf"], "gps.cusum_dr": sel["dr"]}
    cal = {l.name: l.calibrator.transform(test[colmap.get(l.name, l.name)].to_numpy(float)) for l in d.layers}
    S = stack.noisy_or_log(stack.stack_matrix(cal, d.names))
    sc = d.comb_cal.transform(S)
    alarm = sc >= d.comb_threshold
    y = test["label"].to_numpy()
    att, drv = test["attack"].to_numpy(), test["drive"].to_numpy()
    neg_m = y == 0
    neg, gneg = S[neg_m], drv[neg_m]
    ref = json.loads((ROOT / "results/WP1/S8_kitti.json").read_text())["deployed"]
    chk = {"auc_here": auc_np(neg, S[y == 1]), "auc_saved_S8_kitti": ref["auc_row_level"], "fa_rows_here": float(alarm[neg_m].mean()),
           "fa_rows_saved": ref["fa_all_normal_rows"], "row_det_here": {a: float(alarm[(att == a) & (y == 1)].mean()) for a in ref["row_detection"]},
           "row_det_saved": ref["row_detection"]}
    log("GPS check", chk["auc_here"], chk["auc_saved_S8_kitti"], chk["fa_rows_here"], chk["fa_rows_saved"])
    assert abs(chk["auc_here"] - chk["auc_saved_S8_kitti"]) < 1e-6 and abs(chk["fa_rows_here"] - chk["fa_rows_saved"]) < 1e-9
    seen = ["drift", "accel_drift", "jump", "freeze"]
    unseen = ["doppler_spoof", "meaconing"]
    pos_all = y == 1

    def pm(names):
        return pos_all & np.isin(att, names)

    rows = []
    op_of = lambda m: (float(alarm[neg_m].mean()), float(alarm[m].mean()))
    for nm, m, kind in [("ALL attacks (6)", pos_all, "pooled"), ("seen by the combiner (4)", pm(seen), "seen"), ("unseen by the combiner: Doppler + meaconing (2)", pm(unseen), "unseen")] + \
                       [(a, pm([a]), "unseen" if a in unseen else "seen") for a in seen + unseen]:
        rows.append(subset_row(nm, neg, gneg, S[m], drv[m], op_of(m), kind))
        log("gps", nm)
    df = pd.DataFrame(rows)
    cs, pts = curves_for(neg, {a: S[pm([a])] for a in seen + unseen}, S[pos_all], "all six attacks (pooled)")
    sm = {"domain": "gps", "sources": "results/WP1/cache/s8_raw.pkl (raw layer scores, 7 KITTI test drives, 11,074 rows), results/WP1/frozen_gps (calibrators, noisy-or log, threshold), results/WP1/S8_dev.json (CUSUM selection); cross-check results/WP1/S8_kitti.json",
          "unit": "row level (one GPS fix); positives = spoofed rows after onset, negatives = all label-0 rows (clean runs and pre-onset rows); groups = 7 test drives, bootstrap 1000 x over drives",
          "check_vs_saved": chk, "operating_point": {"threshold_calibrated": d.comb_threshold, "fa_rows": float(alarm[neg_m].mean())}}
    extra = ("Seen vs unseen: the combiner (noisy-or log) was fitted without the Doppler and meaconing rows (WP1 S8); the layers themselves are physics rules "
             "and normal-only filters. Row-level numbers differ from the run-level headline of RESULTS_v3.md (76.2% mean run-level detection at 1.83% clean-run FA): "
             "a run counts as detected at its first alarm, a row only when it alarms itself. Check against S8_kitti.json: AUC and row-level FA/detection reproduced exactly.")
    write_outputs("gps", df, pts, sm, "GPS: detection vs false alarm (KITTI test drives, row level)", cs, (float(alarm[neg_m].mean()), float(alarm[pos_all].mean())), extra_md=extra)


# ---------------------------------------------------------------------------------------------------------------- LiDAR
def run_lidar():
    d = pd.read_csv(ROOT / "results/WP3/S9/test_scores.csv.gz")
    fin = json.loads((ROOT / "results/WP3/S9/final.json").read_text())["headline"]
    cl = d[d["attack"] == "clean"]
    neg, gneg = cl["score"].to_numpy(), cl["drive"].to_numpy()
    at = d[d["frame"] == "att"]
    thr = fin["threshold"]
    # score is the calibrated stack score; alarm column = pre-registered rule
    chk = {"fa_here": float(cl["alarm"].mean()), "fa_saved": fin["fa"], "auc_here": {a: auc_np(neg, g["score"].to_numpy()) for a, g in at.groupby("attack")}, "auc_saved": fin["auc"],
           "alarm_equals_score_ge_threshold": bool(((d["score"] >= thr) == d["alarm"]).all())}
    log("LiDAR check", chk["fa_here"], chk["fa_saved"], max(abs(chk["auc_here"][a] - chk["auc_saved"][a]) for a in chk["auc_here"]))
    assert abs(chk["fa_here"] - chk["fa_saved"]) < 1e-9
    names = [a for a in fin["auc"]]
    kind = {a: ("tamper" if a in ("PointDrop", "IntensitySpoof") else "phantom" if a.startswith("ph_") else "comparator") for a in names}
    rows = []
    op = lambda g: (float(cl["alarm"].mean()), float(g["alarm"].mean()))
    pools = [("ALL scan-level attacks (9)", at, "pooled"), ("physical phantoms (4: ph_*)", at[at["attack"].str.startswith("ph_")], "phantom"),
             ("tamper (PointDrop + IntensitySpoof)", at[at["attack"].isin(["PointDrop", "IntensitySpoof"])], "tamper")]
    pools += [(a, at[at["attack"] == a], kind[a]) for a in names]
    for nm, g, k in pools:
        rows.append(subset_row(nm, neg, gneg, g["score"].to_numpy(), g["drive"].to_numpy(), op(g), k))
        log("lidar", nm)
    df = pd.DataFrame(rows)
    cs, pts = curves_for(neg, {a: at[at["attack"] == a]["score"].to_numpy() for a in names}, at["score"].to_numpy(), "all 9 scan-level attacks (pooled)")
    sm = {"domain": "lidar", "sources": "results/WP3/S9/test_scores.csv.gz (11,156 test scans, 7 KITTI test drives), threshold/FA from results/WP3/S9/final.json headline",
          "unit": "scan level; negatives = 1,526 clean test scans; positives = scan-level attacked scans (510 per attack); groups = 7 test drives, bootstrap 1000 x over drives",
          "check_vs_saved": chk, "operating_point": {"threshold": thr, "fa": float(cl["alarm"].mean())}}
    extra = ("Seen vs unseen: not applicable. The v3 LiDAR stack has no layer trained on attack data in its headline (L1 geometry rules, L2a/L2c/L2d normal-only or physics "
             "layers, combiner max), so every attack here is unseen. Episode frames (ep_*, epW_*) are in the test file but are scored per episode in v3 (RESULTS_v3.md section 6, R4); "
             "they are not pooled here. Known physics limit: calibrated far / budget phantoms are invisible to single-return physics (AUC about 0.5). "
             "Cross-check: per-attack AUC equals results/WP3/S9/final.json headline.auc.")
    write_outputs("lidar", df, pts, sm, "LiDAR: detection vs false alarm (KITTI test scans, scan level)", cs, (float(cl["alarm"].mean()), float(at["alarm"].mean())), extra_md=extra)


# ---------------------------------------------------------------------------------------------------------------- CAN
def run_can():
    cols = ["raw_can.l1_id_allow", "raw_can.l1_dlc", "raw_can.l1_period", "raw_can.l1_bus_load", "raw_can.l1_flood", "raw_can.l2a_skew"]
    sets = {"ROAD test (run 1 table)": ROOT / "results/WP2/s3_road_windows_test_A.csv.gz", "Car-Hacking test": ROOT / "results/WP2/s3_carhacking_windows_test.csv.gz"}
    rows, pts, cs_all = [], [], {}
    for sname, f in sets.items():
        t = pd.read_csv(f)
        negm, posm = t["clean"].to_numpy().astype(bool), t["y"].to_numpy() == 1
        masq = t["group"].str.endswith("_masquerade").to_numpy()
        for c in cols:
            s = t[c].to_numpy(float)
            neg, gneg = s[negm], t["group"].to_numpy()[negm]
            subs = [("all attacks", posm, "pooled")]
            if sname.startswith("ROAD"):
                subs += [("plain injection captures", posm & ~masq, "seen-type"), ("masquerade captures", posm & masq, "masquerade")]
            for nm, m, k in subs:
                r = subset_row(f"{sname} / {c.replace('raw_can.', '')} / {nm}", neg, gneg, s[m], t["group"].to_numpy()[m], None, k)
                r["data_set"], r["layer"], r["attacks"] = sname, c.replace("raw_can.", ""), nm
                rows.append(r)
            if True:
                fpr, tpr = roc_points(neg, s[posm])
                cs_all.setdefault(sname, []).append((c.replace("raw_can.", ""), (fpr, tpr), 1.4))
                pts += [{"set": sname, "curve": c, "fpr": a, "tpr": b} for a, b in zip(fpr, tpr)]
        log("can", sname)
    df = pd.DataFrame(rows)
    sm = {"domain": "can", "sources": "results/WP2/s3_road_windows_test_A.csv.gz, results/WP2/s3_carhacking_windows_test.csv.gz (S3 raw window tables: L1 rule columns + L2a skew); headline stack numbers from results/WP2/s7_test.json",
          "unit": "1 s window; negatives = clean-capture windows (clean==True); positives = windows with y==1; groups = captures; bootstrap 1000 x over captures (clean and attack captures resampled within their own kind)",
          "not_available": "final v3 stack scores (L3c per-signal predictors, L3d reverse-light rule; combiner max): only in deleted caches data_extra/WP2_S7_cache",
          "operating_point": "none marked: the S3 table holds raw rule values, the v3 operating point of the stack is on L1+L3c+L3d (ROAD test: clean-window FA 3.20%, masquerade 5/5, plain 6/6; results/WP2/s7_test.json)"}
    import matplotlib
    matplotlib.use("Agg")
    for sname, cs in cs_all.items():
        tag = "road" if sname.startswith("ROAD") else "carhacking"
        plot_roc(OUT / f"can_roc_{tag}", f"CAN {sname}: raw rule columns of the S3 window table (NOT the final stack)", cs, None, "partial: final L3c/L3d scores not available")
    df.to_csv(OUT / "can_table.csv", index=False)
    pd.DataFrame(pts).to_csv(OUT / "can_curve_points.csv", index=False)
    md = ["# CAN: raw rule columns of the S3 window tables (partial)", "", f"**{LABEL}.** Source files: {sm['sources']}", "",
          "These are the single raw L1 rule values (id allow-list, DLC, period, bus load, flood) and the L2a skew value that were saved with the S3 window tables. They are NOT the final v3 CAN stack (L1 + L3c + L3d, combiner max): "
          "its per-window scores are not available without a re-run. Many windows tie at zero for the rule columns, so detection at low FA is a lower bound set by ties (tie-safe: strictly above the threshold).", "",
          md_main(df.drop(columns=["data_set", "layer", "attacks"]).assign(op_fa=np.nan, op_det=np.nan))]
    (OUT / "can_table.md").write_text("\n".join(md), encoding="utf-8")
    sm["label"] = LABEL
    (OUT / "can_summary.json").write_text(json.dumps(sm, indent=1, default=float), encoding="utf-8")
    log("can written")


# ---------------------------------------------------------------------------------------------------------------- network
def run_net():
    d = json.loads((ROOT / "results/WP4/s7_d10.json").read_text())
    rows = []
    for st, v in d["stacks"].items():
        pub = v.get("published")
        if not pub:
            continue
        for fam, det in pub["detection"].items():
            row = {"stack": st, "family": fam, "n_flows": pub["n"].get(fam), "seen_detection_test": det, "fa_published_stack": pub.get("fa")}
            lo = d["loao"].get(fam)
            if lo and st in lo["stacks"]:
                row["unseen_detection_loao"] = lo["stacks"][st]["detection"].get(fam)
                row["loao_fa"] = lo["stacks"][st]["fa"]
            rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "net_seen_unseen.csv", index=False)
    md = ["# Network (CIC-IDS2017, D10): seen vs unseen family, operating point only", "", f"**{LABEL}.** Source: results/WP4/s7_d10.json (`stacks/<stack>/published/detection` = trained-on-all test; `loao/<family>/stacks/<stack>/detection` = that family held out). "
          "Only operating-point detection was saved (no per-flow or per-bin scores): no ROC / AUC is possible without a re-run. FA = flow-level false-alarm rate of the stack at its pre-registered operating point.", "",
          fmt_table(df, ["stack", "family", "n_flows", "seen_detection_test", "unseen_detection_loao", "fa_published_stack", "loao_fa"])]
    (OUT / "net_seen_unseen.md").write_text("\n".join(md), encoding="utf-8")
    (OUT / "net_summary.json").write_text(json.dumps({"domain": "net", "label": LABEL, "sources": "results/WP4/s7_d10.json", "rows": len(df)}, indent=1), encoding="utf-8")
    log("net written")


NOT_AVAILABLE = """# Not available without a re-run

All entries: "re-analysis of v3 test outputs (no refit)" cannot be produced because the per-sample scores were stored only in caches deleted on 2026-10-25
(data_extra/cache_v3, data_extra/WP2_S*_cache; notes/ORCHESTRATOR.md) or were never stored. No test data was re-scored for this step.

| domain | what is missing | what exists instead |
|---|---|---|
| CAN, final stack | per-window scores of L3c (per-signal predictors), L3d (reverse-light rule) and the max combiner on ROAD test | raw L1 rule / L2a columns of the S3 window tables (partial curves, can_*); operating-point tables in results/WP2/s7_test.json |
| Network | per-flow / per-5-minute-bin scores of the host-window logic and flow-shape layers (D10, D23) | operating-point detection per family, seen and leave-one-attack-out (net_seen_unseen.*) |
| V2X | per-message / per-sender scores on VeReMi test, Tampa, V2AIX (results/WP7/frozen_v2x/domain.json holds only the calibration table) | operating-point tables in RESULTS_v3.md section 5 and results/WP5/*.json |
| Fusion / system | per-tick domain scores and fused scores of the M2 system on the K and C simulation timelines (results/WP6, WP7 S2) | per-run detection, delay and blame at the frozen operating point (results/WP6/s5b_test.json, results/WP7/S2_results.json); no curve possible |
| GPS UAV / AV-GPS external tests | per-fix scores | operating-point numbers in results/WP1/S8_external.json |
| LiDAR episodes | per-episode scores are in S9/test_scores.csv.gz but v3 scores episodes with its own episode rule | S9/final.json `episodes` |

To obtain these curves a re-run of the corresponding test scoring (new test exposure) would be needed; that is outside P1.
"""


def run_summary():
    parts = ["# P1 summary tables: " + LABEL, ""]
    for dom, f in [("gps", "gps_table.csv"), ("lidar", "lidar_table.csv"), ("can", "can_table.csv")]:
        p = OUT / f
        if not p.exists():
            continue
        df = pd.read_csv(p)
        if dom == "can":
            df = df[df["attacks"] == "all attacks"]
            df = df.assign(subset=df["data_set"] + " / " + df["layer"])
            df["op_fa"] = np.nan
            df["op_det"] = np.nan
        else:
            df = df.iloc[:1]
            df["subset"] = dom.upper() + ": " + df["subset"]
        parts += [md_main(df), ""]
    (OUT / "summary.md").write_text("\n".join(parts), encoding="utf-8")
    (OUT / "not_available.md").write_text(NOT_AVAILABLE, encoding="utf-8")


RUNNERS = {"gps": run_gps, "lidar": run_lidar, "can": run_can, "net": run_net}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    todo = args or list(RUNNERS) + ["summary"]
    for t in todo:
        if t == "summary":
            run_summary()
            continue
        if (OUT / f"{t}_summary.json").exists() and not force:
            log(t, "already done, skipped")
            continue
        RUNNERS[t]()


if __name__ == "__main__":
    main()
