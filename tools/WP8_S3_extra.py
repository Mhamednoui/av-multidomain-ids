"""WP8 S3 report numbers that are not selection inputs (selection is closed in selection_r3.json): per-layer-alone ablation of the chosen stack
(each layer at its own budget, leave-one-drive-out), union without one layer, episodes of the exploratory B = 1.25 % row, per-drive PointDrop
detection, AUC of the stack statistic per attack, and the v3-rule baseline on the same scans. Output results/WP8/S3/extra.json."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S3_an as A
import WP8_S3_lib as L
from WP8_S3_freeze import cfg_by_name

OUT = L.ROOT / "results" / "WP8" / "S3"


def main():
    sel = json.loads((OUT / "selection_r3.json").read_text())
    frame = pd.read_pickle(OUT / "frame.pkl")
    res = {}
    for label, name in (("chosen_B1", sel["chosen"]), ("exploratory_B1.25", sel["exploratory_B1.25_best"]), ("v3_rule", "M0|all4")):
        cfg = cfg_by_name("r3", name)
        alone = {l: {k: [] for k in L.ATTACKS} for l in A.LAYERS}
        without = {l: {k: [] for k in L.ATTACKS} for l in A.LAYERS}
        fa_alone = {l: [] for l in A.LAYERS}
        sc_clean, sc_att, att_names = [], [], []
        pd_by_drive = {}
        for d in L.VAL:
            st, ref = A.fit_fold(frame, [d], cfg)
            cl = frame[(frame.kind == "clean") & (frame.drive == d) & (frame.i >= 1)]
            at = frame[(frame.kind == "att") & (frame.drive == d)]
            rc, ra = A.layer_raw(ref, cl, st.cs, st.as_), A.layer_raw(ref, at, st.cs, st.as_)
            sc_clean.append(st.stat(rc))
            sc_att.append(st.stat(ra))
            att_names.append(at.attack.to_numpy())
            m = (at.attack == "PointDrop").to_numpy()
            pd_by_drive[d] = float(st.alarm(ra)[m].mean())
            if cfg["method"] == "union":
                la, lc = st.layer_alarm(ra), st.layer_alarm(rc)
                for j, l in enumerate(A.LAYERS):
                    fa_alone[l].append(lc[:, j])
                    for k in L.ATTACKS:
                        mk = (at.attack == k).to_numpy()
                        alone[l][k].append(la[mk, j])
                        keep = [x for x in range(4) if x != j]
                        without[l][k].append(la[mk][:, keep].any(axis=1))
        sc_c, sc_a, nm = np.concatenate(sc_clean), np.concatenate(sc_att), np.concatenate(att_names)
        r = {"config": name, "pointdrop_by_drive": pd_by_drive,
             "auc_stat": {k: float(roc_auc_score(np.r_[np.zeros(len(sc_c)), np.ones((nm == k).sum())], np.r_[sc_c, sc_a[nm == k]])) for k in L.ATTACKS}}
        if cfg["method"] == "union":
            r["layer_alone_fa"] = {l: float(np.concatenate(v).mean()) for l, v in fa_alone.items()}
            r["layer_alone_det"] = {l: {k: float(np.concatenate(v).mean()) for k, v in d.items()} for l, d in alone.items()}
            r["union_without_layer_det"] = {l: {k: float(np.concatenate(v).mean()) for k, v in d.items()} for l, d in without.items()}
        if label == "exploratory_B1.25":
            e, _ = A.evaluate(frame, cfg, with_episodes=True)
            r["episodes"] = e["episodes"]
            r["fa"], r["det"] = e["fa"], e["det"]
        res[label] = r
        print(label, name, flush=True)
    (OUT / "extra.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
