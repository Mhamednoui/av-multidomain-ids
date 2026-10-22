# WP3 S2b: old (S2, add keeps the real return) vs fixed (single return), VALIDATION only

v2 thresholds (val clean 1 % / 2 %): 0.976 / 0.969. Detection in %, onset and sustained pooled for box cloud, per timing for ray-cast.

## Box cloud

| mode | n old/fixed | v2 1% old | v2 1% fixed | L1 union old | L1 union fixed | L1 single_return old | fixed |
|---|---|---|---|---|---|---|---|
| onset | 272/272 | 65.1 | 25.7 | 45.6 | 21.0 | 40.1 | 5.9 |
| sustained | 277/277 | 47.7 | 13.7 | 49.1 | 20.9 | 43.7 | 7.6 |

## Ray-cast phantoms (variant cal = calibrated generator, old = S1 generator)

| variant | mode | band | timing | n | med pts old | med pts fixed | v2 1% old | fixed | v2 2% old | fixed | L1 union old | fixed | L1 single_return old | fixed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cal | add | far | onset | 275 | 121 | 121 | 21.1 | 1.1 | 23.6 | 1.8 | 60.0 | 1.5 | 58.9 | 0.0 |
| cal | add | far | sustained | 275 | 121 | 121 | 18.2 | 1.1 | 21.1 | 1.8 | 60.0 | 1.5 | 58.9 | 0.0 |
| cal | add | near | onset | 275 | 1537 | 1537 | 86.2 | 8.7 | 88.4 | 9.5 | 1.1 | 1.1 | 0.0 | 0.0 |
| cal | add | near | sustained | 275 | 1537 | 1537 | 60.7 | 5.5 | 69.5 | 6.5 | 1.1 | 1.1 | 0.0 | 0.0 |
| cal | budget | far | onset | 275 | 97 | 97 | 1.1 | 1.1 | 1.8 | 1.8 | 1.5 | 1.5 | 0.0 | 0.0 |
| cal | budget | far | sustained | 275 | 97 | 97 | 1.1 | 1.1 | 1.8 | 1.8 | 1.5 | 1.5 | 0.0 | 0.0 |
| cal | budget | near | onset | 275 | 237 | 237 | 1.5 | 1.5 | 2.9 | 2.9 | 1.1 | 1.1 | 0.0 | 0.0 |
| cal | budget | near | sustained | 275 | 237 | 237 | 1.5 | 1.5 | 2.2 | 2.2 | 1.1 | 1.1 | 0.0 | 0.0 |
| cal | budget_add | far | onset | 275 | 98 | 98 | 13.1 | 1.1 | 16.0 | 1.8 | 58.9 | 1.5 | 57.8 | 0.0 |
| cal | budget_add | far | sustained | 275 | 98 | 98 | 9.1 | 1.1 | 12.0 | 1.8 | 58.9 | 1.5 | 57.8 | 0.0 |
| cal | budget_add | near | onset | 275 | 236 | 236 | 15.3 | 1.5 | 18.2 | 2.5 | 1.1 | 1.1 | 0.0 | 0.0 |
| cal | budget_add | near | sustained | 275 | 236 | 236 | 8.0 | 1.5 | 10.5 | 1.8 | 1.1 | 1.1 | 0.0 | 0.0 |
| cal | replace | far | onset | 275 | 121 | 121 | 1.1 | 1.1 | 1.8 | 1.8 | 1.8 | 1.8 | 0.0 | 0.0 |
| cal | replace | far | sustained | 275 | 121 | 121 | 1.1 | 1.1 | 1.8 | 1.8 | 1.8 | 1.8 | 0.0 | 0.0 |
| cal | replace | near | onset | 275 | 1407 | 1407 | 6.9 | 6.9 | 10.5 | 10.5 | 1.1 | 1.1 | 0.0 | 0.0 |
| cal | replace | near | sustained | 275 | 1407 | 1407 | 4.4 | 4.4 | 6.5 | 6.5 | 1.1 | 1.1 | 0.0 | 0.0 |
| old | add | far | onset | 275 | 202 | 202 | 33.8 | 18.2 | 35.6 | 20.7 | 57.8 | 25.8 | 56.0 | 22.2 |
| old | add | far | sustained | 275 | 202 | 202 | 28.0 | 13.5 | 31.3 | 16.4 | 57.8 | 25.8 | 56.0 | 22.2 |
| old | add | near | onset | 275 | 2644 | 2644 | 93.5 | 86.2 | 94.2 | 89.5 | 1.1 | 1.1 | 0.0 | 0.0 |
| old | add | near | sustained | 275 | 2644 | 2644 | 73.1 | 59.3 | 80.0 | 68.4 | 1.1 | 1.1 | 0.0 | 0.0 |
| old | budget | far | onset | 275 | 142 | 142 | 1.1 | 1.1 | 1.8 | 1.8 | 5.1 | 5.1 | 0.0 | 0.0 |
| old | budget | far | sustained | 275 | 142 | 142 | 1.1 | 1.1 | 1.8 | 1.8 | 5.1 | 5.1 | 0.0 | 0.0 |
| old | budget | near | onset | 275 | 239 | 239 | 1.1 | 1.1 | 1.8 | 1.8 | 1.1 | 1.1 | 0.0 | 0.0 |
| old | budget | near | sustained | 275 | 239 | 239 | 1.1 | 1.1 | 1.8 | 1.8 | 1.1 | 1.1 | 0.0 | 0.0 |
| old | budget_add | far | onset | 275 | 142 | 142 | 17.1 | 2.2 | 20.7 | 3.6 | 54.5 | 22.5 | 53.5 | 20.4 |
| old | budget_add | far | sustained | 275 | 142 | 142 | 9.5 | 1.8 | 13.8 | 2.9 | 54.5 | 22.5 | 53.5 | 20.4 |
| old | budget_add | near | onset | 275 | 239 | 239 | 9.5 | 2.2 | 12.7 | 4.0 | 1.1 | 1.1 | 0.0 | 0.0 |
| old | budget_add | near | sustained | 275 | 239 | 239 | 6.2 | 1.8 | 7.3 | 2.5 | 1.1 | 1.1 | 0.0 | 0.0 |
| old | replace | far | onset | 275 | 202 | 202 | 1.1 | 1.1 | 1.8 | 1.8 | 9.8 | 10.2 | 0.0 | 0.0 |
| old | replace | far | sustained | 275 | 202 | 202 | 1.1 | 1.1 | 1.8 | 1.8 | 9.8 | 10.2 | 0.0 | 0.0 |
| old | replace | near | onset | 275 | 2644 | 2644 | 1.1 | 0.7 | 1.8 | 1.5 | 1.8 | 1.8 | 0.0 | 0.0 |
| old | replace | near | sustained | 275 | 2644 | 2644 | 1.1 | 0.7 | 1.8 | 1.5 | 1.8 | 1.8 | 0.0 | 0.0 |

Clean val FA check (v2 1 %, L1 union): {'clean': {'n': 549, 'median_points': None, 'v2_1pct': 0.01092896174863388, 'v2_2pct': 0.020036429872495445, 'L1_union': 0.009107468123861567, 'L1_ring_total': 0.009107468123861567, 'L1_ring_sector': 0.0036429872495446266, 'L1_single_return': 0.0}}