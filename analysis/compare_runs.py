"""Check that two (or more) full runs are bit-identical.

Compares every per-seed and per-dataset result value in results/<run>/{screen,asreview}/*.json
and results/<run>/dedup.json, ignoring only fields that record wall-clock time or the
interpreter version string. Floats are compared with ==, not a tolerance.

  python analysis/compare_runs.py runA/results/full runB/results/full [runC/results/full ...]
Exit code 0 only if all runs are identical.
"""
import json
import sys
from pathlib import Path

IGNORE = {"seconds", "nb_seconds", "svm_seconds", "blocked_ms", "brute_ms", "node", "environment"}


def flatten(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in IGNORE:
                continue
            out.update(flatten(v, f"{prefix}.{k}" if prefix else k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = obj
    return out


def load(run):
    run = Path(run)
    vals = {}
    for f in sorted(run.glob("screen/*.json")) + sorted(run.glob("asreview/*.json")) + [run / "dedup.json"]:
        rel = f.relative_to(run).as_posix()
        vals.update({f"{rel}:{k}": v for k, v in flatten(json.loads(f.read_text())).items()})
    return vals


def main():
    runs = sys.argv[1:]
    if len(runs) < 2:
        sys.exit(__doc__)
    ref = load(runs[0])
    bad = 0
    for other in runs[1:]:
        cur = load(other)
        keys = set(ref) | set(cur)
        diffs = [k for k in sorted(keys) if ref.get(k, "<missing>") != cur.get(k, "<missing>")]
        print(f"{runs[0]}  vs  {other}: {len(keys)} values compared, {len(diffs)} differ")
        for k in diffs[:40]:
            print(f"   {k}: {ref.get(k, '<missing>')!r} != {cur.get(k, '<missing>')!r}")
        bad += len(diffs)
    print("BIT-IDENTICAL" if bad == 0 else "RUNS DIFFER")
    sys.exit(0 if bad == 0 else 1)


if __name__ == "__main__":
    main()
