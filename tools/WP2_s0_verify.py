"""WP2 S0: inventory and integrity check of D11 can-train-and-test (read-only).
Inputs: root folder of the extracted dataset. Output: results/WP2/s0_inventory.json.
Run with python -I. Per CSV: header, rows, label counts, ids, data_field lengths, time span,
monotonic timestamps. Nothing from the dataset is executed."""
import sys, os, json, glob
import pandas as pd

root, out = sys.argv[1], sys.argv[2]
files = sorted(glob.glob(os.path.join(root, 'set_*', '*', '*.csv')))
res = []
for f in files:
    n = 0; lab = {}; ids = set(); lens = {}; tmin = None; tmax = None; mono = True; last = None; bad = 0
    cols = None
    for ch in pd.read_csv(f, dtype={'arbitration_id': str, 'data_field': str}, chunksize=500000):
        cols = list(ch.columns)
        n += len(ch)
        for k, v in ch['attack'].value_counts().items():
            lab[str(k)] = lab.get(str(k), 0) + int(v)
        ids.update(ch['arbitration_id'].unique())
        for k, v in ch['data_field'].str.len().value_counts().items():
            lens[int(k)] = lens.get(int(k), 0) + int(v)
        t = ch['timestamp'].to_numpy()
        bad += int(ch['timestamp'].isna().sum())
        if last is not None and t[0] < last: mono = False
        if (t[1:] < t[:-1]).any(): mono = False
        last = t[-1]
        tmin = t[0] if tmin is None else tmin; tmax = t[-1]
    p = os.path.relpath(f, root).replace(os.sep, '/')
    res.append(dict(path=p, bytes=os.path.getsize(f), cols=cols, rows=n, labels=lab, n_ids=len(ids),
                    hexlen_counts=lens, t_first=float(tmin), duration_s=float(tmax - tmin),
                    monotonic=mono, nan_ts=bad))
    print(p, n, lab, flush=True)
json.dump(dict(root=root, n_files=len(res), files=res), open(out, 'w'), indent=1)
