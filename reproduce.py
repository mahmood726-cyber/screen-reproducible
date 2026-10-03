#!/usr/bin/env python3
"""Re-run the whole Screen experiment and check every number against the paper.

  python reproduce.py            # full run: 19 datasets, Screen 10 seeds, ASReview NB+SVM 3 seeds
  python reproduce.py --quick    # smoke run: 4 small datasets, 1 seed each (a few minutes)

Steps: verify pinned tool versions -> fetch + SHA-256-verify data -> run Screen, ASReview
and de-duplication benchmarks in parallel (one process per dataset) -> build tables,
figures and statistics -> print reproduced vs expected, PASS/FAIL per number.
Exit code 0 only if every number passes.
"""
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable

FULL = {
    "datasets": None,  # all 19, from data/corpora/manifest.json
    "screen_seeds": "101,202,303,404,505,606,707,808,909,1010",
    "asreview_seeds": "42,7,2024",
    "dedup_sizes": "2000,10000,50000,100000",
    "expected": "expected/paper_values.json",
}
QUICK = {
    "datasets": ["cohen_antihistamines", "cohen_urinaryincontinence", "cohen_estrogens", "cohen_nsaids"],
    "screen_seeds": "101",
    "asreview_seeds": "42",
    "dedup_sizes": "2000",
    "expected": "expected/quick_values.json",
}


def check_versions(strict):
    """Report the tool versions actually in use and compare with the pins."""
    want_node = (ROOT / ".nvmrc").read_text().strip().lstrip("v")
    node = shutil.which("node")
    if not node:
        sys.exit("node not found on PATH; install Node " + want_node + " (see README) or use the Docker image")
    got_node = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip().lstrip("v")
    pins = {}
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        line = line.split("#")[0].split(";")[0].strip()
        if "==" in line:
            k, v = line.split("==", 1)
            pins[k.strip().lower()] = v.strip()
    from importlib.metadata import version, PackageNotFoundError
    problems = []
    if got_node != want_node:
        problems.append(f"node {got_node} (pinned {want_node})")
    for pkg in ("asreview", "scikit-learn", "numpy", "scipy", "pandas", "matplotlib"):
        try:
            v = version(pkg)
        except PackageNotFoundError:
            sys.exit(f"python package {pkg} missing: run  pip install -r requirements.txt")
        if pins.get(pkg) and v != pins[pkg]:
            problems.append(f"{pkg} {v} (pinned {pins[pkg]})")
    print(f"environment: Python {platform.python_version()}, Node {got_node}, {platform.system()} {platform.machine()}, {os.cpu_count()} CPUs")
    if problems:
        msg = "version mismatch: " + "; ".join(problems)
        if strict:
            sys.exit(msg + "\n(use --allow-version-mismatch to run anyway)")
        print("WARNING: " + msg + " -- results may differ from the paper")


# Single-threaded numerics and a fixed hash seed in every worker: removes thread-count- and
# hash-order-dependent float summation as a source of cross-machine differences.
DETERMINISTIC_ENV = {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                     "VECLIB_MAXIMUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1", "PYTHONHASHSEED": "0"}


def run(cmd, log):
    t0 = time.time()
    env = {**os.environ, **DETERMINISTIC_ENV}
    with open(log, "w", encoding="utf-8") as f:
        p = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, env=env)
    return p.returncode, time.time() - t0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quick", action="store_true", help="fast smoke run (4 small datasets, 1 seed)")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 2, help="parallel processes (default: all CPUs)")
    ap.add_argument("--skip-asreview", action="store_true", help="skip the ASReview comparator (its numbers will FAIL)")
    ap.add_argument("--allow-version-mismatch", action="store_true")
    ap.add_argument("--analysis-only", action="store_true", help="rebuild outputs from existing results")
    a = ap.parse_args()
    cfg = QUICK if a.quick else FULL
    mode = "quick" if a.quick else "full"
    res, out, logs = ROOT / "results" / mode, ROOT / "outputs" / mode, ROOT / "results" / mode / "logs"
    t_start = time.time()
    check_versions(strict=not a.allow_version_mismatch)

    if not a.analysis_only:
        if subprocess.run([PY, "bench/fetch_data.py"], cwd=ROOT).returncode:
            sys.exit("data fetch/verification failed")
        if res.exists():
            shutil.rmtree(res)
        logs.mkdir(parents=True)
        man = json.loads((ROOT / "data" / "corpora" / "manifest.json").read_text(encoding="utf-8"))
        sizes = {d["id"]: d["n"] for d in man["datasets"]}
        ids = cfg["datasets"] or [d["id"] for d in man["datasets"]]
        ids = sorted(ids, key=lambda i: -sizes[i])  # largest first for load balancing
        tasks = [("dedup", ["node", "bench/run_dedup.mjs", "--sizes", cfg["dedup_sizes"], "--out", str(res / "dedup.json")])]
        for i in ids:
            tasks.append((f"screen:{i}", ["node", "bench/run_screen.mjs", "--dataset", i, "--seeds", cfg["screen_seeds"],
                                         "--out", str(res / "screen" / f"{i}.json")]))
            if not a.skip_asreview:
                tasks.append((f"asreview:{i}", [PY, "bench/run_asreview.py", "--dataset", i, "--models", "nb,svm",
                                                "--seeds", cfg["asreview_seeds"], "--out", str(res / "asreview" / f"{i}.json")]))
        print(f"running {len(tasks)} jobs on {a.jobs} parallel processes ({mode} mode); logs in {logs.relative_to(ROOT)}")
        failed = []
        with ThreadPoolExecutor(max_workers=a.jobs) as ex:
            fut = {ex.submit(run, cmd, logs / (name.replace(":", "_") + ".log")): name for name, cmd in tasks}
            for k, f in enumerate(as_completed(fut), 1):
                rc, secs = f.result()
                name = fut[f]
                print(f"  [{k:>2}/{len(tasks)}] {name:<42} {'ok' if rc == 0 else 'FAILED (rc=%d)' % rc}  {secs:6.0f} s", flush=True)
                if rc:
                    failed.append(name)
        if failed:
            sys.exit("benchmark jobs failed: " + ", ".join(failed) + f" -- see {logs}")

    rc = subprocess.run([PY, "analysis/make_outputs.py", "--results", str(res), "--outputs", str(out),
                         "--expected", cfg["expected"]], cwd=ROOT).returncode
    print(f"total time {time.time() - t_start:.0f} s")
    sys.exit(rc)


if __name__ == "__main__":
    main()
