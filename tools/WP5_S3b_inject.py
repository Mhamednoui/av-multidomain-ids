"""WP5 S3b step 3: VeReMi-taxonomy attacks injected on real V2AIX CAMs (v2x/v2aix_inject.py), detected by the stack at the V2AIX-validation thresholds (variant B),
Mobile and Stationary separately. Scenarios are built from the recordings of ONE split only (test; --smoke = validation as stand-in) and scored once.
Per scenario and configuration: message-level detection on all injected rows and on scored rows (row kind 0 of v2x.l4.row_kinds), 95% cluster-bootstrap CI over recordings,
sender level (>= 3 alarms and >= k val alarms among the attacker's injected messages), and the false-alarm rate on the scenario's genuine messages.
Outputs: results/WP5/s3b_inject_<env>.json (or _smoke). Run from codes_v3/: python -I -u -W ignore tools/WP5_S3b_inject.py [--smoke] [--env Mobile|Stationary] [--types 3,11]
No per-message output is written (licence)."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP5_S3b_lib as L

import numpy as np
import pandas as pd

from v2x import l4, v2aix_inject as inj
from v2x import v2aix_eval as ev

T0 = time.time()
SMOKE = "--smoke" in sys.argv
CFGS = ["physics", "L1", "L2", "L3", "fresh", "physics+fresh", "range", "range_loc", "appear", "rx", "physics+range", "physics+rx"]


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def evaluate(sc, alarms, kinds, k_val, y):
    out = {}
    inj_df = sc[y]
    rec_n = int(inj_df["recording"].nunique())
    senders = inj_df["sender"].to_numpy()
    for cfg in CFGS:
        a = alarms[cfg]
        p, lo, hi, n = ev.boot_rate(inj_df, a[y], B=500)
        sk = kinds[y] == 0
        if sk.sum() > 0:
            ps, los, his, ns = ev.boot_rate(inj_df[sk], a[y][sk], B=500)
        else:
            ps, los, his, ns = None, None, None, 0
        cnt = pd.DataFrame({"s": senders, "a": a[y]}).groupby("s")["a"].sum()
        trk = pd.DataFrame({"tr": inj_df["track"].to_numpy(), "a": a[y]}).groupby("tr")["a"].sum()
        out[cfg] = {"msg_all": p, "msg_all_ci": [lo, hi], "n_injected": n, "msg_scored": ps, "msg_scored_ci": [los, his], "n_scored": ns,
                    "track_any": float((trk >= 1).mean()), "n_injected_tracks": int(len(trk)), "sender_k3": float((cnt >= 3).mean()), "sender_kval": float((cnt >= k_val[cfg]).mean()), "k_val": int(k_val[cfg]), "n_attackers": int(len(cnt)),
                    "fa_on_scenario_genuine": float(a[~y].mean()) if (~y).any() else None}
    out["_meta"] = {"n_injected": int(y.sum()), "n_recordings_with_injection": rec_n, "scored_share": float((kinds[y] == 0).mean()) if y.any() else None}
    return out


def main():
    envs = [arg("--env")] if arg("--env") else L.ENVS
    types = arg("--types").split(",") if arg("--types") else inj.ALL_TYPES
    for env in envs:
        S = L.Setup(env)
        log(env, "setup done; k val", S.k_val)
        df = S.val if SMOKE else L.load_env("test", env, S.sp)
        res = {"env": env, "smoke": SMOKE, "base_messages": int(len(df)), "base_senders": int(df["sender"].nunique()), "k_val": S.k_val, "types": {}}
        for code in types:
            t1 = time.time()
            try:
                sc, att = inj.build_scenario(df, code)
            except ValueError as e:
                res["types"][code] = {"error": str(e)}
                continue
            y = sc["injected"].to_numpy(bool)
            if not y.any():
                res["types"][code] = {"name": inj.type_name(code), "n_attackers_chosen": len(att), "n_injected": 0}
                log(env, code, "no injected rows")
                continue
            s = S.score(sc)
            kinds = np.asarray(l4.row_kinds(sc))
            r = evaluate(sc, s["alarm"], kinds, S.k_val, y)
            r["name"] = inj.type_name(code)
            r["n_attackers_chosen"] = len(att)
            r["scenario_messages"] = int(len(sc))
            res["types"][code] = r
            log(env, code, r["name"], "n inj", r["_meta"]["n_injected"], "physics all", round(r["physics"]["msg_all"], 3), "scored", r["physics"]["msg_scored"], "rx", round(r["rx"]["msg_all"], 3),
                f"{time.time() - t1:.0f}s")
            (L.OUT / (f"s3b_inject_{env}" + ("_smoke" if SMOKE else "") + ".json")).write_text(json.dumps(res, indent=1, default=float))
    log("done")


if __name__ == "__main__":
    main()
