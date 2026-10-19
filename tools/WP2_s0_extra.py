"""WP2 S0 extra checks: duplicate files (md5) across sets, size of timestamp inversions."""
import sys, os, glob, hashlib, collections, json
import numpy as np, pandas as pd
root = sys.argv[1]
md = collections.defaultdict(list)
for f in sorted(glob.glob(os.path.join(root, 'set_*', '*', '*.csv'))):
    h = hashlib.md5(open(f, 'rb').read()).hexdigest()
    md[h].append(os.path.relpath(f, root).replace(os.sep, '/'))
dups = [v for v in md.values() if len(v) > 1]
print('distinct', len(md), 'dup groups', len(dups))
for v in dups[:6]: print(v)
for p in ['set_01/test_01_known_vehicle_known_attack/rpm-3.csv', 'set_01/test_03_known_vehicle_unknown_attack/double-3.csv']:
    d = pd.read_csv(os.path.join(root, p))
    dt = np.diff(d.timestamp.to_numpy()); neg = dt < 0
    print(p, 'inversions', int(neg.sum()), 'min dt', dt.min(), 'attack rows after inversion', int(d.attack.to_numpy()[1:][neg].sum()))
    print(d[d.attack == 1].head(2).to_string())
json.dump(dict(distinct=len(md), dup_groups=dups), open(sys.argv[2], 'w'), indent=1)
