"""WP9 B1: frame-expanded metrics of the saved window decisions (post-processing of saved test scores; no model call).

Every frame inherits the decision of its 1 s window (alarm = window score >= the frozen validation threshold). Counts are
per segment (capture / block run) so the 95% CI is a segment bootstrap. Frame-level precision / recall / F1 / FPR / accuracy
are the units used by most CAN papers; a window detector flags every frame of an alarmed window, so its frame FPR is
coarser than that of a per-frame detector. Output: results/WP9/B1_frames.json
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP9_B1_lib as L
import WP9_B1_fit as FIT

SUBS = {"carhacking": ["test_blocks", "normal_run_test"], "road": ["test", "unseen_family"],
        "d11": ["test_01", "test_02", "test_03", "test_04"]}


def metrics(tp, fp, fn, tn):
    pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
    return {"precision": pr, "recall": rc, "f1": L.f1(pr, rc), "fpr": fp / max(fp + tn, 1),
            "accuracy": (tp + tn) / max(tp + fp + fn + tn, 1)}


def main():
    out = {}
    rng = np.random.default_rng(L.SEED)
    for tag in ["carhacking", "road", "d11_set_01", "d11_set_02", "d11_set_03", "d11_set_04"]:
        ds = tag.split("_")[0]
        sset = tag[4:] if ds == "d11" else None
        t = json.load(open(L.OUT / f"B1_{tag}_test.json"))
        z = np.load(L.SCORES / f"{tag}_test.npz", allow_pickle=True)
        for mname, mm in t["models"].items():
            thr = mm["thr_from_validation"]
            for sub in SUBS[ds]:
                d = z[f"{mname}__{sub}"].item()
                segs = {}
                for sg in np.unique(d["seg"]):
                    m = d["seg"] == sg
                    segs[str(sg)] = (d["wid"][m], d["s"][m].astype(np.float64))
                rows = []
                for sg, (wid, s) in segs.items():
                    S = L.load_segment(ds, sg)
                    fw = L.window_index(S["t"])
                    nw = int(fw.max()) + 1
                    valid = np.zeros(nw, bool); alarm = np.zeros(nw, bool)
                    valid[wid] = True; alarm[wid] = s >= thr
                    fv = valid[fw]; fa = alarm[fw]; att = S["cls"] != 0
                    rows.append([int((att & fa & fv).sum()), int((~att & fa & fv).sum()), int((att & ~fa & fv).sum()),
                                 int((~att & ~fa & fv).sum())])
                rows = np.array(rows)
                tot = rows.sum(axis=0)
                r = metrics(*tot)
                bs = []
                for _ in range(500):
                    pick = rng.integers(len(rows), size=len(rows))
                    bs.append(metrics(*rows[pick].sum(axis=0)))
                r["ci95"] = {k: [float(np.percentile([b[k] for b in bs], 2.5)), float(np.percentile([b[k] for b in bs], 97.5))]
                             for k in ("precision", "recall", "f1", "fpr", "accuracy")}
                r.update({"n_segments": len(rows), "frames": int(tot.sum()), "attack_frames": int(tot[0] + tot[2])})
                out[f"{tag}|{mname}|{sub}"] = r
    L.jd(out, L.OUT / "B1_frames.json")
    print("written", len(out))


if __name__ == "__main__":
    main()
