"""WP3 S6 validation probe: sustained-step detection of single statistics on val episodes (sensor-fixed vs world-fixed)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from WP3_S6_lib import *  # noqa
clean = load("clean", TRAINVAL)
ep, epw = load("ep_val", VAL), load("epw_val", VAL)
for s in ["fix_tot", "fix_cc", "app_cc", "van_cc", "miss_w20"]:
    L = layer("L2d", [s], clean)
    for tag, e in (("S", ep), ("W", epw)):
        e = e[e.step >= 2]
        mv = e.disp > 0.5
        print(s, tag, "all %.2f" % alarm(L, e).mean(), "moving %.2f (n=%d)" % (alarm(L, e[mv]).mean(), mv.sum()), "by kind",
              {k: round(float(alarm(L, g).mean()), 2) for k, g in e[mv].groupby("attack")})
    print(s, "clean moving FA %.3f" % alarm(L, clean[clean.disp > 0.5]).mean(), "stopped %.3f" % alarm(L, clean[clean.disp <= 0.5]).mean(), "q99", L.threshold)
