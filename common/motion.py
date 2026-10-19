"""MotionEstimate: ego motion published by any domain that observes it (CAN wheel speed,
GPS/IMU, LiDAR odometry, V2X self-report). Used by crossdomain/ motion witnesses.

Reference: ARCHITECTURE.md section 3.
"""
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class MotionEstimate:
    t: float                                   # stream time (s)
    source: str                                # "can" | "gps" | "imu" | "lidar" | "v2x"
    speed: Optional[float] = None              # m/s
    yaw_rate: Optional[float] = None           # rad/s
    displacement: Optional[Tuple[float, float]] = None  # (dx, dy) in metres over the last second
    sigma: float = 1.0                         # 1-sigma uncertainty of the speed (m/s); larger = less trusted
