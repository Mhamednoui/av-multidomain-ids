"""WP5 S5 diagnostic: share of genuine Tampa messages that repeat the previous position exactly (frozen), vs VeReMi genuine. Output results/WP5/s5_tampa_frozen.json."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True
import numpy as np

import WP5_S2_l1 as s2
import WP5_S5_diag as dg
from v2x import adapters, splitting

tp = adapters.load_tampa(with_age=True)
sp = json.loads((s2.OUT / "splits_tampa_v2.json").read_text())
res = {}
for part in ("train", "val", "test"):
    f = splitting.rows_of(tp, sp[part])
    k = dg.row_kinds(f)
    sc = k[k != 1]
    res[part] = {"n": int(len(f)), "share_unscored": float((k == 1).mean()), "share_frozen_of_all": float((k == 2).mean()),
                 "frozen_share_of_scored_pairs": float((k[k != 1] == 2).mean())}
s2.jdump("s5_tampa_frozen.json", res)
print(json.dumps(res))
