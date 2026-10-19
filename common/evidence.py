"""Evidence: the one record every check (rule, physics, model) emits for one sample.

Inputs: produced by Layer.score / DomainCombiner. Outputs: plain dataclass, JSON friendly.
Reference: ARCHITECTURE.md section 2.
"""
from dataclasses import dataclass, field, asdict

DOMAINS = ("network", "can", "gps", "lidar", "v2x", "cross")


@dataclass
class Evidence:
    domain: str          # "network" | "can" | "gps" | "lidar" | "v2x" | "cross"
    layer: str           # "L1" | "L2a" | "L2b" | ... | "L3" | "L4" | "combined"
    name: str            # stable id of the check, e.g. "gps.cusum_innovation"
    t: float             # stream time of the sample (seconds)
    score: float         # 0..1, monotone in attack-ness, calibrated on validation
    alarm: bool          # score >= this check's threshold at the agreed budget
    reason: str = ""     # one plain sentence when alarm is True, else ""
    details: dict = field(default_factory=dict)   # observed, expected, residual, ...
    sample_id: str = ""  # links back to the sample

    def to_dict(self) -> dict:
        return asdict(self)
