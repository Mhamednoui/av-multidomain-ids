"""WP6 S1: SIMULATED CAN wheel-speed frames (ROAD 0x6e0 layout) from KITTI OXTS, decoded by the frozen CanDomain.

Purpose: KITTI has GPS/IMU and LiDAR on the same car but no CAN bus. To pair the CAN motion claim with them, the
ROAD vehicle's wheel-speed message is synthesised from the OXTS forward speed and yaw rate, encoded into payload bytes
with the ROAD DBC layout (0x6e0: four 14-bit Motorola signals), and decoded by can.domain.CanDomain.motion_estimates,
so the real frozen interface is exercised (held value at the end of each second, 0.01 km/h unit, published sigma).
Model (parameters from ROAD TRAIN ambient captures, results/WP6/s1_road_wheel.json, tools/WP6_S1_road_wheel.py):
  - message period 0.010 s (ROAD median 0.0100 s), timestamps jittered by U(-1, 1) ms (ROAD p99 period 13-15 ms);
  - wheel speed w_i = vf * (1 + e_drive) -/+ omega * TRACK / 2 (left / right), e_drive ~ N(0, 2%) per drive = tyre
    radius / scale error (same as the WP1 odometry model, gps/stream.py), TRACK = 1.6 m;
  - additive white noise N(0, 0.015 m/s) per wheel and message (ROAD: median short-term noise around a 0.5 s moving
    average 0.0149 m/s on moving segments), then quantised to the raw unit 0.01 km/h, clipped to 0..16383 (14 bit);
  - unsigned (|vf|): KITTI drives do not reverse; transport latency 0 (unknown for ROAD; estimated on comma2k19).
vf, omega: OXTS forward velocity and yaw rate at 10 Hz, linearly interpolated to the message times.
Inputs: OXTS dict of gps.stream.load_oxts; rng. Outputs: (t, ids, dlc, B) arrays of a capture; MotionEstimate list.
Limits: real wheel speeds also show slip, tyre-pressure scale drift and suspension effects that OXTS cannot provide.
"""
import numpy as np

from can import signals as S

WHEEL_ID = 0x6E0
UNIT_MPS = 0.01 / 3.6
PERIOD, JITTER = 0.010, 0.001
TRACK = 1.6
SCALE_SIGMA = 0.02
NOISE_MPS = 0.015
_SIGS = None


def _sigs():
    global _SIGS
    if _SIGS is None:
        _SIGS = S.parse_dbc()[WHEEL_ID]
    return _SIGS


def encode_wheels(raw):
    """raw: n x 4 integer wheel speeds (0..16383) -> n x 8 uint8 payloads in the ROAD DBC layout (inverse of Sig.decode)."""
    raw = np.asarray(raw, np.int64)
    w = np.zeros(len(raw), np.uint64)
    for j, s in enumerate(_sigs()):
        w |= (raw[:, j].astype(np.uint64) & np.uint64((1 << s.length) - 1)) << np.uint64(s.shift)
    B = np.zeros((len(raw), 8), np.uint8)
    for i in range(8):
        B[:, i] = ((w >> np.uint64(8 * (7 - i))) & np.uint64(0xFF)).astype(np.uint8)
    return B


def simulate_frames(ox, rng, scale=None, latency=0.0):
    """OXTS dict (t, vf, wz) -> (t, ids, dlc, B, truth) of a wheel-speed-only capture. `latency` delays the content
    (message at time t carries the speed of t - latency); used by the latency unit test."""
    t_ox = np.asarray(ox["t"], float)
    tm = np.arange(t_ox[0], t_ox[-1], PERIOD)
    tm = np.sort(tm + rng.uniform(-JITTER, JITTER, len(tm)))
    tm = tm[(tm >= t_ox[0]) & (tm <= t_ox[-1])]
    src = np.clip(tm - latency, t_ox[0], None)
    vf = np.abs(np.interp(src, t_ox, ox["vf"]))
    om = np.interp(src, t_ox, ox["wz"])
    e = rng.normal(0, SCALE_SIGMA) if scale is None else scale
    base = vf * (1 + e)
    half = om * TRACK / 2
    W = np.c_[base - half, base + half, base - half, base + half]      # FL, FR, RL, RR (order irrelevant: the mean is used)
    W = W + rng.normal(0, NOISE_MPS, W.shape)
    raw = np.clip(np.round(W / UNIT_MPS), 0, (1 << 14) - 1).astype(np.int64)
    B = encode_wheels(raw)
    n = len(tm)
    return tm, np.full(n, WHEEL_ID), np.full(n, 8), B, {"scale": float(e), "t": tm, "v_true": vf}


def can_motion_estimates(domain, frames):
    """MotionEstimate list from the frozen CanDomain for a simulated capture (frames = simulate_frames output)."""
    t, ids, dlc, B, _ = frames
    return domain.motion_estimates(t, ids, dlc, B)
