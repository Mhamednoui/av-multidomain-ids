"""WP2 S4: summary of the final (all 8 clean ambient captures) model of variant 0 -> results/WP2/s4_final_model.json."""
import json
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP2_S4_run as R
from can import l2b_signals as Z

M = pickle.load(open(R.CACHE / "models" / "h0__final.pkl", "rb"))
d = Z.model_summary(M)
names = {"0xd0.5": "speedometer", "0xd0.2": "reverse light bit", "0x6e0.0": "wheel speed 1", "0x6e0.1": "wheel speed 2", "0x6e0.2": "wheel speed 3",
         "0x6e0.3": "wheel speed 4", "0x4e7.1": "coolant temperature byte", "0x498.3": "speed-like (corr 1.0 with speedometer)",
         "0x20e.1": "speed-like (corr 1.0 with speedometer)"}
d["meaning_from_train_metadata_and_correlation"] = names
d["reverse_bit_joint_partners"] = [[f"{a[0]:#x}.{a[1]}", f"{b[0]:#x}.{b[1]}", round(n, 3)] for a, b, _, _, _, n in M.joint if (0xd0, 2) in (a, b)]
json.dump(d, open(R.OUT / "s4_final_model.json", "w"), indent=1)
print(d["classes"], d["linear_pairs"], d["joint_pairs"], d["reverse_bit_joint_partners"])
