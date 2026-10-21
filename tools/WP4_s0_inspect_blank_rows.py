"""WP4 S0 check: inspect the rows of the Thursday-Morning-WebAttacks CSV with an empty Label.

Reads the extracted D10 CSVs only (untrusted data, read-only, run with python -I).
Output: results/WP4/s0_d10_blank_label_check.json
"""
import csv, json, os, collections

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data_extra', 'D10_cicids2017_generated_flows', 'extracted', 'TrafficLabelling'))
RES = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'results', 'WP4', 's0_d10_blank_label_check.json'))


def rows_of(name):
    csv.field_size_limit(1 << 24)
    with open(os.path.join(BASE, name), newline='', encoding='utf-8', errors='replace') as f:
        r = csv.reader(f)
        header = [h.strip() for h in next(r)]
        return header, list(r)


def main():
    hw, web = rows_of('Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv')
    li = hw.index('Label')
    blank_idx = [i for i, r in enumerate(web) if r[li] == '']
    labelled_idx = [i for i, r in enumerate(web) if r[li] != '']
    contiguous = blank_idx == list(range(blank_idx[0], blank_idx[0] + len(blank_idx))) if blank_idx else False
    _, inf = rows_of('Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv')
    inf_set = collections.Counter(tuple(r) for r in inf)
    blank_in_inf = sum(1 for i in blank_idx if inf_set[tuple(web[i])] > 0)
    blank_ts_empty = sum(1 for i in blank_idx if web[i][hw.index('Timestamp')] == '')
    out = {
        'file': 'Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv',
        'rows_total': len(web), 'rows_labelled': len(labelled_idx), 'rows_blank_label': len(blank_idx),
        'blank_label_block_contiguous': contiguous,
        'blank_label_first_index': blank_idx[0] if blank_idx else None,
        'blank_label_rows_with_empty_timestamp': blank_ts_empty,
        'blank_label_rows_identical_to_infiltration_file_row': blank_in_inf,
        'infiltration_file_rows': len(inf),
    }
    with open(RES, 'w') as f:
        json.dump(out, f, indent=1)
    print(json.dumps(out))


if __name__ == '__main__':
    main()
