"""WP4 S0 check: inventory of the downloaded CSE-CIC-IDS2018 processed CSVs (D23).

Streams each CSV (untrusted data, read-only, run with python -I). Checks: file size equals the
S3 listing size, header columns, row count, label counts, repeated header rows, empty rows.
Output: results/WP4/s0_d23_inventory.json
"""
import csv, json, os, collections

DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data_extra', 'D23_cse-cic-ids2018', 'raw'))
LISTING = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'results', 'WP4', 's0_d23_listing.json'))
RES = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'results', 'WP4', 's0_d23_inventory.json'))


def main():
    csv.field_size_limit(1 << 24)
    listing = json.load(open(LISTING))
    out = []
    for name, size in sorted(listing.items()):
        p = os.path.join(DIR, name)
        rec = {'file': name, 'listing_bytes': size, 'local_bytes': os.path.getsize(p) if os.path.exists(p) else None}
        rec['size_match'] = rec['local_bytes'] == size
        labels = collections.Counter()
        rows = empty = header_repeats = 0
        header = None
        with open(p, newline='', encoding='utf-8', errors='replace') as f:
            r = csv.reader(f)
            for row in r:
                if header is None:
                    header = [h.strip() for h in row]
                    li = header.index('Label') if 'Label' in header else None
                    continue
                if not any(c.strip() for c in row):
                    empty += 1
                    continue
                if [h.strip() for h in row] == header:
                    header_repeats += 1
                    continue
                rows += 1
                if len(row) != len(header):
                    labels['<ragged row>'] += 1
                    continue
                if li is not None:
                    labels[row[li].strip()] += 1
        rec.update({'columns': len(header or []), 'has_label': li is not None if header else False,
                    'data_rows': rows, 'empty_rows': empty, 'repeated_header_rows': header_repeats,
                    'labels': dict(labels), 'header_first5': (header or [])[:5]})
        out.append(rec)
        print(json.dumps({k: rec[k] for k in ('file', 'size_match', 'columns', 'data_rows', 'empty_rows', 'repeated_header_rows')}), flush=True)
    with open(RES, 'w') as f:
        json.dump({'files': out, 'total_rows': sum(x['data_rows'] for x in out)}, f, indent=1)
    print('TOTAL', sum(x['data_rows'] for x in out))


if __name__ == '__main__':
    main()
