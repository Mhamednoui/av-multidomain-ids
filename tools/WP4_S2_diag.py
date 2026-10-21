"""WP4 S2 diagnostic on TRAIN / VALIDATION only (no test): why the source-agnostic allow-list detects so much in D10.
Writes results/WP4/s2_diag_val.json."""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from network import l1
from tools.WP4_S2_lib import load_d10

d = load_d10()
tr = d[(d.family == "BENIGN") & (d.split == "train")]
vb = d[(d.family == "BENIGN") & (d.split == "val")]
va = d[(d.family != "BENIGN") & (d.split == "val")]
out = {}
srv = "192.168.10.50"
out["benign_train_share_dst_web_server"] = float((tr.dst_ip == srv).mean())
out["benign_train_flows_dst_web_server"] = int((tr.dst_ip == srv).sum())
out["benign_train_flows_dst_web_server_port80"] = int(((tr.dst_ip == srv) & (tr.dst_port == 80)).sum())
out["benign_val_share_dst_web_server"] = float((vb.dst_ip == srv).mean())
out["attack_val_share_dst_web_server"] = float((va.dst_ip == srv).mean())
L = l1.AllowService().fit(tr).calibrate(vb)
sc = L.calibrator.transform(L.raw_scores(va))
al = sc >= L.threshold
out["val_allow_service_detection_by_family_dst_web_server"] = {
    f: {"share_to_web_server": float((g.dst_ip == srv).mean()), "det_web_server": float(al[(va.family == f).to_numpy() & (va.dst_ip == srv).to_numpy()].mean()) if ((va.family == f) & (va.dst_ip == srv)).any() else None,
        "det_other_dst": float(al[(va.family == f).to_numpy() & (va.dst_ip != srv).to_numpy()].mean()) if ((va.family == f) & (va.dst_ip != srv)).any() else None}
    for f, g in va.groupby("family", observed=True)}
yb = L.calibrator.transform(L.raw_scores(vb)) >= L.threshold
out["val_benign_alarms_to_web_server_share"] = float((vb.dst_ip.to_numpy()[yb] == srv).mean())
out["attacker_as_src_benign_train"] = int((tr.src_ip == "172.16.0.1").sum())
out["attacker_as_dst_benign_train"] = int((tr.dst_ip == "172.16.0.1").sum())
json.dump(out, open("results/WP4/s2_diag_val.json", "w"), indent=1)
print(json.dumps(out, indent=1))
