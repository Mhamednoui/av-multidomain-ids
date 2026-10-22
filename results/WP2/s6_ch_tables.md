# WP2 S6: Car-Hacking test blocks (scored once)
variants {'t': [('all', 1)], 'p': [('all', 1)]}; window thresholds {'t': -0.8161622285842894, 'p': -10.581843376159666}

### window level
windows: {'clean': 300, 'attack': 976, 'other_normal': 403}

| config | clean FA | other-normal FA | files detected | DoS | Fuzzy | RPM | Gear |
|---|---|---|---|---|---|---|---|
| L1 | 0.7% | 43.9% | 4/4 | 100.0% | 100.0% | 99.5% | 99.5% |
| L4t | 2.3% | 3.2% | 4/4 | 100.0% | 100.0% | 100.0% | 100.0% |
| L4p | 4.0% | 18.6% | 4/4 | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t | 3.0% | 45.7% | 4/4 | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 4.7% | 49.1% | 4/4 | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 7.0% | 50.1% | 4/4 | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall DoS 100.0%, Fuzzy 100.0%, RPM 100.0%, Gear 100.0%; FA clean frames 0.9%
- p: recall DoS 100.0%, Fuzzy 100.0%, RPM 100.0%, Gear 100.0%; FA clean frames 1.1%