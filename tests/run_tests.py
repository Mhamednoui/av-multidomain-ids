"""Minimal test runner (no pytest needed): runs every test_* function in tests/**/test_*.py.
Copied from codes_v2/tests/run_tests.py; extended to look in sub-folders (tests/<domain>/).
Usage (from codes_v3/): python tests/run_tests.py [substring of a file path]
"""
import importlib.util
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.dont_write_bytecode = True


def main():
    flt = sys.argv[1] if len(sys.argv) > 1 else ""
    passed = failed = skipped = 0
    for f in sorted(HERE.rglob("test_*.py")):
        if flt not in str(f):
            continue
        spec = importlib.util.spec_from_file_location(f"{f.parent.name}_{f.stem}", f)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for name in sorted(n for n in dir(mod) if n.startswith("test_")):
            t0 = time.time()
            try:
                getattr(mod, name)()
                passed += 1
                print(f"PASS  {f.parent.name}/{name} ({time.time() - t0:.1f}s)")
            except Exception as e:
                if type(e).__name__ == "Skip":
                    skipped += 1
                    print(f"SKIP  {name}: {e}")
                else:
                    failed += 1
                    print(f"FAIL  {f.parent.name}/{name}")
                    traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
