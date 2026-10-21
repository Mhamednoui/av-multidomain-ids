"""WP4 S0: extract the D10 GeneratedLabelledFlows zip (data only, no code run) and inventory it.

Input: ../data_extra/D10_cicids2017_generated_flows/raw/GeneratedLabelledFlows.zip
Output: ../data_extra/D10_cicids2017_generated_flows/extracted/ and results/WP4/s0_d10_inventory.json
Run with python -I (downloaded data is untrusted: read only, never execute).
"""
import csv, json, os, sys, zipfile, collections

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data_extra', 'D10_cicids2017_generated_flows'))
ZIP = os.path.join(BASE, 'raw', 'GeneratedLabelledFlows.zip')
OUT_DIR = os.path.join(BASE, 'extracted')
RES = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'results', 'WP4', 's0_d10_inventory.json'))
REQUIRED = ['Flow ID', 'Source IP', 'Source Port', 'Destination IP', 'Destination Port', 'Protocol', 'Timestamp', 'Label']


def main():
    csv.field_size_limit(1 << 24)
    with zipfile.ZipFile(ZIP) as z:
        names = z.namelist()
        bad = z.testzip()
        for n in names:
            if os.path.isabs(n) or '..' in n.replace(chr(92), '/').split('/'):
                raise SystemExit('unsafe member name: %r' % n)
        # member folder name has a trailing space ("TrafficLabelling /"): strip it for Windows paths
        clean = {}
        for info in z.infolist():
            if info.is_dir() or not info.filename.lower().endswith('.csv'):
                continue
            parts = [s.strip() for s in info.filename.replace(chr(92), '/').split('/')]
            dest = os.path.join(OUT_DIR, *parts)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with z.open(info) as src, open(dest, 'wb') as dst:
                dst.write(src.read())
            clean[info.filename] = dest
    files = []
    for n, p in clean.items():
        with open(p, newline='', encoding='utf-8', errors='replace') as f:
            r = csv.reader(f)
            header = [h.strip() for h in next(r)]
            labels = collections.Counter()
            rows = 0
            ts_first = ts_last = None
            li = header.index('Label') if 'Label' in header else None
            ti = header.index('Timestamp') if 'Timestamp' in header else None
            for row in r:
                if len(row) != len(header):
                    continue
                rows += 1
                if li is not None:
                    labels[row[li]] += 1
                if ti is not None:
                    if ts_first is None:
                        ts_first = row[ti]
                    ts_last = row[ti]
        files.append({
            'path': n, 'bytes': os.path.getsize(p), 'rows': rows,
            'columns': len(header), 'missing_required': [c for c in REQUIRED if c not in header],
            'labels': dict(labels), 'timestamp_first': ts_first, 'timestamp_last': ts_last,
        })
    total = sum(f['rows'] for f in files)
    out = {'zip_members': names, 'zip_testzip_error': bad, 'csv_files': files, 'total_rows': total}
    os.makedirs(os.path.dirname(RES), exist_ok=True)
    with open(RES, 'w') as f:
        json.dump(out, f, indent=1)
    print(json.dumps({'members': len(names), 'total_rows': total}))
    for f in files:
        print(f['path'], f['rows'], f['columns'], f['missing_required'], f['timestamp_first'], f['timestamp_last'])


if __name__ == '__main__':
    sys.exit(main())
