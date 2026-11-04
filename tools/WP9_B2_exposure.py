"""WP9 B2: register test exposure -> results/WP9/B2_exposure.json (from the locks and the *_test.json files).
For each (table, protocol): test rows, lock part hash, when scored, model, how many times (1), overlap of the B2 test rows with the v3 / WP4 / WP8 D10 splits
(only the original-label table D10o shares flows with the v3 split; D10e / D23x are different flow extractions of the same captures).
Run (codes_v3): python -u -W ignore -I tools/WP9_B2_exposure.py
"""
import glob, json, os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RES = os.path.join(ROOT, "results", "WP9")
SAME_DAYS = {"D10o": "same flows as the v3 (WP4/WP8) D10 table", "D10e": "different flow extraction (fixed CICFlowMeter) of the same CICIDS2017 capture days; no row identity with the v3 table",
             "D23x": "different dataset from the v3 D23 table used in WP4 (regenerated flows); the v3 D23 test was never used for model selection in B2"}


def main():
    out = {"note": "B2 is a NEW split, distinct from the v3/WP8 D10 test. Each test part below was scored exactly once with the model selected on its own validation part (tools/WP9_B2_run.py refuses to rescore).",
           "v3_d10_test_definition": "last 20% (flow count) of every period of every day, WP4 split column 'test' (network/flows.py time_split)", "entries": []}
    for p in sorted(glob.glob(os.path.join(RES, "B2", "*_test.json"))):
        t = json.load(open(p))
        tab, proto = t["table"], t["protocol"]
        lock = json.load(open(os.path.join(ROOT, "locks", "WP9_%s.json" % tab)))
        pr = lock["protocols"][proto]
        ov = (pr.get("v3_split_overlap") or {}).get("test")
        out["entries"].append({"table": tab, "protocol": proto, "test_rows": t["test_rows"], "lock": "locks/WP9_%s.json" % tab, "part_sha256": pr["part_sha256"],
                               "scored_at": t["time"], "times_scored": 1, "model": t["cand"]["id"], "relation_to_v3": SAME_DAYS[tab],
                               "b2_test_rows_by_v3_split": ov, "scores": "results/WP9/scores/B2/%s_%s_test.npz" % (tab, proto)})
    json.dump(out, open(os.path.join(RES, "B2_exposure.json"), "w"), indent=1)
    print(json.dumps(out["entries"], indent=1)[:1500])


if __name__ == "__main__":
    main()
