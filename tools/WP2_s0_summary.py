"""Summarise results/WP2/s0_inventory.json (WP2 S0) into a short table on stdout."""
import json, sys, collections
d = json.load(open(sys.argv[1]))
F = d['files']
print('files', len(F), 'rows', sum(f['rows'] for f in F), 'bytes', sum(f['bytes'] for f in F))
print('cols set', {tuple(f['cols']) for f in F})
print('label keys', {k for f in F for k in f['labels']})
print('non-monotonic', [f['path'] for f in F if not f['monotonic']], 'nan', sum(f['nan_ts'] for f in F))
print('hexlen', sorted({k for f in F for k in f['hexlen_counts']}))
print('t_first', sorted({f['t_first'] for f in F})[:5])
by = collections.defaultdict(lambda: [0, 0, 0])
for f in F:
    s, sub = f['path'].split('/')[:2]
    a = f['labels'].get('1', 0); n = f['labels'].get('0', 0)
    by[(s, sub)][0] += 1; by[(s, sub)][1] += n; by[(s, sub)][2] += a
for k, v in sorted(by.items()): print(k, 'files %d normal %d attack %d' % tuple(v))
z = [f['path'] for f in F if f['labels'].get('1', 0) == 0 and 'attack-free' not in f['path']]
print('no-attack-frames non attack-free files:', z)
