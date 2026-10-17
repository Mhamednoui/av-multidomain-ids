"""
Window Engine — AV-IDS
======================
Buffers incoming sensor data into time windows before passing to domain runners.
This is how the IDS works in a real AV deployment where data arrives packet by packet.

Instead of running the model on every single packet (infeasible at 5000 pkt/s),
we buffer N packets over a time window, then flush the window to the runner once.

Supported domains:
  - CAN     : buffer CAN_WINDOW_SIZE packets → pass as batch to CANDetector
  - GPS     : buffer GPS_WINDOW_SIZE frames  → pass as batch (needs consecutive frames for diff features)
  - Network : pass-through (already flow-level, no buffering needed)
  - LiDAR   : pass-through (already one scan per frame)

Usage:
    from windowing.window_engine import CANWindow, GPSWindow

    can_win = CANWindow(window_size=50)
    for packet in stream:
        can_win.push(packet)
        if can_win.ready():
            result = can_det.predict(can_win.flush())
"""
from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional


# ── default window sizes ──────────────────────────────────────────────────────
# CAN bus fires ~5000 pkt/s. A 100ms window = ~500 packets.
# For demo purposes we use smaller defaults that are easy to fill quickly.
CAN_WINDOW_DEFAULT = 50    # ~10ms worth of CAN traffic at 5000 pkt/s
GPS_WINDOW_DEFAULT = 10    # 1s worth of GPS fixes at 10 Hz


class BaseWindow:
    """
    Sliding window buffer for a single sensor domain.

    Parameters
    ----------
    window_size : int   — number of packets/frames to accumulate before flushing
    stride      : int   — how many new packets between flushes (default = window_size → tumbling)
                          stride < window_size → overlapping windows
    """

    def __init__(self, window_size: int, stride: Optional[int] = None):
        self.window_size = window_size
        self.stride      = stride if stride is not None else window_size
        self._buffer: deque = deque(maxlen=window_size)
        self._since_flush   = 0

    def push(self, packet: Dict[str, Any]) -> None:
        """Add one packet/frame to the buffer."""
        self._buffer.append(packet)
        self._since_flush += 1

    def ready(self) -> bool:
        """True when the window is full AND stride condition is met."""
        return (len(self._buffer) == self.window_size and
                self._since_flush >= self.stride)

    def flush(self) -> List[Dict[str, Any]]:
        """
        Return the current window contents as a list of dicts — ready to pass
        directly to the domain runner's predict() method.
        Resets the stride counter (does NOT clear the buffer, so windows overlap
        when stride < window_size).
        """
        self._since_flush = 0
        return list(self._buffer)

    def reset(self) -> None:
        """Clear the buffer entirely (e.g. after a domain switch or test reset)."""
        self._buffer.clear()
        self._since_flush = 0

    @property
    def size(self) -> int:
        return len(self._buffer)

    def __repr__(self) -> str:
        return (f"{self.__class__.__name__}("
                f"window={self.window_size}, stride={self.stride}, "
                f"buffered={self.size}, since_flush={self._since_flush})")


class CANWindow(BaseWindow):
    """
    Window for CAN bus packets.

    Each packet must have: ID (int), DATA_0 … DATA_7 (int 0-255).
    On flush, returns a list of dicts — pass directly to CANDetector.predict().

    The CANDetector.predict() already runs feature engineering (byte diffs,
    entropy, ID frequency) across the batch, so a larger window gives more
    context for the rolling diff features.

    Recommended window_size: 50–500 depending on latency tolerance.
    """

    def __init__(self, window_size: int = CAN_WINDOW_DEFAULT,
                 stride: Optional[int] = None):
        super().__init__(window_size, stride)

    def aggregate(self) -> Dict[str, Any]:
        """
        Optional: return a single representative packet (the last one) when
        the runner is called in single-packet mode. Use flush() for batch mode.
        """
        if not self._buffer:
            raise RuntimeError("Buffer is empty — call push() first.")
        return self._buffer[-1]


class GPSWindow(BaseWindow):
    """
    Window for GPS/IMU frames.

    GPS temporal delta features (lat_delta, vel_delta, etc.) require consecutive
    frames. A window of at least 10 frames (1 second at 10 Hz) gives stable deltas.

    Each frame must have all GPS columns the GPSDetector expects.
    On flush, returns a list of dicts — pass directly to GPSDetector.predict().

    The GPSDetector._engineer() calls .diff() on the batch, so the first frame
    in each window will have delta=0. This is acceptable and matches real deployment
    (the first GPS fix of a drive always has delta=0).
    """

    def __init__(self, window_size: int = GPS_WINDOW_DEFAULT,
                 stride: Optional[int] = None):
        super().__init__(window_size, stride)


class NetworkWindow:
    """
    Pass-through — network flows are already aggregated at the flow level
    (CICIDS2017 features are per-flow, not per-packet).

    This class exists only for API symmetry. push() stores the flow dict,
    ready() is always True after the first push, flush() returns it.
    """

    def __init__(self):
        self._flow: Optional[Dict] = None

    def push(self, flow: Dict[str, Any]) -> None:
        self._flow = flow

    def ready(self) -> bool:
        return self._flow is not None

    def flush(self) -> List[Dict[str, Any]]:
        f = self._flow
        self._flow = None
        return [f]

    def reset(self) -> None:
        self._flow = None

    def __repr__(self) -> str:
        return f"NetworkWindow(has_flow={self._flow is not None})"


class LiDARWindow:
    """
    Pass-through — LiDAR is already one scan per frame (one .bin file or N×4 array).
    Each scan is self-contained; no buffering needed.

    This class exists only for API symmetry.
    """

    def __init__(self):
        self._scan = None

    def push(self, scan) -> None:
        """scan can be a file path (str/Path) or an N×4 numpy array."""
        self._scan = scan

    def ready(self) -> bool:
        return self._scan is not None

    def flush(self):
        s = self._scan
        self._scan = None
        return s

    def reset(self) -> None:
        self._scan = None

    def __repr__(self) -> str:
        return f"LiDARWindow(has_scan={self._scan is not None})"


class MultiDomainWindow:
    """
    Convenience wrapper that manages all four domain windows together.

    Usage:
        mdw = MultiDomainWindow(can_size=50, gps_size=10)
        mdw.push_can(packet)
        mdw.push_gps(frame)
        mdw.push_network(flow)
        mdw.push_lidar(scan)

        if mdw.all_ready():
            inputs = mdw.flush_all()
            # inputs = {"can": [...], "gps": [...], "network": [...], "lidar": ...}
    """

    def __init__(self, can_size: int = CAN_WINDOW_DEFAULT,
                 gps_size: int = GPS_WINDOW_DEFAULT,
                 can_stride: Optional[int] = None,
                 gps_stride: Optional[int] = None):
        self.can     = CANWindow(can_size, can_stride)
        self.gps     = GPSWindow(gps_size, gps_stride)
        self.network = NetworkWindow()
        self.lidar   = LiDARWindow()

    def push_can(self, packet: Dict)     -> None: self.can.push(packet)
    def push_gps(self, frame: Dict)      -> None: self.gps.push(frame)
    def push_network(self, flow: Dict)   -> None: self.network.push(flow)
    def push_lidar(self, scan)           -> None: self.lidar.push(scan)

    def all_ready(self) -> bool:
        return (self.can.ready() and self.gps.ready() and
                self.network.ready() and self.lidar.ready())

    def domain_status(self) -> Dict[str, bool]:
        return {
            "can":     self.can.ready(),
            "gps":     self.gps.ready(),
            "network": self.network.ready(),
            "lidar":   self.lidar.ready(),
        }

    def flush_all(self) -> Dict[str, Any]:
        return {
            "can":     self.can.flush(),
            "gps":     self.gps.flush(),
            "network": self.network.flush(),
            "lidar":   self.lidar.flush(),
        }

    def reset(self) -> None:
        self.can.reset()
        self.gps.reset()
        self.network.reset()
        self.lidar.reset()

    def __repr__(self) -> str:
        s = self.domain_status()
        return (f"MultiDomainWindow("
                f"can={self.can.size}/{self.can.window_size} ready={s['can']}, "
                f"gps={self.gps.size}/{self.gps.window_size} ready={s['gps']}, "
                f"network={s['network']}, lidar={s['lidar']})")
