"""WP2 S7: example outputs of the frozen CanDomain for WP6 / WP7 (validation capture correlated_signal_attack_2_masquerade; not a test capture).
Writes results/WP2/s7_domain/example_evidence_correlated_signal.json and example_can_motion_estimates.json.
Usage: python -u -W ignore tools/WP2_S7_fixtures.py
"""
import json
from dataclasses import asdict

from WP2_S7_lib import OUT, load_unit
from can.domain import CanDomain

dom = CanDomain.load(OUT / "s7_domain")
U = load_unit("correlated_signal_attack_2_masquerade")
comb, per = dom.score_capture(U.t, U.id, U.dlc, U.B, name="correlated_signal_attack_2_masquerade")
first = next(i for i, e in enumerate(comb) if e.alarm)
sel = comb[max(first - 2, 0): first + 3]
(OUT / "s7_domain" / "example_evidence_correlated_signal.json").write_text(json.dumps([asdict(e) for e in sel], indent=1))
est = dom.motion_estimates(U.t, U.id, U.dlc, U.B)
(OUT / "s7_domain" / "example_can_motion_estimates.json").write_text(json.dumps([asdict(e) for e in est[3:9]], indent=1))
print(json.dumps(asdict(sel[2]), indent=1)[:1500])
print(asdict(est[5]))
