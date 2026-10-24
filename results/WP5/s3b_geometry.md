# S3b geometry diagnosis (train + validation recordings; results/WP5/s3b_geometry.json)

## Mobile: 17732 messages with ego pose, 249 senders, 192 recordings
distance quantiles (m): q0.5=185, q0.9=3523, q0.99=5021, q0.999=6516, q1.0=6644
share beyond 300 m / 1 km / 2 km / 5 km: 37.0% / 30.1% / 27.8% / 1.1%
implied ego speed p50 / p99 / max: 21.3 / 43.2 / 114.3 m/s

| distance bin | messages | recordings | senders | age_s p50 | age_s p99 | E2 violations | E2prime (generation-time dt, post-hoc) | haversine/local p1..p99 |
|---|---|---|---|---|---|---|---|---|
| <100 m | 4874 | 145 | 182 | 0.022 | 0.97 | 0.59% of 4778 | 0.44% of 4770 | 0.9902..1.0568 |
| 100-300 m | 6305 | 161 | 200 | 0.023 | 0.99 | 0.76% of 6038 | 0.60% of 6028 | 0.9900..1.0478 |
| 0.3-1 km | 1217 | 94 | 109 | 0.019 | 0.12 | 1.14% of 1056 | 0.95% of 1055 | 0.9896..1.0342 |
| 1-2 km | 414 | 7 | 7 | 0.028 | 0.07 | 0.25% of 407 | 0.00% of 407 | 0.9986..1.0423 |
| 2-5 km | 4731 | 3 | 13 | 0.028 | 0.29 | 0.02% of 4633 | 0.04% of 4629 | 0.9993..1.0454 |
| >5 km | 191 | 3 | 3 | 0.016 | 0.20 | 0.00% of 176 | 0.00% of 176 | 1.0078..1.0264 |

messages beyond 2 km: 4922 from 4 recordings / 14 senders; largest single-recording share 37%; by location: {'Mobile/Highway': 3598, 'Mobile/Rural': 1324}

| location | messages | recordings | d p50 | d p99 | d max | ego pose source |
|---|---|---|---|---|---|---|
| Mobile/Aachen | 1779 | 14 | 166 | 388 | 992 | cohda, oxts |
| Mobile/Cologne | 936 | 13 | 188 | 781 | 905 | cohda, oxts |
| Mobile/Dusseldorf | 724 | 10 | 113 | 409 | 1437 | cohda |
| Mobile/Highway | 12412 | 150 | 182 | 4942 | 6644 | cohda, oxts |
| Mobile/Rural | 1881 | 5 | 3526 | 5156 | 5158 | cohda |

## Stationary: 138889 messages with ego pose, 1172 senders, 909 recordings
distance quantiles (m): q0.5=567, q0.9=3186, q0.99=4233, q0.999=5253, q1.0=8053
share beyond 300 m / 1 km / 2 km / 5 km: 61.1% / 36.4% / 27.7% / 0.4%
implied ego speed p50 / p99 / max: 0.0 / 0.0 / 0.0 m/s

| distance bin | messages | recordings | senders | age_s p50 | age_s p99 | E2 violations | E2prime (generation-time dt, post-hoc) | haversine/local p1..p99 |
|---|---|---|---|---|---|---|---|---|
| <100 m | 35551 | 643 | 767 | 0.022 | 0.69 | 0.63% of 33656 | 0.23% of 33685 | 0.9934..0.9991 |
| 100-300 m | 18413 | 476 | 593 | 0.031 | 1.48 | 2.77% of 15822 | 0.31% of 15885 | 0.9934..0.9990 |
| 0.3-1 km | 34366 | 201 | 314 | 0.025 | 1.68 | 3.50% of 30026 | 0.22% of 30299 | 0.9934..0.9985 |
| 1-2 km | 12069 | 110 | 190 | 0.026 | 1.74 | 3.72% of 10257 | 0.14% of 10367 | 0.9940..0.9967 |
| 2-5 km | 37936 | 137 | 229 | 0.025 | 1.78 | 1.79% of 32675 | 0.00% of 32943 | 0.9969..0.9989 |
| >5 km | 554 | 58 | 68 | 0.015 | 1.33 | 3.05% of 394 | 0.00% of 396 | 0.9973..0.9989 |

messages beyond 2 km: 38490 from 158 recordings / 263 senders; largest single-recording share 6%; by location: {'Stationary/A44-Jackerath': 38490}

| location | messages | recordings | d p50 | d p99 | d max | ego pose source |
|---|---|---|---|---|---|---|
| Stationary/A44-Jackerath | 101668 | 241 | 991 | 4299 | 8053 | cohda_static |
| Stationary/Aachen-Heinrichsallee | 1998 | 118 | 25 | 67 | 111 | cohda_static |
| Stationary/Aachen-Monheimsallee | 3208 | 66 | 78 | 158 | 173 | cohda_static |
| Stationary/Aachen-Ponttor | 14176 | 242 | 44 | 142 | 236 | cohda_static |
| Stationary/Aachen-Theaterstrasse | 17839 | 242 | 71 | 270 | 327 | cohda_static |

## E4 link budget (free space, upper bound of the reachable range)
```
{
 "assumptions": {
  "eirp_dbm": 33.0,
  "rx_antenna_gain_dbi_fixed_unit": 8.0,
  "rx_antenna_gain_dbi_vehicle": 3.0,
  "sensitivity_dbm_3mbps_10mhz": -95.0,
  "source": "ETSI EN 302 663 (ITS-G5 G5A EIRP limit 33 dBm); IEEE 802.11p receiver minimum sensitivity -85 dBm (typical chips -95 to -98 dBm at 3 Mbit/s)"
 },
 "Mobile": {
  "d_max_m": 6643.804457948067,
  "free_space_path_loss_db": 124.3153770669976,
  "received_power_dbm_free_space": -88.3153770669976,
  "margin_to_minus95_dbm_db": 6.684622933002402,
  "margin_to_minus85_dbm_db": -3.3153770669975984
 },
 "Stationary": {
  "d_max_m": 8052.721157639936,
  "free_space_path_loss_db": 125.98589345275195,
  "received_power_dbm_free_space": -84.98589345275195,
  "margin_to_minus95_dbm_db": 10.014106547248048,
  "margin_to_minus85_dbm_db": 0.014106547248047718
 }
}
```

E1 haversine / local-frame distance: {'n': 135495, 'p1': 0.9934300322990953, 'median': 0.997593726495615, 'p99': 1.038511965473315, 'min': 0.9891196408087566, 'max': 1.0621212466309582}; beyond 2 km: {'n': 43412, 'min': 0.9939454588502616, 'max': 1.0455433314643903}