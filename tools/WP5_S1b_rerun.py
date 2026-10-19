"""WP5 S1b: re-run the Tampa evaluations of S2 (L1) and S3 (L2) unchanged in method on the deduplicated data and the new split.

Run from codes_v3/:
  python -I -u -W ignore tools/WP5_S1b_rerun.py            the single test run on splits_tampa_v2.json (dedup passages, time-block split)
  python -I -u -W ignore tools/WP5_S1b_rerun.py --legacy   same code on the OLD data (coreData_id senders) and OLD split splits_tampa.json
                                                           (map_road out of the union): separates the leak effect from the union change
  python -I -u -W ignore tools/WP5_S1b_rerun.py --smoke    pipeline check with the VALIDATION part standing in for test (files *_smoke, deleted)
Outputs (results/WP5/): s2_tampa_<tag>.json/.md, s3_tampa_<tag>.json/.md (harness), s2_summary_tampa_<tag>.json, s3_summary_tampa_<tag>.json,
s2_tables_tampa_<tag>.md, s3_tables_tampa_<tag>.md; tag = v2 | v1same | smoke.
Acceptance rule: notes/WP5_v2x.md, 'S1b ... acceptance rule'. Methods are those of v2x/l1.py and v2x/l2.py, unchanged.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True

import WP5_S2_l1 as s2
import WP5_S3_l2 as s3
from v2x import adapters

LEGACY = "--legacy" in sys.argv
SMOKE = "--smoke" in sys.argv
OUT = s2.OUT


def main():
    assert not (LEGACY and SMOKE)
    if LEGACY:
        tag = "v1same"
        split_file = "splits_tampa.json"
        loader = lambda: adapters.load_tampa_v1(with_age=True)
    elif SMOKE:
        tag = "smoke"
        sp = json.loads((OUT / "splits_tampa_v2.json").read_text())
        sp["test"] = sp["val"]
        split_file = "splits_tampa_v2_smoke.json"
        (OUT / split_file).write_text(json.dumps(sp))
        loader = lambda: adapters.load_tampa(with_age=True)
    else:
        tag = "v2"
        split_file = "splits_tampa_v2.json"
        loader = lambda: adapters.load_tampa(with_age=True)
    s2.TAMPA_SPLIT_FILE, s2.TAMPA_NAME, s2.tampa_loader = split_file, f"s2_tampa_{tag}", loader
    s3.TAMPA_SPLIT_FILE, s3.tampa_loader, s3.SUF = split_file, loader, f"_{tag}"
    s3.SMOKE = False                   # the S3 smoke switch would read sp["val"] as test itself; here the split file does it
    s2.log("tag", tag, "split", split_file)
    summ2, tab2 = {"tag": tag, "split_file": split_file, "limits": {k: float(v) for k, v in s2.l1.LIMITS.items()},
                   "budget": s2.BUDGET, "heldout_attack_types": s2.HELDOUT}, []
    s2.run_tampa(summ2, tab2)
    s2.jdump(f"s2_summary_tampa_{tag}.json", summ2)
    (OUT / f"s2_tables_tampa_{tag}.md").write_text("\n".join(tab2))
    summ3, tab3 = {"tag": tag, "split_file": split_file, "budget": s3.BUDGET, "heldout_attack_types": s3.HELDOUT,
                   "soft_layers_outside_union": list(s3.SOFT_LAYERS)}, []
    s3.run_tampa(False, summ3, tab3)
    s2.jdump(f"s3_summary_tampa_{tag}.json", summ3)
    (OUT / f"s3_tables_tampa_{tag}.md").write_text("\n".join(tab3))
    s2.log("done", tag)


if __name__ == "__main__":
    main()
