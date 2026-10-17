"""
Temporal Alert Correlator — AV-IDS
====================================
Post-processing layer that sits AFTER FusionEngine.predict().
Maintains a sliding window of recent FusionAlerts and escalates the threat
level when multiple consecutive alerts are suspicious.

This solves the stray-packet problem: a single LOW alert could be noise,
but 6 consecutive LOW/HIGH alerts on the same domain is a confirmed attack.

Pipeline position:
    raw data -> WindowEngine -> domain runners -> FusionEngine -> TemporalCorrelator -> final alert

No existing model or code needs to change.

Usage:
    from temporal.temporal_correlator import TemporalCorrelator

    tc = TemporalCorrelator(window=10, threshold=0.6)
    for alert in stream:
        final = tc.correlate(alert)
        print(final.threat_label, final.escalated)
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class CorrelatedAlert:
    """
    Wraps a FusionAlert with temporal correlation metadata.

    Fields
    ------
    threat_level      : int   0-4 (possibly escalated from original)
    threat_label      : str   NORMAL/LOW/MEDIUM/HIGH/CRITICAL
    attack_score      : float original fusion attack score
    is_attack         : bool  threat_level >= 2
    escalated         : bool  True if level was bumped by correlator
    escalation_reason : str   human-readable reason for escalation
    window_attack_rate: float fraction of recent window that were attacks
    persistent_domain : str   domain that consistently triggered in the window
    triggered_by      : list  from original FusionAlert
    original_level    : int   level before correlation
    timestamp         : str   ISO timestamp of this alert
    """
    threat_level      : int
    threat_label      : str
    attack_score      : float
    is_attack         : bool
    escalated         : bool
    escalation_reason : str
    window_attack_rate: float
    persistent_domain : str
    triggered_by      : List[str]
    original_level    : int
    timestamp         : str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


LEVEL_LABELS = {0: "NORMAL", 1: "LOW", 2: "MEDIUM", 3: "HIGH", 4: "CRITICAL"}


class TemporalCorrelator:
    """
    Sliding-window alert correlator.

    Parameters
    ----------
    window    : int   — number of recent alerts to consider (default 10)
    threshold : float — fraction of window that must be attacks to trigger escalation (default 0.6)
    max_level : int   — maximum threat level after escalation (default 4 = CRITICAL)

    Escalation rule:
        If attack_rate in window >= threshold AND current alert is already
        LOW or above -> bump threat_level by +1 (capped at max_level).

    Clearing rule:
        If attack_rate in window drops below threshold/2 -> threat_level is
        NOT escalated even if current alert is low-level.
    """

    def __init__(self, window: int = 10, threshold: float = 0.6,
                 max_level: int = 4):
        self.window    = window
        self.threshold = threshold
        self.max_level = max_level
        self._history: deque = deque(maxlen=window)

    # ── public API ───────────────────────────────────────────────────────────

    def correlate(self, alert) -> CorrelatedAlert:
        """
        Process one FusionAlert (dataclass or dict) and return a CorrelatedAlert.
        The threat level may be escalated based on recent history.
        """
        d = self._to_dict(alert)

        original_level = d.get("threat_level", 0)
        attack_score   = d.get("attack_score", 0.0)
        triggered_by   = list(d.get("triggered_by", []))
        is_atk         = original_level >= 2

        # record this alert in history
        self._history.append({
            "is_attack":    is_atk,
            "level":        original_level,
            "triggered_by": triggered_by,
        })

        # compute window statistics
        rate              = self._attack_rate()
        persistent_domain = self._most_persistent_domain()

        # escalation decision
        escalated         = False
        escalation_reason = ""
        new_level         = original_level

        if rate >= self.threshold and original_level >= 1:
            new_level = min(original_level + 1, self.max_level)
            escalated = new_level > original_level
            if escalated:
                escalation_reason = (
                    f"{rate:.0%} of last {len(self._history)} alerts were attacks "
                    f"(threshold={self.threshold:.0%}); "
                    f"persistent domain: {persistent_domain}"
                )

        new_label = LEVEL_LABELS[new_level]

        return CorrelatedAlert(
            threat_level       = new_level,
            threat_label       = new_label,
            attack_score       = attack_score,
            is_attack          = new_level >= 2,
            escalated          = escalated,
            escalation_reason  = escalation_reason,
            window_attack_rate = rate,
            persistent_domain  = persistent_domain,
            triggered_by       = triggered_by,
            original_level     = original_level,
        )

    def reset(self) -> None:
        """Clear history — call between test scenarios."""
        self._history.clear()

    @property
    def history_size(self) -> int:
        return len(self._history)

    def window_summary(self) -> Dict[str, Any]:
        """Return current window statistics without processing a new alert."""
        return {
            "window_size":    self.window,
            "filled":         len(self._history),
            "attack_rate":    self._attack_rate(),
            "persistent_domain": self._most_persistent_domain(),
        }

    # ── private helpers ──────────────────────────────────────────────────────

    def _attack_rate(self) -> float:
        if not self._history:
            return 0.0
        return sum(1 for h in self._history if h["is_attack"]) / len(self._history)

    def _most_persistent_domain(self) -> str:
        """Return the domain that appeared most often in triggered_by across the window."""
        counts: Dict[str, int] = {}
        for h in self._history:
            for d in h["triggered_by"]:
                counts[d] = counts.get(d, 0) + 1
        if not counts:
            return "-"
        return max(counts, key=counts.__getitem__)

    @staticmethod
    def _to_dict(alert) -> Dict[str, Any]:
        if isinstance(alert, dict):
            return alert
        if hasattr(alert, "__dataclass_fields__"):
            d = {}
            for f in alert.__dataclass_fields__:
                d[f] = getattr(alert, f)
            return d
        raise TypeError(f"Unsupported alert type: {type(alert)}")
