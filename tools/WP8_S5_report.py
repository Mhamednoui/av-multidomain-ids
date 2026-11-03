"""WP8 S5: acceptance check of rules C1, C2 (CAN) and V1 (V2X) from results/WP8/S5/parts/*.json -> results/WP8/S5/S5_acceptance.json and a markdown table."""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "results" / "WP8" / "S5" / "parts"
val = [json.load(open(p)) for p in sorted(P.glob("can_val_*.json"))]
lng = [json.load(open(p)) for p in sorted(P.glob("can_long_*.json"))]
allc = val + lng
v2 = [json.load(open(p)) for p in sorted(P.glob("v2x_*.json"))]
out = {}
cnt = lambda r: r["alarm_mismatch"] + r["id_mismatch"] + r["reason_mismatch"] + r["t_mismatch"] + r["detail_mismatch"] + r["motion_mismatch"]
out["C1"] = {"captures_val": len(val), "captures_long_train": len(lng), "windows_compared": int(sum(r["windows_batch"] for r in allc)), "frames": int(sum(r["frames"] for r in allc)),
             "mismatches": int(sum(cnt(r) for r in allc)), "max_abs_diff": float(max(r["max_abs_diff"] for r in allc)), "met": all(cnt(r) == 0 and r["max_abs_diff"] <= 1e-12 for r in allc)}
out["C2"] = {"p99_ms_per_capture": {r["name"]: round(r["window_ms"]["p99"], 2) for r in allc}, "max_p99_ms": float(max(r["window_ms"]["p99"] for r in allc)),
             "growth": {r["name"]: r["growth"] for r in lng if "growth" in r}, "longest_capture": max(allc, key=lambda r: r["frames"])["name"]}
lg = out["C2"]["longest_capture"]
gr = [r["growth"]["ratio"] for r in allc if r["name"] == lg and "growth" in r]
out["C2"]["met"] = out["C2"]["max_p99_ms"] <= 150 and bool(gr) and gr[0] <= 1.5
out["C2"]["v3_reference"] = "v3 prefix re-score: 0.14 s median below 100k frames, 2.3 s above 600k frames (reports/WP7_S2.md)"
V = {}
for src in ("veremi", "v2aix"):
    a = [x for x in v2 if x["source"] == src]
    cps = np.array([x["compute_s"] / max(x["stream_s"], 1.0) for x in a])           # stream duration floored at 1 s (single-message recordings have no span)
    cps_raw = np.array([x["compute_per_stream_s"] for x in a])
    V[src] = {"egos": len(a), "messages": int(sum(x["messages"] for x in a)), "stream_s_total": float(sum(x["stream_s"] for x in a)),
              "compute_per_stream_s_max": float(cps.max()), "compute_per_stream_s_p95": float(np.percentile(cps, 95)), "share_egos_le_0.5": float((cps <= 0.5).mean()),
              "egos_with_span_lt_5s": int(sum(x["stream_s"] < 5 for x in a)), "egos_le_0.5_unfloored": float((cps_raw <= 0.5).mean()),
              "msg_ms_p99_max": float(max(x["msg_ms"]["p99"] for x in a)), "msg_ms_median": float(np.median([x["msg_ms"]["median"] for x in a])),
              "raw_mismatch_rows": int(sum(x["mismatch_rows"] for x in a)), "raw_mismatch_rows_unexplained": int(sum(x["mismatch_rows_unexplained"] for x in a)),
              "reordered_messages": int(sum(x["reordered"] for x in a)), "egos_with_reordered": int(sum(x["reordered"] > 0 for x in a)), "ties": int(sum(x["ties"] for x in a)),
              "evidence_alarm_mismatch": int(sum(x["evidence_alarm_mismatch"] + x["evidence_layer_or_reason_mismatch"] for x in a)),
              "evidence_score_max_abs_diff_exact_egos": float(max(x["evidence_score_max_abs_diff"] for x in a if x["mismatch_rows"] == 0)),
              "egos_exactly_identical": int(sum(x["mismatch_rows"] == 0 and x["evidence_alarm_mismatch"] == 0 for x in a))}
out["V1"] = V
out["V1"]["met"] = all(V[s]["share_egos_le_0.5"] >= 0.95 and V[s]["msg_ms_p99_max"] <= 100 and V[s]["raw_mismatch_rows_unexplained"] == 0 for s in V)
out["V1"]["strict_zero_mismatch_met"] = all(V[s]["raw_mismatch_rows"] == 0 for s in V)
(ROOT / "results" / "WP8" / "S5" / "S5_acceptance.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
