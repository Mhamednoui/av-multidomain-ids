#!/bin/bash
# Downloads the CSE-CIC-IDS2018 processed CSVs from the public AWS bucket (HTTPS, no account).
BASE="https://cse-cic-ids2018.s3.ca-central-1.amazonaws.com/Processed%20Traffic%20Data%20for%20ML%20Algorithms"
FILES="Friday-02-03-2018_TrafficForML_CICFlowMeter.csv
Friday-16-02-2018_TrafficForML_CICFlowMeter.csv
Friday-23-02-2018_TrafficForML_CICFlowMeter.csv
Thuesday-20-02-2018_TrafficForML_CICFlowMeter.csv
Thursday-01-03-2018_TrafficForML_CICFlowMeter.csv
Thursday-15-02-2018_TrafficForML_CICFlowMeter.csv
Thursday-22-02-2018_TrafficForML_CICFlowMeter.csv
Wednesday-14-02-2018_TrafficForML_CICFlowMeter.csv
Wednesday-21-02-2018_TrafficForML_CICFlowMeter.csv
Wednesday-28-02-2018_TrafficForML_CICFlowMeter.csv"
for f in $FILES; do
  echo "START $f $(date -Iseconds)"
  curl -C - -L --retry 5 --retry-delay 5 -sS -o "$f" "$BASE/$f"
  echo "END $f rc=$? size=$(stat -c %s "$f") $(date -Iseconds)"
done
echo ALLDONE $(date -Iseconds)
