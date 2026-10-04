# screen-reproducible

[![reproduce](https://github.com/mahmood726-cyber/screen-reproducible/actions/workflows/reproduce.yml/badge.svg)](https://github.com/mahmood726-cyber/screen-reproducible/actions/workflows/reproduce.yml)
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/mahmood726-cyber/screen-reproducible?quickstart=1)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23132680.svg)](https://doi.org/10.5281/zenodo.23132680)
[![Latest verified run](https://img.shields.io/badge/latest%20verified%20run-results%20page-2c5e8a)](https://mahmood726-cyber.github.io/screen-reproducible/)

**Screen** is an offline, browser-only tool for title–abstract screening in systematic
reviews. It has keyboard screening, dual review with Cohen's κ, de-duplication, Naive Bayes
active-learning ranking and PRISMA counts, and nothing is installed or uploaded. This
repository holds a frozen copy of Screen (from [allmeta](https://github.com/mahmood726-cyber/allmeta),
commit `421ba13`, byte-identical to the [live version](https://mahmood726-cyber.github.io/allmeta/screen/))
and everything needed to re-run the benchmark in the accompanying F1000Research article. It
contains:
- the 19 labelled review datasets and a de-duplication dataset
- a harness that runs the app's own JavaScript unchanged
- the ASReview 2.2 comparator (Naive Bayes and its current SVM default)
- the analysis that regenerates every table, figure and statistic, and checks each number against the paper

## Reproduce in one click

There are three ways in, from no effort to a full independent re-run.

**1. See the latest verified runs (nothing to run).**

The [results page](https://mahmood726-cyber.github.io/screen-reproducible/) is published by CI. It has two parts:
- **Latest full run:** every number in the paper.
- **Latest quick run:** run on every push.

Each shows the PASS/FAIL table, the result on each of Docker, Linux, Windows and macOS, and, for full runs, the bit-identity check.

**2. Open in GitHub Codespaces (one click).**

Click the *Open in GitHub Codespaces* badge above, then *Create codespace*.
- The pinned environment is built from this repository's `Dockerfile`: Python 3.13.13, Node 24.15.0 and the pinned packages, including ASReview 2.2.
- The datasets are then fetched and checked, and the quick reproduction runs automatically. Its log ends with `QUICK RUN: ALL PASS`, and the report is in `outputs/quick/reproduction_report.md`.
- For the full run, type `python reproduce.py` in the terminal. It takes about 30–80 minutes, depending on cores, and writes `outputs/full/`.

Limits:
- You need to be signed in to GitHub.
- The codespace runs on your own Codespaces allowance. Personal accounts get a free monthly quota of core-hours and storage (see GitHub's billing page); this configuration requests a 4-core machine, so it uses that quota twice as fast as a 2-core one.
- The first build takes a few minutes.
- `codespaces-check` in Actions builds the same devcontainer and runs its automatic quick run on every relevant change.

**3. Re-run the CI yourself (one click in a fork).**

Only maintainers can trigger workflows on this repository, so use your own copy:
1. Click **Fork**.
2. In your fork, open the **Actions** tab and click *I understand my workflows, go ahead and enable them*. GitHub disables workflows in new forks.
3. Choose **reproduce**, then **Run workflow**, with mode **full** (the default).

That runs every number in the paper on Docker, Linux, Windows and macOS (about 20–40 minutes per platform, in parallel), followed by the bit-identity check. Actions are free on public repositories.
- Each job's **summary** shows its PASS/FAIL report.
- **Artifacts** hold `reproduction-report-full-<platform>` and the complete outputs.
- Mode **quick** is the short smoke run.
- Publishing to Pages happens only on this repository, so it is skipped in forks.

**On your own machine:**

```bash
git clone https://github.com/mahmood726-cyber/screen-reproducible && cd screen-reproducible
python -m pip install -r requirements.txt
python reproduce.py --quick        # about 1 minute; full run: python reproduce.py
```

You need Python 3.13 and Node.js 24.15.0 on your PATH. Alternatively, use Docker:

```bash
docker build -t screen-reproducible . && docker run --rm screen-reproducible --full
```

`make quick` and `make reproduce` do the same as the two `reproduce.py` commands.

**Using the app:** open `app/screen/index.html` in a browser (double-clicking the file works), or run `python -m http.server 8080` and go to http://localhost:8080.

## What `reproduce.py` does

1. Checks that the Node and Python package versions match the pins and refuses to run if they differ (`--allow-version-mismatch` overrides).
2. Downloads the 15 Cohen 2006 datasets from a pinned commit and checks all 20 data files by SHA-256 (see [data/README.md](data/README.md) for why those 15 are downloaded rather than included).
3. Runs, in parallel with one process per dataset:
   - **Screen**: `bench/run_screen.mjs`. The ranking functions are copied verbatim from `app/screen/index.html` into a Node `vm` with no browser, then simulated with per-record active learning over 10 seeds.
   - **ASReview 2.2**: `bench/run_asreview.py`. Runs ELAS u3 (Naive Bayes) and ELAS u4 (SVM, ASReview's current default) with ASReview's own code, over 3 seeds.
   - **De-duplication**: `bench/run_dedup.mjs`. Runs the app's own de-duplication code on author-labelled duplicates, reformatted duplicates, blocked versus exhaustive comparison, and synthetic corpora of up to 100,000 records.
4. Builds the outputs (`analysis/make_outputs.py`), prints *expected vs reproduced* with PASS/FAIL for every number, and exits non-zero if any number fails.

## Expected run times

| Mode | What runs | 4-core laptop (Windows) | GitHub Actions `ubuntu-latest` |
|---|---|---|---|
| `--quick` | 4 small datasets, 1 seed per tool, de-dup up to 2,000 records | ~30 s | ~30 s |
| full | 19 datasets; Screen 10 seeds; ASReview NB + SVM 3 seeds; de-dup up to 100,000 records | ~80 min | ~32 min |

The full run is CPU-bound and uses every core by default (`--jobs N` to change this). Most of the
time is spent in ASReview's SVM on the three largest datasets.

## Outputs and how they map to the paper

Everything is written to `outputs/full/` (or `outputs/quick/`):

| File | Paper |
|---|---|
| `table1_wss95.md` / `.csv` | Table 1: WSS@95 per dataset for Screen, ASReview NB and ASReview SVM |
| `table2_dedup.md` / `.csv` | Table 2: de-duplication results |
| `docs/screenshots/step1.png` … `step6.png` | Figure 1 (A–F): the six steps of a screening session (see docs/screenshots/README.md) |
| `figure2_wss95_by_dataset.png` | Figure 2: WSS@95 by dataset, three tools |
| `figure3_paired_differences.png` | Figure 3: paired per-dataset differences, with Wilcoxon p |
| `figure4_dedup_scaling.png` | Figure 4: de-duplication workload, blocked vs all pairs |
| `visual_abstract.png` | Visual abstract |
| `stats.json` | All statistics quoted in the text (means 0.447 / 0.428 / 0.466; 12/19 and 4/19; Wilcoxon p 0.1819 (W = 61) and 0.0494 (W = 46); recall at 10/20/50%; stopping-rule count) |
| `reproduction_report.md` / `.json` | Expected vs reproduced, PASS/FAIL per number |

Raw per-dataset results (with per-seed values) are in `results/<mode>/`. The values the
check compares against are in `expected/paper_values.json` (copied from the paper) and
`expected/quick_values.json`. The quick reference values were computed independently with
allmeta's original benchmark scripts, not with this repository's harness.

**What is not exactly reproducible:** de-duplication run times (milliseconds) depend on the
machine and are reported but not checked. Comparison counts and all accuracy numbers are
deterministic and are checked.

## System requirements

- Python 3.13 (tested with 3.13.13) and Node.js 24.15.0. Exact versions of all Python packages are pinned in `requirements.txt` (asreview 2.2, scikit-learn 1.8.0, numpy 2.4.4, scipy 1.17.1, pandas 2.3.3, matplotlib 3.10.9).
- The benchmark harness uses only Node built-ins, so `npm install` is not needed (`package-lock.json` is empty by design).
- About 1 GB of RAM per parallel job and about 60 MB of disk. Internet access is needed once, to download the Cohen datasets (the Docker image downloads them at build time).
- Windows, macOS and Linux. CI runs quick mode on all three for every push, plus a Docker build and quick run. A manually dispatched full run executes on Linux, Windows, macOS and in Docker, and a final job checks that all four produce bit-identical results.

## Determinism

Results are bit-identical across machines (checked by `analysis/compare_runs.py`, which compares
every per-seed value with `==`). Three things make that true:
- **Screen** ranks with JavaScript's stable `Array.prototype.sort` and seeded PRNGs, and Node is pinned to 24.15.0.
- **ASReview's SVM** (scikit-learn `LinearSVC`, `random_state=None`) takes its random seed from NumPy's global generator. `bench/run_asreview.py` therefore calls `np.random.seed(seed)` before every simulation. Without this the result depended on what had run earlier in the process: on Opiods, WSS@95 ranged from 0.269 to 0.277.
- **ASReview ranks** with `np.argsort(-p)`, NumPy's unstable sort, which NumPy 2.x dispatches to CPU-specific SIMD code. Records with exactly tied probabilities were therefore ordered differently on different CPUs. The harness uses `StableMax`, which is the same query strategy with `kind="stable"` (ties broken by record order). This changes ASReview's results only where probabilities tie exactly.

BLAS/OpenMP are also limited to one thread, and `PYTHONHASHSEED=0` is set.

## Notes on the benchmark

- Screen's default settings were tuned on these same 19 datasets, using different seeds. Expect lower work savings on new reviews.
- The benchmark retrains after every decision. In the app, retraining happens when the user selects **Train**.
- The two tools start differently: Screen starts from 20 random records, ASReview from one relevant and one irrelevant record. Both count these starting records as screened.
- The harness fixes a bug in allmeta's `benchmark/run_headless.mjs`: `ML_NGRAM_MAX`, `ML_DF_MAX_FRAC` and `dec` were missing from its extraction lists, so it crashed against the current app. See `bench/extract.mjs`.

## How to cite

Please cite:
- the article (reference to be added on publication);
- this repository, v1.0.0, doi:[10.5281/zenodo.23132680](https://doi.org/10.5281/zenodo.23132680) (see `CITATION.cff`);
- the original dataset authors listed in [data/README.md](data/README.md).

Releases are archived on Zenodo through the GitHub–Zenodo integration (metadata in `.zenodo.json`).

## Licence

MIT (see `LICENSE`), the same as allmeta. The data keep their own licences (see `data/README.md`).
