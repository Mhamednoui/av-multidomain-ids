"""WP3 S1: save the drive split with groups '<drive>/<file>' to results/WP3/split.json (acceptance A5)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lidar.data import save_split

m = save_split()
print({p: (len(v["drives"]), v["scans"]) for p, v in m["parts"].items()})
