# WP2 CAN brief (state at 2026-10-21, after S2)

## State
- S0 data inventory, S1 adapters/splits/frames: APPROVED. S2 (L1 rules): done, verdict NOT MET (ROAD false alerts 3.4% > 1%).
- Next (see notes/WP2_can.md): L2 timing/statistical layer, payload/signal layer, combination + bench.

## Binding decisions
- Domain "can", layers L1.. ; Layer API from common/layer.py; evaluation only through common/evaluate.py.
- Unit 1 = frame (causal, recorded order, dt_clipped only; never use the sign of dt). Unit 2 = 1 s window by running-max t;
  window label = >= 1 injected frame.
- Clean = attack-free traffic only (ROAD ambient + lead of attack captures minus 1 s; Car-Hacking blocks without injection;
  D11 same lead rule). Profiles/thresholds never see attack frames; the tolerance variant is the only chosen hyper-parameter.
- Splits: v2 ROAD split, v2 block split for Car-Hacking, D11 splits in results/WP2/splits_d11.json (4 sets, 4 test subsets).
- D11 regime A zero-shot, regime B on-vehicle (first 30 s profile, next 30 s thresholds, score t >= 60 s).
- Test labels never choose anything. ROAD run 1 is the verdict; run 2 (IQR periodic test) is "revised design".

## Pitfalls
- Specification rules cannot see same-ID same-period masquerade; do not claim the masquerade target for L1.
- ID/DLC allow-lists are vehicle-specific: zero-shot to another vehicle gives ~100% FA. Needs on-vehicle calibration.
- Noisy-or of 5 rules at 1% each gives 3-4% FA; ROAD test ambient (benign_anomaly, extended_short) shifts vs val.
- D11 files with no clean frame exist (ProfileBuilder guards empty input). Car-Hacking test is interleaved blocks:
  delay fields are not onset delays; "other_normal" windows there border attacks, high alarm rate is expected.
- Do NOT cache per-frame strings: a 39 GB blow-up filled the disk. Cache = int8 attack codes
  (../data_extra/WP2_S2_cache, 3.4 GB; rebuild: tools/WP2_S2_cache.py road|carhacking|d11, ~10 min).
- Run python with PYTHONDONTWRITEBYTECODE=1 in the tf conda env. Avoid apostrophes in long bash heredocs (parse errors).

## File map
- can/: frames.py, adapters.py, splits.py (S1); l1.py (rules, profile, features); l1_exp.py (experiment machinery).
- tools/: WP2_S2_cache.py, WP2_S2_run.py (road|carhacking|d11 set_0N, resumable).
- tests/can/: test_frames_adapters.py, test_l1.py.
- results/WP2/: s1_*.json, splits_*.json, s2_road.json (run 2), s2_run1_frozen/ (verdict), s2_run2_iqr/, s2_carhacking.json,
  s2_d11_set_0N.json, s2_d11_tables.md, s2_harness/, s2_profiles/, logs/.
- reports/WP2_S1.md, WP2_S2.md; notes/WP2_can.md (all decisions, written before results).
