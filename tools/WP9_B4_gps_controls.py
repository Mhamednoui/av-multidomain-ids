"""WP9 B4 GPS controls on VALIDATION (committed before the test): row-shuffled labels, session-label permutation (null), proxy-only vehicle-state model,
feature-importance flag. Chosen config per feature set from results/WP9/B4_gps_selection.json. No test session is used.
Output: results/WP9/B4_gps_controls.json.   Run: python -u -W ignore tools/WP9_B4_gps_controls.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import WP9_B4_gps_lib as L

OUT = L.ROOT / "results" / "WP9"


def main():
    t0 = time.time()
    df = L.load_sessions()
    c1 = L.LOCK["case_I"]
    tr, va = L.rows(df, c1["train"]), L.rows(df, c1["val"])
    sel = json.loads((OUT / "B4_gps_selection.json").read_text())
    res = {"rules": {"shuffle_band": [0.42, 0.58], "session_permutation": "PASS if real val AUC > 95th percentile of the 20-draw null",
                     "flags": "single feature > 0.5 gain or satellite/HDOP group > 0.5"}, "sets": {}}
    sess_lab = tr.groupby("session").y.first()
    for name, S in sel["sets"].items():
        cols, d = S["features"], S["chosen_depth"]
        n_tr = S["chosen"]["trees"]
        m = L.fit_xgb(tr[cols], tr.y, va[cols], va.y, depth=d)
        real_auc = L.safe_auc(va.y, m.predict_proba(va[cols])[:, 1])
        r = {"depth": d, "real_val_auc": real_auc}
        # 1 row-shuffled labels (train labels permuted, 5 seeds). Primary: fixed number of rounds = chosen trees (no early stopping on the REAL validation labels,
        # which selects the best-looking iteration: amendment 2, 2026-11-05, validation seen, test not). Supplementary: early stopping on the real validation labels.
        sh, sh_es = [], []
        for seed in (1, 2, 3, 4, 5):
            y = np.random.default_rng(seed).permutation(tr.y.to_numpy())
            ms = L.fit_xgb(tr[cols], y, None, None, depth=d, seed=seed, n_rounds=n_tr)
            sh.append(L.safe_auc(va.y, ms.predict_proba(va[cols])[:, 1]))
            me = L.fit_xgb(tr[cols], y, va[cols], va.y, depth=d, seed=seed)
            sh_es.append(L.safe_auc(va.y, me.predict_proba(va[cols])[:, 1]))
        r["row_shuffle_val_auc"] = sh
        r["row_shuffle_val_auc_earlystop_on_real_val"] = sh_es
        r["row_shuffle_pass"] = bool(all(0.42 <= a <= 0.58 for a in sh))
        # 2 session-label permutation (whole session label swapped among train sessions), fixed number of rounds = chosen trees (no val early stopping on a real signal)
        nulls = []
        ids = sess_lab.index.to_numpy()
        for seed in range(20):
            perm = np.random.default_rng(100 + seed).permutation(sess_lab.to_numpy())
            mp = dict(zip(ids, perm))
            y = tr.session.map(mp).to_numpy()
            if y.sum() in (0, len(y)):
                continue
            mq = L.fit_xgb(tr[cols], y, None, None, depth=d, seed=seed, n_rounds=n_tr)
            nulls.append(L.safe_auc(va.y, mq.predict_proba(va[cols])[:, 1]))
        q = [float(np.quantile(nulls, p)) for p in (0.05, 0.5, 0.95)]
        r["session_perm_null_auc"] = {"n": len(nulls), "q05_q50_q95": q, "min": float(min(nulls)), "max": float(max(nulls))}
        r["session_perm_pass"] = bool(real_auc > q[2])
        # 4 importance
        imp = L.gain_share(m, cols)
        top = list(imp.items())[:5]
        sat = sum(v for k, v in imp.items() if k in L.SAT)
        r["top_gain_share"] = top
        r["satellite_hdop_gain_share"] = sat
        r["flag_single_feature"] = bool(top[0][1] > 0.5)
        r["flag_receiver_state"] = bool(sat > 0.5)
        res["sets"][name] = r
        print(name, {k: (v if not isinstance(v, (list, dict)) else '...') for k, v in r.items()}, flush=True)
    # 3 proxy-only vehicle-state model
    px = L.PROXY
    best = None
    out = {}
    for d in (3, 5):
        m = L.fit_xgb(tr[px], tr.y, va[px], va.y, depth=d)
        out[d] = L.safe_auc(va.y, m.predict_proba(va[px])[:, 1])
    res["proxy_only_vehicle_state"] = {"features": px, "val_auc_by_depth": out}
    print("proxy-only", out, flush=True)
    (OUT / "B4_gps_controls.json").write_text(json.dumps(res, indent=1))
    print("done", f"{time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
