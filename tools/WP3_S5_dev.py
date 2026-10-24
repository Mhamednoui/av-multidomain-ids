"""WP3 S5 validation round: choose the variant (margin, gap, strict) by the rule in notes/WP3_lidar.md. Needs clean + att_val caches.
Writes results/WP3/S5/dev.json and variant_choice.json."""
import itertools
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS
from lidar import occlusion as O
from lidar import occlusion_eval as E
from lidar.data import VAL

RES = RESULTS / "WP3" / "S5"
ATT = E.PH + E.FL + ["PointDrop", "IntensitySpoof", "cmp_boxcloud", "cmp_mradd_near", "cmp_mradd_far"]

tc, sc = E.load_kind("clean", VAL)
ta, sa = E.load_kind("att_val", VAL)
out = {}
best = None
for v in itertools.product(range(len(O.MARGINS)), range(len(O.GAPS)), (0, 1)):
    cf, af = E.frame(tc, sc, v), E.frame(ta, sa, v)
    lay = O.L2bUnion().calibrate(cf, 0.01)
    det = E.detection(lay, af)
    fa = float((E.cal(lay, cf) >= lay.threshold).mean())
    obj = float(np.mean([det[a] for a in E.CHOICE]))
    out[str(v)] = {"fa_val": fa, "objective": obj, "det": {a: float(det[a]) for a in ATT},
                   "stat_only": {s: {a: float(E.detection(O.L2bUnion([s]).calibrate(cf, 0.01), af)[a]) for a in E.CHOICE} for s in O.STATS}}
    print(v, f"FA {fa:.3f} obj {obj:.3f}", {a: round(det[a], 2) for a in E.CHOICE}, flush=True)
    if best is None or obj > best[1] + 1e-12:
        best = (v, obj)
out["chosen"] = list(best[0])
(RES / "dev.json").write_text(json.dumps(out, indent=1))
(RES / "variant_choice.json").write_text(json.dumps({"variant": list(best[0]), "objective": best[1],
                                                      "rule": "highest mean val detection at 1 % FA over 4 calibrated phantoms + box cloud"}))
print("chosen", best)
