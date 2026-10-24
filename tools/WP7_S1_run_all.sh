#!/bin/bash
# WP7 S1: run the five stream-vs-batch tools one after the other (latency is measured, so they do not overlap). From codes_v3/.
PY=/c/Users/nouir/miniconda3/envs/tf/python.exe
export PYTHONDONTWRITEBYTECODE=1
for d in ${@:-gps can cross v2x lidar}; do
  $PY -I -u -W ignore tools/WP7_S1_$d.py > results/WP7/logs/$d.log 2>&1
  echo "$d exit $?" >> results/WP7/logs/run_all.log
done
