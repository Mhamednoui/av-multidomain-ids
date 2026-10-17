"""
Response Module — AV-IDS
========================
Receives a FusionAlert and takes the appropriate action based on threat level.

  NORMAL   (0) → nothing
  LOW      (1) → log to file
  MEDIUM   (2) → log + console warning
  HIGH     (3) → log + write alert JSON to alerts/
  CRITICAL (4) → log + alert JSON + write ISOLATE flag file

Usage:
    from response.response_module import ResponseModule
    rm = ResponseModule()
    rm.handle(alert)
"""
import json
import logging
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
ALERTS_DIR = HERE / "alerts"
ALERTS_DIR.mkdir(exist_ok=True)

LOG_FILE = HERE / "ids_alerts.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger("AV-IDS")


class ResponseModule:
    """
    Takes a FusionAlert (or its dict form) and triggers the appropriate response.

    Parameters
    ----------
    alerts_dir : Path  — where to write HIGH/CRITICAL alert JSON files
    isolate_path : Path — path of the ISOLATE flag file written on CRITICAL
    """

    def __init__(self, alerts_dir: Path = ALERTS_DIR,
                 isolate_path: Path = HERE / "ISOLATE"):
        self.alerts_dir   = Path(alerts_dir)
        self.isolate_path = Path(isolate_path)
        self.alerts_dir.mkdir(exist_ok=True)
        self._counter = 0

    # ------------------------------------------------------------------

    def handle(self, alert) -> dict:
        """
        Process one FusionAlert.  Returns the action dict that was taken.
        `alert` can be a FusionAlert dataclass or the dict from alert_to_dict().
        """
        self._counter += 1

        # normalise to dict
        if hasattr(alert, "__dataclass_fields__"):
            d = self._dataclass_to_dict(alert)
        else:
            d = dict(alert)

        level = d.get("threat_level", 0)
        label = d.get("threat_label", "NORMAL")
        score = d.get("attack_score", 0.0)
        by    = d.get("triggered_by", [])
        ts    = datetime.now().isoformat(timespec="seconds")

        action = {"timestamp": ts, "threat_label": label,
                  "attack_score": score, "triggered_by": by, "actions_taken": []}

        if level == 0:
            # NORMAL — silent
            pass

        elif level == 1:
            # LOW — log only
            logger.info(f"[LOW]      score={score:.3f}  triggered_by={by}")
            action["actions_taken"].append("logged")

        elif level == 2:
            # MEDIUM — log + console warning
            logger.warning(f"[MEDIUM]   score={score:.3f}  triggered_by={by}")
            action["actions_taken"].append("logged")
            action["actions_taken"].append("console_warning")

        elif level == 3:
            # HIGH — log + alert JSON
            logger.error(f"[HIGH]     score={score:.3f}  triggered_by={by}")
            path = self._write_alert_json(ts, d, "HIGH")
            action["actions_taken"].extend(["logged", "alert_json"])
            action["alert_file"] = str(path)

        elif level >= 4:
            # CRITICAL — log + alert JSON + ISOLATE flag
            logger.critical(f"[CRITICAL] score={score:.3f}  triggered_by={by}  --> ISOLATING")
            path = self._write_alert_json(ts, d, "CRITICAL")
            self._write_isolate_flag(ts, d)
            action["actions_taken"].extend(["logged", "alert_json", "isolate_flag"])
            action["alert_file"]   = str(path)
            action["isolate_file"] = str(self.isolate_path)

        return action

    # ------------------------------------------------------------------

    def clear_isolate(self):
        """Remove the ISOLATE flag file once the threat is resolved."""
        if self.isolate_path.exists():
            self.isolate_path.unlink()
            logger.info("ISOLATE flag cleared.")

    def summary(self) -> dict:
        """Return count of alert files per threat level in alerts/."""
        counts = {"HIGH": 0, "CRITICAL": 0}
        for f in self.alerts_dir.glob("*.json"):
            for lvl in counts:
                if lvl in f.name:
                    counts[lvl] += 1
        counts["total_handled"] = self._counter
        return counts

    # ------------------------------------------------------------------  private

    def _write_alert_json(self, ts: str, alert_dict: dict, level: str) -> Path:
        safe_ts = ts.replace(":", "-")
        fname   = self.alerts_dir / f"{level}_{safe_ts}_{self._counter:04d}.json"
        payload = {"timestamp": ts, "threat_level": level, **alert_dict}
        fname.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return fname

    def _write_isolate_flag(self, ts: str, alert_dict: dict):
        content = {
            "timestamp":    ts,
            "reason":       "CRITICAL threat detected",
            "triggered_by": alert_dict.get("triggered_by", []),
            "attack_score": alert_dict.get("attack_score", 0.0),
        }
        self.isolate_path.write_text(
            json.dumps(content, indent=2), encoding="utf-8")

    @staticmethod
    def _dataclass_to_dict(obj) -> dict:
        """Convert FusionAlert dataclass to plain dict, handling nested structures."""
        d = {}
        for field in obj.__dataclass_fields__:
            val = getattr(obj, field)
            if hasattr(val, "__dataclass_fields__"):
                val = ResponseModule._dataclass_to_dict(val)
            d[field] = val
        return d
