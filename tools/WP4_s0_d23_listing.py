"""WP4 S0: parse the S3 ListObjectsV2 XML of the CSE-CIC-IDS2018 processed folder into JSON.

Input: results/WP4/s0_d23_s3_listing_raw.xml (saved from
https://cse-cic-ids2018.s3.ca-central-1.amazonaws.com/?list-type=2&prefix=Processed%20Traffic%20Data%20for%20ML%20Algorithms/)
Output: results/WP4/s0_d23_listing.json  (file name -> size in bytes, CSV files only)
"""
import json, os
import xml.etree.ElementTree as ET

HERE = os.path.dirname(__file__)
SRC = os.path.abspath(os.path.join(HERE, '..', 'results', 'WP4', 's0_d23_s3_listing_raw.xml'))
OUT = os.path.abspath(os.path.join(HERE, '..', 'results', 'WP4', 's0_d23_listing.json'))
PREFIX = 'Processed Traffic Data for ML Algorithms/'


def main():
    ns = {'s3': 'http://s3.amazonaws.com/doc/2006-03-01/'}
    root = ET.parse(SRC).getroot()
    out = {}
    for c in root.findall('s3:Contents', ns):
        key = c.find('s3:Key', ns).text
        if key.startswith(PREFIX) and key.endswith('.csv'):
            out[key[len(PREFIX):]] = int(c.find('s3:Size', ns).text)
    with open(OUT, 'w') as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print(len(out), sum(out.values()))


if __name__ == '__main__':
    main()
