"""WP0 S2: run the harness on the synthetic 3-layer toy domain -> results/WP0/toy_example.{json,md}.
Run from codes_v3/: python -u -W ignore tools/WP0_toy_example.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import results_dir
from common.evaluate import evaluate_domain, markdown_table
from common.toy import toy_run

val, test = toy_run(seed=0)
res = evaluate_domain("toy_example", val, test, wp="WP0")
print(markdown_table(res))
print("combiner method:", res["combined"]["method"], res["combined"]["method_selection"])
