# WP2 S6: D11 test subsets (scored once)

## set_01  variants {'t': ['all', 1], 'p': ['all', 3]}  shuffle pass: can.l4_timing False (0.311/0.835), can.l4_payload False (0.388/0.821)
### set_01 test_01 ['Impala'] regime A
windows: {'clean': 838, 'attack': 101, 'other_normal': 2546}

| config | clean FA | other-normal FA | files detected | DoS | force-neutral | rpm | standstill |
|---|---|---|---|---|---|---|---|
| L1 | 3.5% | 3.7% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 0.4% | 0.2% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L4p | 0.4% | 0.3% | 8/8 | 97.9% | 100.0% | 100.0% | 100.0% |
| L1+L4t | 3.7% | 3.8% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 3.8% | 3.7% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 3.9% | 3.8% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall DoS 100.0%, force-neutral 100.0%, rpm 99.9%, standstill 98.5%; FA clean frames 0.6%
- p: recall DoS 100.0%, force-neutral 100.0%, rpm 99.9%, standstill 99.9%; FA clean frames 0.4%

### set_01 test_01 ['Impala'] regime B
windows: {'clean': 838, 'attack': 101, 'other_normal': 2546}

| config | clean FA | other-normal FA | files detected | DoS | force-neutral | rpm | standstill |
|---|---|---|---|---|---|---|---|
| L1 | 3.5% | 3.6% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 2.0% | 2.0% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L4p | 2.0% | 2.3% | 8/8 | 97.9% | 100.0% | 100.0% | 100.0% |
| L1+L4t | 4.9% | 5.3% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 5.3% | 5.4% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 6.4% | 7.0% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall DoS 100.0%, force-neutral 100.0%, rpm 99.9%, standstill 99.2%; FA clean frames 1.1%
- p: recall DoS 100.0%, force-neutral 100.0%, rpm 99.9%, standstill 100.0%; FA clean frames 3.7%

### set_01 test_02 ['Silverado'] regime A
windows: {'clean': 887, 'attack': 220, 'other_normal': 919}

| config | clean FA | other-normal FA | files detected | DoS | force-neutral | rpm | standstill |
|---|---|---|---|---|---|---|---|
| L1 | 100.0% | 100.0% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 100.0% | 100.0% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L4p | 100.0% | 100.0% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t | 100.0% | 100.0% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 100.0% | 100.0% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 100.0% | 100.0% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall DoS 100.0%, force-neutral 92.0%, rpm 84.9%, standstill 82.6%; FA clean frames 59.3%
- p: recall DoS 100.0%, force-neutral 100.0%, rpm 84.9%, standstill 95.7%; FA clean frames 61.1%

### set_01 test_02 ['Silverado'] regime B
windows: {'clean': 887, 'attack': 220, 'other_normal': 919}

| config | clean FA | other-normal FA | files detected | DoS | force-neutral | rpm | standstill |
|---|---|---|---|---|---|---|---|
| L1 | 3.0% | 3.6% | 8/8 | 100.0% | 100.0% | 85.0% | 100.0% |
| L4t | 2.3% | 5.1% | 8/8 | 100.0% | 100.0% | 92.5% | 100.0% |
| L4p | 25.0% | 18.1% | 8/8 | 100.0% | 100.0% | 47.5% | 100.0% |
| L1+L4t | 5.0% | 8.2% | 8/8 | 100.0% | 100.0% | 97.5% | 100.0% |
| L1+L4p | 27.6% | 20.3% | 8/8 | 100.0% | 100.0% | 87.5% | 100.0% |
| L1+L4t+L4p | 28.9% | 23.3% | 8/8 | 100.0% | 100.0% | 97.5% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall DoS 100.0%, force-neutral 81.8%, rpm 84.9%, standstill 82.6%; FA clean frames 1.0%
- p: recall DoS 100.0%, force-neutral 81.8%, rpm 61.2%, standstill 81.5%; FA clean frames 1.4%

### set_01 test_03 ['Impala'] regime A
windows: {'clean': 981, 'attack': 750, 'other_normal': 3751}

| config | clean FA | other-normal FA | files detected | double | interval | speed | systematic | triple | fuzzing |
|---|---|---|---|---|---|---|---|---|---|
| L1 | 3.4% | 4.9% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 1.1% | 0.2% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4p | 1.6% | 0.2% | 11/12 | 100.0% | 99.8% | 100.0% | 54.5% | 100.0% | 70.5% |
| L1+L4t | 4.4% | 5.0% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 4.8% | 4.9% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 5.4% | 5.0% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall double 97.9%, fuzzing 99.6%, interval 100.0%, speed 100.0%, systematic 99.7%, triple 99.5%; FA clean frames 0.9%
- p: recall double 97.8%, fuzzing 99.6%, interval 100.0%, speed 100.0%, systematic 99.7%, triple 99.5%; FA clean frames 0.5%

### set_01 test_03 ['Impala'] regime B
windows: {'clean': 981, 'attack': 750, 'other_normal': 3751}

| config | clean FA | other-normal FA | files detected | double | interval | speed | systematic | triple | fuzzing |
|---|---|---|---|---|---|---|---|---|---|
| L1 | 2.7% | 3.3% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 5.0% | 4.3% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4p | 3.1% | 0.9% | 11/12 | 100.0% | 99.8% | 100.0% | 54.5% | 100.0% | 70.5% |
| L1+L4t | 7.0% | 7.2% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 5.4% | 4.1% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 9.0% | 7.8% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall double 98.2%, fuzzing 99.6%, interval 100.0%, speed 100.0%, systematic 99.7%, triple 99.4%; FA clean frames 1.3%
- p: recall double 97.8%, fuzzing 99.6%, interval 100.0%, speed 100.0%, systematic 99.7%, triple 99.4%; FA clean frames 3.7%

### set_01 test_04 ['Traverse'] regime A
windows: {'clean': 1936, 'attack': 154, 'other_normal': 4004}

| config | clean FA | other-normal FA | files detected | double | interval | speed | systematic | triple | fuzzing |
|---|---|---|---|---|---|---|---|---|---|
| L1 | 100.0% | 100.0% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 99.9% | 100.0% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4p | 99.9% | 100.0% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t | 100.0% | 100.0% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 100.0% | 100.0% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 100.0% | 100.0% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall double 99.9%, fuzzing 99.7%, interval 100.0%, speed 99.8%, systematic 99.8%, triple 99.9%; FA clean frames 40.4%
- p: recall double 99.6%, fuzzing 99.6%, interval 100.0%, speed 99.8%, systematic 99.8%, triple 99.5%; FA clean frames 41.5%

### set_01 test_04 ['Traverse'] regime B
windows: {'clean': 1936, 'attack': 154, 'other_normal': 4004}

| config | clean FA | other-normal FA | files detected | double | interval | speed | systematic | triple | fuzzing |
|---|---|---|---|---|---|---|---|---|---|
| L1 | 2.3% | 2.7% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 5.9% | 5.3% | 12/12 | 100.0% | 100.0% | 64.7% | 90.0% | 100.0% | 100.0% |
| L4p | 2.3% | 2.7% | 12/12 | 100.0% | 100.0% | 76.5% | 17.1% | 100.0% | 100.0% |
| L1+L4t | 8.1% | 7.3% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 4.5% | 5.0% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 9.6% | 9.2% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall double 100.0%, fuzzing 99.7%, interval 100.0%, speed 99.8%, systematic 99.5%, triple 96.0%; FA clean frames 1.4%
- p: recall double 93.3%, fuzzing 99.6%, interval 100.0%, speed 99.8%, systematic 99.5%, triple 93.3%; FA clean frames 1.9%

## set_02  variants {'t': ['all', 1], 'p': ['all', 2]}  shuffle pass: can.l4_timing False (0.416/0.786), can.l4_payload False (0.364/0.655)
### set_02 test_01 ['Traverse'] regime A
windows: {'clean': 1936, 'attack': 154, 'other_normal': 4004}

| config | clean FA | other-normal FA | files detected | double | fuzzing | interval | speed | systematic | triple |
|---|---|---|---|---|---|---|---|---|---|
| L1 | 1.0% | 1.9% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 0.4% | 0.7% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4p | 0.5% | 0.6% | 10/12 | 100.0% | 100.0% | 21.4% | 17.6% | 15.7% | 100.0% |
| L1+L4t | 1.2% | 2.0% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 1.3% | 2.1% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 1.5% | 2.2% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall double 100.0%, fuzzing 100.0%, interval 100.0%, speed 100.0%, systematic 100.0%, triple 100.0%; FA clean frames 0.7%
- p: recall double 100.0%, fuzzing 100.0%, interval 100.0%, speed 100.0%, systematic 100.0%, triple 100.0%; FA clean frames 1.0%

### set_02 test_01 ['Traverse'] regime B
windows: {'clean': 1936, 'attack': 154, 'other_normal': 4004}

| config | clean FA | other-normal FA | files detected | double | fuzzing | interval | speed | systematic | triple |
|---|---|---|---|---|---|---|---|---|---|
| L1 | 1.5% | 2.7% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 1.9% | 2.2% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4p | 5.6% | 5.1% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 22.9% | 100.0% |
| L1+L4t | 3.2% | 4.2% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 6.7% | 6.9% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 7.4% | 7.8% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall double 100.0%, fuzzing 100.0%, interval 100.0%, speed 100.0%, systematic 100.0%, triple 100.0%; FA clean frames 1.1%
- p: recall double 100.0%, fuzzing 100.0%, interval 100.0%, speed 100.0%, systematic 100.0%, triple 100.0%; FA clean frames 0.9%

### set_02 test_02 ['Subaru'] regime A
windows: {'clean': 1035, 'attack': 163, 'other_normal': 3331}

| config | clean FA | other-normal FA | files detected | double | fuzzing | interval | speed | systematic | triple |
|---|---|---|---|---|---|---|---|---|---|
| L1 | 100.0% | 100.0% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 100.0% | 100.0% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4p | 100.0% | 100.0% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t | 100.0% | 100.0% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 100.0% | 100.0% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 100.0% | 100.0% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall double 100.0%, fuzzing 100.0%, interval 100.0%, speed 100.0%, systematic 100.0%, triple 100.0%; FA clean frames 99.4%
- p: recall double 100.0%, fuzzing 100.0%, interval 100.0%, speed 100.0%, systematic 100.0%, triple 100.0%; FA clean frames 100.0%

### set_02 test_02 ['Subaru'] regime B
windows: {'clean': 1035, 'attack': 163, 'other_normal': 3331}

| config | clean FA | other-normal FA | files detected | double | fuzzing | interval | speed | systematic | triple |
|---|---|---|---|---|---|---|---|---|---|
| L1 | 6.9% | 3.1% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 1.0% | 0.9% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4p | 100.0% | 99.4% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t | 7.2% | 3.6% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 100.0% | 99.4% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 100.0% | 99.4% | 12/12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall double 89.8%, fuzzing 100.0%, interval 100.0%, speed 100.0%, systematic 100.0%, triple 89.8%; FA clean frames 1.0%
- p: recall double 24.1%, fuzzing 99.7%, interval 70.5%, speed 98.4%, systematic 100.0%, triple 21.9%; FA clean frames 1.2%

### set_02 test_03 ['Traverse'] regime A
windows: {'clean': 1957, 'attack': 109, 'other_normal': 3549}

| config | clean FA | other-normal FA | files detected | DoS | force-neutral | rpm | standstill |
|---|---|---|---|---|---|---|---|
| L1 | 2.2% | 1.2% | 8/8 | 100.0% | 76.5% | 100.0% | 100.0% |
| L4t | 1.0% | 0.4% | 8/8 | 100.0% | 85.3% | 88.9% | 94.7% |
| L4p | 0.5% | 0.4% | 8/8 | 79.3% | 44.1% | 37.0% | 15.8% |
| L1+L4t | 2.4% | 1.3% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 2.2% | 1.4% | 8/8 | 100.0% | 97.1% | 100.0% | 100.0% |
| L1+L4t+L4p | 2.4% | 1.5% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: True, L1+L4p: True, L1+L4t+L4p: True

frame level @1% (threshold from validation clean frames) 
- t: recall DoS 100.0%, force-neutral 94.0%, rpm 96.7%, standstill 100.0%; FA clean frames 0.6%
- p: recall DoS 100.0%, force-neutral 98.0%, rpm 93.3%, standstill 100.0%; FA clean frames 0.9%

### set_02 test_03 ['Traverse'] regime B
windows: {'clean': 1957, 'attack': 109, 'other_normal': 3549}

| config | clean FA | other-normal FA | files detected | DoS | force-neutral | rpm | standstill |
|---|---|---|---|---|---|---|---|
| L1 | 3.8% | 2.8% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 1.9% | 1.5% | 8/8 | 100.0% | 97.1% | 96.3% | 100.0% |
| L4p | 1.3% | 1.0% | 8/8 | 100.0% | 47.1% | 37.0% | 31.6% |
| L1+L4t | 4.7% | 3.7% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 4.1% | 3.3% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 5.0% | 4.2% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall DoS 100.0%, force-neutral 92.0%, rpm 96.7%, standstill 100.0%; FA clean frames 0.8%
- p: recall DoS 100.0%, force-neutral 98.0%, rpm 93.3%, standstill 100.0%; FA clean frames 0.8%

### set_02 test_04 ['Subaru'] regime A
windows: {'clean': 918, 'attack': 60, 'other_normal': 1857}

| config | clean FA | other-normal FA | files detected | DoS | force-neutral | rpm | standstill |
|---|---|---|---|---|---|---|---|
| L1 | 100.0% | 100.0% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 100.0% | 100.0% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L4p | 100.0% | 100.0% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t | 100.0% | 100.0% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 100.0% | 100.0% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 100.0% | 100.0% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall DoS 100.0%, force-neutral 100.0%, rpm 100.0%, standstill 100.0%; FA clean frames 99.4%
- p: recall DoS 100.0%, force-neutral 100.0%, rpm 100.0%, standstill 100.0%; FA clean frames 100.0%

### set_02 test_04 ['Subaru'] regime B
windows: {'clean': 918, 'attack': 60, 'other_normal': 1857}

| config | clean FA | other-normal FA | files detected | DoS | force-neutral | rpm | standstill |
|---|---|---|---|---|---|---|---|
| L1 | 3.6% | 3.9% | 8/8 | 100.0% | 100.0% | 95.0% | 100.0% |
| L4t | 3.4% | 3.9% | 8/8 | 100.0% | 100.0% | 95.0% | 100.0% |
| L4p | 94.8% | 96.2% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t | 5.9% | 7.2% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 95.0% | 96.6% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 95.1% | 96.6% | 8/8 | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall DoS 100.0%, force-neutral 89.0%, rpm 97.2%, standstill 100.0%; FA clean frames 1.2%
- p: recall DoS 31.7%, force-neutral 0.0%, rpm 39.5%, standstill 0.0%; FA clean frames 1.2%

## set_03  variants {'t': ['all', 1], 'p': ['all', 2]}  shuffle pass: can.l4_timing False (0.478/0.645), can.l4_payload True (0.367/0.541)
### set_03 test_01 ['Silverado'] regime A
windows: {'clean': 1116, 'attack': 236, 'other_normal': 1506}

| config | clean FA | other-normal FA | files detected | DoS | double | force-neutral | fuzzing | triple |
|---|---|---|---|---|---|---|---|---|
| L1 | 2.8% | 2.9% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 0.0% | 0.0% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4p | 0.5% | 0.9% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t | 2.8% | 2.9% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 3.3% | 3.8% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 3.3% | 3.8% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall DoS 100.0%, double 100.0%, force-neutral 100.0%, fuzzing 100.0%, triple 100.0%; FA clean frames 0.5%
- p: recall DoS 100.0%, double 100.0%, force-neutral 100.0%, fuzzing 100.0%, triple 100.0%; FA clean frames 0.7%

### set_03 test_01 ['Silverado'] regime B
windows: {'clean': 1116, 'attack': 236, 'other_normal': 1506}

| config | clean FA | other-normal FA | files detected | DoS | double | force-neutral | fuzzing | triple |
|---|---|---|---|---|---|---|---|---|
| L1 | 3.7% | 4.4% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 1.5% | 2.3% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4p | 0.5% | 1.0% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t | 4.9% | 6.4% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 4.2% | 5.4% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 5.4% | 7.0% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall DoS 100.0%, double 100.0%, force-neutral 100.0%, fuzzing 100.0%, triple 100.0%; FA clean frames 0.9%
- p: recall DoS 100.0%, double 100.0%, force-neutral 100.0%, fuzzing 100.0%, triple 100.0%; FA clean frames 0.9%

### set_03 test_02 ['Subaru'] regime A
windows: {'clean': 805, 'attack': 314, 'other_normal': 2697}

| config | clean FA | other-normal FA | files detected | DoS | double | force-neutral | fuzzing | triple |
|---|---|---|---|---|---|---|---|---|
| L1 | 100.0% | 100.0% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 100.0% | 100.0% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4p | 100.0% | 100.0% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t | 100.0% | 100.0% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 100.0% | 100.0% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 100.0% | 100.0% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall DoS 100.0%, double 100.0%, force-neutral 100.0%, fuzzing 99.5%, triple 100.0%; FA clean frames 92.0%
- p: recall DoS 100.0%, double 100.0%, force-neutral 100.0%, fuzzing 98.2%, triple 100.0%; FA clean frames 91.7%

### set_03 test_02 ['Subaru'] regime B
windows: {'clean': 805, 'attack': 314, 'other_normal': 2697}

| config | clean FA | other-normal FA | files detected | DoS | double | force-neutral | fuzzing | triple |
|---|---|---|---|---|---|---|---|---|
| L1 | 2.6% | 2.0% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 0.1% | 0.6% | 10/10 | 97.6% | 100.0% | 22.2% | 98.1% | 99.1% |
| L4p | 0.4% | 0.4% | 8/10 | 97.6% | 100.0% | 0.0% | 99.0% | 100.0% |
| L1+L4t | 2.6% | 2.4% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 3.0% | 2.4% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 3.0% | 2.8% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall DoS 100.0%, double 100.0%, force-neutral 98.5%, fuzzing 99.8%, triple 100.0%; FA clean frames 1.8%
- p: recall DoS 100.0%, double 100.0%, force-neutral 9.5%, fuzzing 99.5%, triple 98.0%; FA clean frames 1.6%

### set_03 test_03 ['Silverado'] regime A
windows: {'clean': 1137, 'attack': 708, 'other_normal': 1410}

| config | clean FA | other-normal FA | files detected | rpm | speed | standstill | systematic | interval | rpm-accessory | speed-accessory |
|---|---|---|---|---|---|---|---|---|---|---|
| L1 | 2.5% | 2.3% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 0.0% | 0.0% | 14/14 | 100.0% | 100.0% | 100.0% | 93.3% | 100.0% | 5.2% | 65.4% |
| L4p | 0.7% | 0.9% | 11/14 | 100.0% | 47.4% | 100.0% | 97.8% | 0.2% | 0.0% | 57.7% |
| L1+L4t | 2.5% | 2.3% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 3.2% | 3.1% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 3.2% | 3.1% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall interval 100.0%, rpm 100.0%, rpm-accessory 96.6%, speed 100.0%, speed-accessory 99.4%, standstill 100.0%, systematic 99.9%; FA clean frames 0.5%
- p: recall interval 100.0%, rpm 99.9%, rpm-accessory 89.7%, speed 100.0%, speed-accessory 99.6%, standstill 99.9%, systematic 99.6%; FA clean frames 0.7%

### set_03 test_03 ['Silverado'] regime B
windows: {'clean': 1137, 'attack': 708, 'other_normal': 1410}

| config | clean FA | other-normal FA | files detected | rpm | speed | standstill | systematic | interval | rpm-accessory | speed-accessory |
|---|---|---|---|---|---|---|---|---|---|---|
| L1 | 6.5% | 4.8% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 96.6% | 100.0% |
| L4t | 0.6% | 2.0% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 37.9% | 73.1% |
| L4p | 1.5% | 3.5% | 13/14 | 100.0% | 100.0% | 100.0% | 98.9% | 95.3% | 3.4% | 88.5% |
| L1+L4t | 7.0% | 6.3% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 96.6% | 100.0% |
| L1+L4p | 7.9% | 7.9% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 96.6% | 100.0% |
| L1+L4t+L4p | 8.4% | 9.1% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 96.6% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall interval 100.0%, rpm 100.0%, rpm-accessory 96.6%, speed 100.0%, speed-accessory 99.6%, standstill 100.0%, systematic 100.0%; FA clean frames 0.9%
- p: recall interval 100.0%, rpm 99.9%, rpm-accessory 89.7%, speed 100.0%, speed-accessory 99.6%, standstill 99.9%, systematic 99.6%; FA clean frames 1.0%

### set_03 test_04 ['Subaru'] regime A
windows: {'clean': 528, 'attack': 975, 'other_normal': 2505}

| config | clean FA | other-normal FA | files detected | rpm | speed | standstill | systematic | interval | rpm-accessory | speed-accessory |
|---|---|---|---|---|---|---|---|---|---|---|
| L1 | 100.0% | 100.0% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 100.0% | 100.0% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4p | 100.0% | 100.0% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t | 100.0% | 100.0% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 100.0% | 100.0% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 100.0% | 100.0% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall interval 100.0%, rpm 100.0%, rpm-accessory 100.0%, speed 100.0%, speed-accessory 100.0%, standstill 100.0%, systematic 99.8%; FA clean frames 91.9%
- p: recall interval 100.0%, rpm 100.0%, rpm-accessory 100.0%, speed 100.0%, speed-accessory 100.0%, standstill 100.0%, systematic 99.1%; FA clean frames 91.7%

### set_03 test_04 ['Subaru'] regime B
windows: {'clean': 528, 'attack': 975, 'other_normal': 2505}

| config | clean FA | other-normal FA | files detected | rpm | speed | standstill | systematic | interval | rpm-accessory | speed-accessory |
|---|---|---|---|---|---|---|---|---|---|---|
| L1 | 3.6% | 5.9% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 3.6% | 3.0% | 14/14 | 62.3% | 98.2% | 100.0% | 100.0% | 97.9% | 62.1% | 100.0% |
| L4p | 3.0% | 4.4% | 9/14 | 26.1% | 100.0% | 0.0% | 100.0% | 100.0% | 0.0% | 100.0% |
| L1+L4t | 6.4% | 7.7% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 6.4% | 9.8% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 8.7% | 11.5% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall interval 100.0%, rpm 99.9%, rpm-accessory 99.6%, speed 100.0%, speed-accessory 100.0%, standstill 100.0%, systematic 99.9%; FA clean frames 2.1%
- p: recall interval 100.0%, rpm 99.0%, rpm-accessory 98.5%, speed 100.0%, speed-accessory 100.0%, standstill 0.0%, systematic 99.6%; FA clean frames 2.6%

## set_04  variants {'t': ['all', 1], 'p': ['maxid', 2]}  shuffle pass: can.l4_timing False (0.297/0.725), can.l4_payload False (0.285/0.676)
### set_04 test_01 ['Subaru'] regime A
windows: {'clean': 528, 'attack': 975, 'other_normal': 2505}

| config | clean FA | other-normal FA | files detected | interval | rpm | rpm-accessory | speed | speed-accessory | standstill | systematic |
|---|---|---|---|---|---|---|---|---|---|---|
| L1 | 2.1% | 3.1% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 1.3% | 0.7% | 14/14 | 100.0% | 100.0% | 100.0% | 98.2% | 100.0% | 100.0% | 100.0% |
| L4p | 1.7% | 1.2% | 14/14 | 100.0% | 100.0% | 100.0% | 98.2% | 100.0% | 100.0% | 69.4% |
| L1+L4t | 3.4% | 3.6% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 3.2% | 4.0% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 4.5% | 4.2% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall interval 100.0%, rpm 100.0%, rpm-accessory 100.0%, speed 100.0%, speed-accessory 100.0%, standstill 100.0%, systematic 100.0%; FA clean frames 0.8%
- p: recall interval 100.0%, rpm 100.0%, rpm-accessory 100.0%, speed 100.0%, speed-accessory 100.0%, standstill 100.0%, systematic 100.0%; FA clean frames 1.2%

### set_04 test_01 ['Subaru'] regime B
windows: {'clean': 528, 'attack': 975, 'other_normal': 2505}

| config | clean FA | other-normal FA | files detected | interval | rpm | rpm-accessory | speed | speed-accessory | standstill | systematic |
|---|---|---|---|---|---|---|---|---|---|---|
| L1 | 22.3% | 23.4% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 4.9% | 2.3% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4p | 9.7% | 5.2% | 14/14 | 100.0% | 100.0% | 100.0% | 98.2% | 100.0% | 100.0% | 75.0% |
| L1+L4t | 24.8% | 23.9% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 25.0% | 24.8% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 26.9% | 25.0% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall interval 100.0%, rpm 100.0%, rpm-accessory 100.0%, speed 100.0%, speed-accessory 100.0%, standstill 100.0%, systematic 100.0%; FA clean frames 1.7%
- p: recall interval 100.0%, rpm 100.0%, rpm-accessory 100.0%, speed 100.0%, speed-accessory 100.0%, standstill 100.0%, systematic 100.0%; FA clean frames 2.0%

### set_04 test_02 ['Traverse'] regime A
windows: {'clean': 2549, 'attack': 570, 'other_normal': 5217}

| config | clean FA | other-normal FA | files detected | interval | rpm | rpm-accessory | speed | speed-accessory | standstill | systematic |
|---|---|---|---|---|---|---|---|---|---|---|
| L1 | 100.0% | 100.0% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 100.0% | 100.0% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4p | 100.0% | 99.9% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t | 100.0% | 100.0% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 100.0% | 100.0% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 100.0% | 100.0% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall interval 100.0%, rpm 100.0%, rpm-accessory 100.0%, speed 100.0%, speed-accessory 100.0%, standstill 100.0%, systematic 100.0%; FA clean frames 99.5%
- p: recall interval 100.0%, rpm 100.0%, rpm-accessory 100.0%, speed 100.0%, speed-accessory 100.0%, standstill 100.0%, systematic 100.0%; FA clean frames 99.5%

### set_04 test_02 ['Traverse'] regime B
windows: {'clean': 2549, 'attack': 570, 'other_normal': 5217}

| config | clean FA | other-normal FA | files detected | interval | rpm | rpm-accessory | speed | speed-accessory | standstill | systematic |
|---|---|---|---|---|---|---|---|---|---|---|
| L1 | 3.9% | 3.2% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 1.7% | 1.0% | 13/14 | 100.0% | 76.5% | 63.8% | 47.1% | 8.3% | 78.0% | 100.0% |
| L4p | 28.1% | 21.1% | 10/14 | 8.2% | 100.0% | 51.7% | 17.6% | 0.0% | 63.4% | 72.3% |
| L1+L4t | 5.3% | 4.0% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 30.5% | 23.5% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 31.5% | 24.1% | 14/14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall interval 100.0%, rpm 70.5%, rpm-accessory 69.5%, speed 90.4%, speed-accessory 31.7%, standstill 74.1%, systematic 100.0%; FA clean frames 1.2%
- p: recall interval 31.5%, rpm 67.5%, rpm-accessory 60.2%, speed 76.9%, speed-accessory 13.3%, standstill 43.6%, systematic 99.9%; FA clean frames 1.3%

### set_04 test_03 ['Subaru'] regime A
windows: {'clean': 805, 'attack': 314, 'other_normal': 2697}

| config | clean FA | other-normal FA | files detected | DoS | double | force-neutral | fuzzing | triple |
|---|---|---|---|---|---|---|---|---|
| L1 | 2.7% | 2.4% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 1.2% | 0.9% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4p | 1.4% | 1.1% | 10/10 | 97.6% | 100.0% | 100.0% | 96.1% | 100.0% |
| L1+L4t | 3.4% | 3.0% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 3.2% | 3.1% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 3.6% | 3.3% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall DoS 100.0%, double 100.0%, force-neutral 97.2%, fuzzing 100.0%, triple 100.0%; FA clean frames 0.7%
- p: recall DoS 100.0%, double 100.0%, force-neutral 92.7%, fuzzing 100.0%, triple 100.0%; FA clean frames 1.0%

### set_04 test_03 ['Subaru'] regime B
windows: {'clean': 805, 'attack': 314, 'other_normal': 2697}

| config | clean FA | other-normal FA | files detected | DoS | double | force-neutral | fuzzing | triple |
|---|---|---|---|---|---|---|---|---|
| L1 | 2.4% | 2.2% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 1.9% | 1.3% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4p | 1.4% | 1.2% | 10/10 | 97.6% | 100.0% | 100.0% | 96.1% | 100.0% |
| L1+L4t | 3.2% | 3.0% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 2.9% | 3.0% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 3.4% | 3.4% | 10/10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall DoS 100.0%, double 100.0%, force-neutral 98.9%, fuzzing 100.0%, triple 100.0%; FA clean frames 1.4%
- p: recall DoS 100.0%, double 100.0%, force-neutral 93.1%, fuzzing 100.0%, triple 100.0%; FA clean frames 1.6%

### set_04 test_04 ['Traverse'] regime A
windows: {'clean': 970, 'attack': 332, 'other_normal': 2293}

| config | clean FA | other-normal FA | files detected | DoS | double | force-neutral | fuzzing | triple |
|---|---|---|---|---|---|---|---|---|
| L1 | 100.0% | 100.0% | 9/9 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 100.0% | 100.0% | 9/9 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4p | 100.0% | 100.0% | 9/9 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t | 100.0% | 100.0% | 9/9 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 100.0% | 100.0% | 9/9 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 100.0% | 100.0% | 9/9 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall DoS 100.0%, double 100.0%, force-neutral 100.0%, fuzzing 100.0%, triple 100.0%; FA clean frames 99.5%
- p: recall DoS 100.0%, double 100.0%, force-neutral 100.0%, fuzzing 100.0%, triple 100.0%; FA clean frames 99.5%

### set_04 test_04 ['Traverse'] regime B
windows: {'clean': 970, 'attack': 332, 'other_normal': 2293}

| config | clean FA | other-normal FA | files detected | DoS | double | force-neutral | fuzzing | triple |
|---|---|---|---|---|---|---|---|---|
| L1 | 2.9% | 2.8% | 9/9 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4t | 1.4% | 0.8% | 9/9 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L4p | 3.5% | 6.5% | 8/9 | 100.0% | 100.0% | 0.0% | 98.9% | 100.0% |
| L1+L4t | 3.8% | 3.4% | 9/9 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4p | 6.4% | 9.3% | 9/9 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| L1+L4t+L4p | 7.3% | 9.7% | 9/9 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): L1+L4t: False, L1+L4p: False, L1+L4t+L4p: False

frame level @1% (threshold from validation clean frames) 
- t: recall DoS 100.0%, double 100.0%, force-neutral 95.9%, fuzzing 100.0%, triple 100.0%; FA clean frames 1.4%
- p: recall DoS 86.1%, double 88.9%, force-neutral 27.1%, fuzzing 99.9%, triple 78.5%; FA clean frames 1.4%
