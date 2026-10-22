"""WP3 S3: append the phantom-appearance table (from phantom_appearance.json) to results/WP3/S3/S3_tables.md."""
import json
from pathlib import Path
R = Path(__file__).resolve().parent.parent / "results" / "WP3" / "S3"
j = json.loads((R / "phantom_appearance.json").read_text())
L = ["", "## Phantom appearance in the object table (validation drives, every 12th scan, calibrated single-return phantoms; add == replace)", "",
     "one = an object holds >= 60 % of the phantom points AND its centroid is within 2 m of the phantom centre; pure = phantom points >= 80 % of that object; merged = same but < 80 %.", "",
     "| case | n | median phantom pts | seg. frac | one object | one, pure | one, merged with real | split / absent | median object pts | median length m | median rings | car-like |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
for k, v in j.items():
    L.append(f"| {k} | {v['n']} | {v['median_phantom_points']:.0f} | {v['segmented_frac']:.2f} | {100*v['one_object']:.0f} % | {100*v['one_pure']:.0f} % | {100*v['one_merged_with_real']:.0f} % | {100*v['split_or_absent']:.0f} % | {v['median_obj_points']:.0f} | {v['median_len']:.1f} | {v['median_rings']:.0f} | {100*v['carlike_frac']:.0f} % |")
t = R / "S3_tables.md"
s = t.read_text().split("\n## Phantom appearance")[0].rstrip("\n")
t.write_text(s + "\n" + "\n".join(L))
print("\n".join(L))
