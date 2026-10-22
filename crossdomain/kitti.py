"""WP6 S1: KITTI motion-witness streams (gps claim, imu gyro, lidar odometry, simulated can wheel speed) per drive.

Purpose: build, for one KITTI drive, the MotionEstimate streams of every source from the FROZEN producers of WP1 / WP2
(gps.domain.gps_motion_estimates, gps.lidar_odom.motion_estimates, can.domain.CanDomain.motion_estimates) plus an IMU
yaw-rate stream from the gyro column of the WP1 stream (source "imu", instantaneous, speed unknown).
Inputs: one clean WP1 stream run (gps/stream.py columns, 1 Hz), the cached WP1 LiDAR odometry of the drive, the full-rate
OXTS of the drive (for the CAN simulation and native-rate latency), a CanDomain, a numpy Generator.
Outputs: dict source -> DataFrame (crossdomain.witness.COLS); native-rate signals for latency estimation.
"""
import numpy as np
import pandas as pd

from common.motion import MotionEstimate
from crossdomain import can_sim
from crossdomain.witness import to_frame
from gps import lidar_odom as LO
from gps.domain import gps_motion_estimates

IMU_GYRO_SIGMA = 0.005           # gps/stream.py GYRO_SIGMA (rad/s per sample)


def imu_motion_estimates(run):
    """Gyro yaw rate at every fix (source "imu", instantaneous sample; speed / displacement unknown, sigma = NaN speed)."""
    return [MotionEstimate(t=float(t), source="imu", speed=None, yaw_rate=float(w), displacement=None, sigma=float("nan"))
            for t, w in zip(run["t"].to_numpy(float), run["yaw_rate"].to_numpy(float))]


def lidar_estimates(run, drive, folder=None):
    tp, P, qual = LO.load_odometry(drive, folder)
    ok = LO.run_features(run, tp, P, qual, windows=(1,))["lid_ok"] > 0
    return LO.motion_estimates(run["t"].to_numpy(float), P, tp, quality_ok=ok)


def drive_sources(run, drive, ox, can_domain, rng, folder=None, scale=None):
    """All KITTI sources for one clean run of `drive` -> dict of frames (witness.COLS). scale: CAN tyre-scale error (None = draw
    N(0, 2%) per drive, the pre-registered model; revised design R2 passes vehicle scale + small per-drive term)."""
    out = {"gps": to_frame(gps_motion_estimates(run)), "imu": to_frame(imu_motion_estimates(run)),
           "lidar": to_frame(lidar_estimates(run, drive, folder))}
    frames = can_sim.simulate_frames(ox, rng, scale=scale)
    out["can"] = to_frame(can_sim.can_motion_estimates(can_domain, frames))
    return out, frames[4]


def forward_speed(grid_frame):
    """Revised design R4: speed of a displacement source = forward displacement over the last second (signed, unbiased at
    standstill, unlike the norm of a noisy displacement)."""
    g = grid_frame.copy()
    g["speed"] = g["dx"]
    return g


def native_signals(drive, ox, folder=None):
    """Native-rate signals for the latency estimate: OXTS forward speed / yaw rate (10 Hz) and LiDAR scan-to-scan
    speed / yaw rate (10 Hz, stamped at the middle of each scan pair)."""
    z = np.load(LO.cache_file(drive, folder))
    tp, rel = z["t"], z["rel"]
    dt = np.diff(tp)
    ok = dt > 0
    tl = (0.5 * (tp[1:] + tp[:-1]))[ok]                     # a scan-pair motion is the mean over the pair: stamp at its middle
    return {"oxts_speed": (np.asarray(ox["t"]), np.abs(np.asarray(ox["vf"]))), "oxts_yaw": (np.asarray(ox["t"]), np.asarray(ox["wz"])),
            "lidar_speed": (tl, np.hypot(rel[ok, 0], rel[ok, 1]) / dt[ok]), "lidar_yaw": (tl, rel[ok, 2] / dt[ok])}
