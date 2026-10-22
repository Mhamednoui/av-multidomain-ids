"""WP3 S3 ego-motion from KITTI OXTS: planar pose of every scan and the transform of points between consecutive scans.

Purpose: compare object positions in consecutive scans (association, tracking) after removing the car's own motion.
Inputs: OXTS files of a drive (lat, lon, yaw per frame; one OXTS record per velodyne scan in the `sync` data).
Outputs: poses (x east, y north, yaw) in a local Mercator frame; 2D rigid transforms frame t -> frame t+k.
Model: planar (roll, pitch, height ignored: error < 5 cm over 0.1 s at city speed); IMU -> velodyne offset from the KITTI
calibration of 2011_09_26 (calib_imu_to_velo: R = I, T = (-0.8087, 0.3196, -0.7997) m, so p_imu = p_velo - T).
Copy of the OXTS reading logic of WP1 (gps/stream.py) and of KITTI devkit Mercator projection (Geiger et al. 2013).
"""
import numpy as np

from lidar.data import drive_dir

ER = 6378137.0
T_IMU_TO_VELO = np.array([-0.8087, 0.3196])


def oxts_dir(d):
    return drive_dir(d).parent.parent / "oxts" / "data"


def poses(d):
    """N x 3 array (x east m, y north m, yaw rad) for the frames of drive d."""
    rec = np.array([np.loadtxt(f) for f in sorted(oxts_dir(d).glob("*.txt"))])
    lat, lon, yaw = rec[:, 0], rec[:, 1], rec[:, 5]
    scale = np.cos(np.radians(lat[0]))
    x = scale * np.radians(lon) * ER
    y = scale * ER * np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))
    return np.c_[x - x[0], y - y[0], np.unwrap(yaw)]


def to_world(xy, pose):
    """Velodyne-frame planar points -> local world frame."""
    p = xy - T_IMU_TO_VELO
    c, s = np.cos(pose[2]), np.sin(pose[2])
    return np.c_[c * p[:, 0] - s * p[:, 1], s * p[:, 0] + c * p[:, 1]] + pose[:2]


def from_world(xy, pose):
    c, s = np.cos(pose[2]), np.sin(pose[2])
    q = xy - pose[:2]
    p = np.c_[c * q[:, 0] + s * q[:, 1], -s * q[:, 0] + c * q[:, 1]]
    return p + T_IMU_TO_VELO


def between(xy, pose_a, pose_b):
    """Points of the velodyne frame at pose_a expressed in the velodyne frame at pose_b (static world assumed)."""
    return from_world(to_world(xy, pose_a), pose_b)
