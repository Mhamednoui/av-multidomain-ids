"""WP9 B3 post-hoc diagnostic (validation only): which of (sendTime, sender id, pseudonym id) predicts attack, and is it the pseudonym prefix (pseudonym churn)?
Run: python -I -u -W ignore tools/WP9_B3_proxy_diag.py -> results/WP9/B3_proxy_diag.json"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tools")); sys.dont_write_bytecode = True
import numpy as np, pandas as pd, xgboost as xgb
from sklearn.metrics import roc_auc_score
import WP9_B3_lib as L

_, mtr = L.load_part("train"); _, mva = L.load_part("val")
ytr, yva = (mtr["label"].to_numpy() > 0).astype(int), (mva["label"].to_numpy() > 0).astype(int)
for d in (mtr, mva):
    d["t_day"] = d["t"] % 86400.0
    d["pseudo_prefix"] = d["pseudo"] // 100000000        # pseudonym index digit(s): 1 = first pseudonym of the sender
    d["pseudo_len"] = d["pseudo"].astype(str).str.len()
    d["n_pseudo_of_sender"] = d.groupby("sender")["pseudo"].transform("nunique")
out = {}
for nm, cols in {"t_only": ["t"], "sender_only": ["sender"], "pseudo_only": ["pseudo"], "pseudo_prefix_only": ["pseudo_prefix"], "t_sender": ["t", "sender"],
                 "t_sender_pseudo": ["t", "sender", "pseudo"]}.items():
    m = xgb.XGBClassifier(n_estimators=200, max_depth=6, learning_rate=0.1, tree_method="hist", n_jobs=2, random_state=42, eval_metric="logloss")
    m.fit(mtr[cols].to_numpy(np.float64), ytr)
    out[nm] = float(roc_auc_score(yva, m.predict_proba(mva[cols].to_numpy(np.float64))[:, 1]))
    print(nm, round(out[nm], 3), flush=True)
L.jd(out, L.OUT / "B3_proxy_diag.json")
