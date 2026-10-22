"""WP6 cross-domain layer. S1 = motion witnesses (no attack verdict).

API for S2 ("which domain lies"), see reports/WP6_S1.md section "API":

Producers (frozen, other WPs; MotionEstimate = common.motion):
  gps.domain.gps_motion_estimates(run_df)                    "gps"   CLAIM  speed, yaw (compass), displacement, sigma 0.45
  gps.lidar_odom.motion_estimates(t_fix, P, tp, ok)          "lidar" WITNESS speed, yaw, displacement, sigma(v)
  can.domain.CanDomain.motion_estimates(t, ids, dlc, B)      "can"   CLAIM  speed (held value), sigma max(0.3, 3% v)
  crossdomain.kitti.imu_motion_estimates(run_df)             "imu"   WITNESS yaw rate (gyro)
  crossdomain.v2x_self.bsm_motion_estimates(track_df)        "v2x"   CLAIM  (other vehicles only in our data)
  crossdomain.comma.frames(route)                            comma2k19 "can" / "wheel" / "gnss" / "imu" native frames
  crossdomain.can_sim.simulate_frames(oxts, rng)             KITTI SIMULATED 0x6e0 frames for the frozen CanDomain

Witness layer (crossdomain.witness):
  f = to_frame(estimates)                                    DataFrame t, source, speed, yaw_rate, dx, dy, sigma
  g = to_grid(f, grid, kind=None, lag=0.0)                   1 Hz MEAN over (t-1, t] (kind "mean" for gps/lidar,
                                                             "inst" for can/imu/gnss/v2x: cumulative-trapezoid mean)
  tab = pair_table(ga, gb, "gps", "lidar", "speed")          r = a - b, s = hypot(sigma_a, sigma_b), z = r / s, v
  m = SigmaModel.from_dict(results/WP6/s1_sigma_models.json[...]["models"]["gps-lidar speed"])
  z = m.z(tab.r, tab.v)                                      recalibrated z (train-fitted; "kitti_R"/"comma_R" = R1 linear bias)
  lag = estimate_lag([lag_covariance(ta, a, tb, b) ...])     latency (b lags a by lag s), CI by group bootstrap
  honesty(z)                                                 mean, std, p99 |z|, honest flag (S1 acceptance bounds)
S2 contract: for every grid second and pair, |z| large = the pair disagrees; the domain shared by the disagreeing pairs
(and absent from the agreeing ones) is the suspect. Pairs available: KITTI gps-lidar (speed, yaw, lateral), gps-can, lidar-can
(speed), gps-imu, imu-lidar (yaw); comma gnss-can, gnss-wheel (speed), gnss-imu (yaw).
"""
