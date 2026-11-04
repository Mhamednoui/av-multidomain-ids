#!/bin/bash
# usage: WP9_B2_driver.sh <table> <stages...>   (runs T, G, B in turn; resumable)
cd /c/Users/nouir/PFE/codes_v3
t=$1; shift
for p in T G B; do
  PYTHONDONTWRITEBYTECODE=1 /c/Users/nouir/miniconda3/envs/tf/python.exe -u -W ignore -I tools/WP9_B2_run.py $t $p "$@"
done
