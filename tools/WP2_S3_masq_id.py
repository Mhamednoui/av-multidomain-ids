"""WP2 S3: upper bound for skew on ROAD masquerade: score of the INJECTED ID only, attack vs pre-attack frames of the same ID.

Descriptive (not used to choose anything). For every ROAD masquerade capture and each of the 16 skew variants (fitted on the
ROAD train captures exactly as in tools/WP2_S3_run.py): AUC between the scores of the injected ID's frames inside the attack interval
(positives; attacker only, legitimate frames removed) and its frames after warm-up and before the attack (negatives), plus the median
score ratio. AUC 0.5 = no information even when the attacked ID is known. Output: results/WP2/s3_road_masq_id.json
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from can import adapters as A
from can import l1 as L
from can import l1_exp as E
from can import l2a_exp as X
from can import l2a_skew as K
from WP2_S2_run import dump, fit_profile
from common.config import RESULTS
from common.metrics import auc

caps = A.road_captures()
caps = caps[caps["usable"]].sort_values("name").reset_index(drop=True)
train = list(caps.name[caps.part == "train"])


def loader():
    for n in train:
        raw = E.load_cached("road", n)
        yield L.make_features(raw["t"], raw["id"], raw["dlc"], windows=False), E.lead_clean(raw["t"], raw["label"])


items = [(E.load_cached("road", n), None) for n in train]
fit_items = []
for n in train:
    raw = E.load_cached("road", n)
    fit_items.append((raw, E.lead_clean(raw["t"], raw["label"])))
profile = fit_profile(fit_items)
del fit_items, items
variants = list(range(len(K.VARIANTS)))
profs = X.fit_skew(profile, loader, variants)
out = {}
for _, r in caps[caps.kind == "masquerade"].iterrows():
    raw = E.load_cached("road", r["name"])
    F = L.make_features(raw["t"], raw["id"], raw["dlc"], raw["label"], windows=False)
    iid = int(r["meta"]["injection_id"], 16)
    a, b = r["meta"]["injection_interval"]
    m = F["id"] == iid
    pos = m & (raw["label"] == 1)
    row = {}
    for v in variants:
        sc = K.run_pass(F, profs[v])[0]
        neg = m & (F["t"] < a - 1.0) & (sc > -1)
        # negatives: only frames the filter has scored (after warm-up); frames before that carry 0 by construction
        started = np.flatnonzero(m & (sc > 0))
        t_start = F["t"][started[0]] if len(started) else a
        neg = neg & (F["t"] >= t_start)
        if neg.sum() < 20 or pos.sum() < 20:
            row[K.VARIANT_NAMES[v]] = None
            continue
        row[K.VARIANT_NAMES[v]] = {"auc": float(auc(np.r_[np.zeros(neg.sum()), np.ones(pos.sum())], np.r_[sc[neg], sc[pos]])),
                                   "median_pre": float(np.median(sc[neg])), "median_attack": float(np.median(sc[pos])),
                                   "n_pre": int(neg.sum()), "n_attack": int(pos.sum())}
    out[r["name"]] = {"part": r["part"], "id": hex(iid), "variants": row}
    best = max((x["auc"] for x in row.values() if x), default=None)
    print(r["name"], "best AUC over variants:", best, flush=True)
dump(out, RESULTS / "WP2" / "s3_road_masq_id.json")
