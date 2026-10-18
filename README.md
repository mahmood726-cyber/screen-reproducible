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
commit `421ba13`, byte-identical to the [live version](https://mahmood726-cyber.github.io/allmeta/screen/)
at the time it was archived) and everything needed to re-run the benchmark in the accompanying
F1000Research article. The article describes allmeta v1.6.0 ([doi:10.5281/zenodo.23428850](https://doi.org/10.5281/zenodo.23428850)).
Commit `421ba13` predates v1.6.0, but every function and constant the benchmark uses (the 37 ranking and
de-duplication functions and settings listed in `bench/extract.mjs`) is byte-identical in allmeta v1.6.0
and v1.6.1. It contains:
- the 19 labelled review datasets and a de-duplication dataset
- a harness that runs the app's own JavaScript unchanged
- the ASReview 2.2 comparator (Naive Bayes and its current SVM default)
- the analysis that regenerates the benchmark tables, figures and statistics, and checks each number against reference values
- the per-seed results of the canonical runs (`canonical/`), so every table and figure can be rebuilt in a minute without re-running anything

## Two protocols: v1.0.0 (the paper) and v1.0.1 (corrected default)

An audit of the archive (18 October 2026) found that the simulation behind the paper's numbers differs in
two places from what the paper describes and from what a reviewer using the app experiences. Both are now
explicit, selectable protocols. **v1.0.0 still reproduces every benchmark number printed in the paper**;
v1.0.1 is the default.

| | v1.0.0 (paper) | v1.0.1 (default) |
|---|---|---|
| Start set | 20 random records. If none is relevant, the **first relevant record in file order** is added, the same record for every seed. On sparse datasets most seeds therefore share one forced record, and the seed-to-seed SD understates how much the result depends on the starting record. | Same 20 random records. If a class is missing, the record added is the first record of that class in the **seed's own random permutation**: a uniformly random draw made with the seed's RNG. |
| Training gate | Ranking starts once 1 relevant + 2 irrelevant records are labelled (the simulation's own gate). | Ranking starts once **2 relevant + 2 irrelevant** records are labelled: the gate of the app's *Train & rank* button (`mlTrainOn`: "Label at least 2 includes and 2 excludes"). Until then the simulated reviewer screens records in the seed's random order. |
| Screen code | the shipped `simulateActiveLearning`, called verbatim | `bench/protocol.mjs`: the shipped vocabulary, fit, scoring and metric functions; only the two rules above differ |
| ASReview seeds | 3 (42, 7, 2024) | Screen's 10 seed values (101, 202, …, 1010), so both tools have the same replication and an SD |
| Reference values | `expected/paper_values.json`: parsed from the paper text, at the printed decimals | `expected/v1.0.1/`: regression pins from the canonical run (see below) |

The gate matters most on sparse datasets: under v1.0.1 a start set with only one relevant record keeps
the reviewer screening in random order until a second relevant record turns up, which is what a real user
of the app has to do. `node bench/test_protocol.mjs` checks, before any v1.0.1 number is trusted, that
(1) the v1.0.1 driver run with the v1.0.0 rules reproduces the shipped `simulateActiveLearning` exactly
(every curve point, compared with `===`), (2) the app's own `mlTrainOn` refuses 1+2 and accepts 2+2,
(3) on a planted corpus whose relevant records sit at the end of the file, v1.0.0 forces the same record
for every seed and v1.0.1 does not, and (4) under v1.0.1 no ranked round happens before the gate.
`reproduce.py` runs this self-test first and stops if it fails.

Sensitivity overrides for the v1.0.1 driver (not used by `reproduce.py`): `node bench/run_screen.mjs ...
--start-draw file|rng --gate P,N --unranked file|rng`.

## Reproduce in one click

There are three ways in, from no effort to a full independent re-run.

**1. See the latest verified runs (nothing to run).**

The [results page](https://mahmood726-cyber.github.io/screen-reproducible/) is published by CI. It has two parts:
- **Latest full run:** every number of the protocol the run used (v1.0.0 = every benchmark number printed in the paper).
- **Latest quick run:** run on every push, under both protocols.

Each shows the PASS/FAIL table, the result on each platform, and, for full runs on all platforms, the bit-identity check.

**2. Open in GitHub Codespaces (one click).**

Click the *Open in GitHub Codespaces* badge above, then *Create codespace*.
- The pinned environment is built from this repository's `Dockerfile`: Python 3.13.13, Node 24.15.0 and the pinned packages, including ASReview 2.2.
- The datasets are then fetched and checked, and the quick reproduction runs automatically under both protocols. Its log ends with `QUICK RUN: ALL PASS`, and the reports are in `outputs/v1.0.0/quick/` and `outputs/v1.0.1/quick/`.
- For a full run, type `python reproduce.py --protocol v1.0.0` (the paper's numbers) or `python reproduce.py` (v1.0.1) in the terminal. It writes `outputs/<protocol>/full/`.

Limits:
- You need to be signed in to GitHub.
- The codespace runs on your own Codespaces allowance. Personal accounts get a free monthly quota of core-hours and storage (see GitHub's billing page); this configuration requests a 4-core machine, so it uses that quota twice as fast as a 2-core one.
- The first build takes a few minutes.
- `codespaces-check` in Actions builds the same devcontainer and runs its automatic quick run on every relevant change.

**3. Re-run the CI yourself (one click in a fork).**

Only maintainers can trigger workflows on this repository, so use your own copy:
1. Click **Fork**.
2. In your fork, open the **Actions** tab and click *I understand my workflows, go ahead and enable them*. GitHub disables workflows in new forks.
3. Choose **reproduce**, then **Run workflow**, with mode **full**, the protocol (**v1.0.0** for the paper's numbers) and platforms **all** or **docker**.

With platforms **all** that runs the full benchmark on Docker, Linux, Windows and macOS in parallel, followed by the bit-identity check; **docker** runs the canonical Docker run only. Actions are free on public repositories.
- Each job's **summary** shows its PASS/FAIL report.
- **Artifacts** hold `reproduction-report-full-<platform>` and the complete outputs.
- Mode **quick** is the short smoke run (both protocols).
- Publishing to Pages happens only on this repository's main branch, so it is skipped in forks.

**On your own machine:**

```bash
git clone https://github.com/mahmood726-cyber/screen-reproducible && cd screen-reproducible
python -m pip install -r requirements.txt
python reproduce.py --quick --protocol v1.0.0   # smoke run, the paper's protocol
python reproduce.py --quick                     # smoke run, protocol v1.0.1
python reproduce.py --protocol v1.0.0           # full run: every benchmark number printed in the paper
python reproduce.py                             # full run, protocol v1.0.1
python reproduce.py --protocol v1.0.0 --from-canonical   # no run: rebuild everything from the archived per-seed results
```

You need Python 3.13 and Node.js 24.15.0 on your PATH. Alternatively, use Docker:

```bash
docker build -t screen-reproducible . && docker run --rm screen-reproducible --full --protocol v1.0.0
```

`make quick` and `make reproduce` run the two default (v1.0.1) commands.

**Using the app:** open `app/screen/index.html` in a browser (double-clicking the file works), or run `python -m http.server 8080` and go to http://localhost:8080.

## What `reproduce.py` does

1. Checks that the Node and Python package versions match the pins and refuses to run if they differ (`--allow-version-mismatch` overrides).
2. Downloads the 15 Cohen 2006 datasets from a pinned commit and checks all 20 data files by SHA-256 (see [data/README.md](data/README.md) for why those 15 are downloaded rather than included).
3. Runs the protocol self-test (`bench/test_protocol.mjs`, above).
4. Runs, in parallel with one process per dataset:
   - **Screen**: `bench/run_screen.mjs --protocol <p>`. The ranking functions are copied verbatim from `app/screen/index.html` into a Node `vm` with no browser, then simulated with per-record active learning over 10 seeds. Each seed's WSS@95, recall at 10/20/50%, a recall curve on a 1% grid, the buscar stop point and the start-set diagnostics (relevant records in the start set, the forced record) are stored.
   - **ASReview 2.2**: `bench/run_asreview.py`. Runs ELAS u3 (Naive Bayes) and ELAS u4 (SVM, ASReview's current default) with ASReview's own code, over 3 seeds (v1.0.0) or 10 seeds (v1.0.1), and stores per-seed values and the SD.
   - **De-duplication**: `bench/run_dedup.mjs`. Runs the app's own de-duplication code on author-labelled duplicates, reformatted duplicates, blocked versus exhaustive comparison, and synthetic corpora of up to 100,000 records, and records the machine it ran on.
5. Builds the outputs (`analysis/make_outputs.py`), prints *expected vs reproduced* with PASS/FAIL for every number, and exits non-zero if any number fails. A run with no reference file fails closed (exit 3: nothing was checked).

## Expected run times

| Mode | What runs | 4-core laptop (Windows) | GitHub Actions `ubuntu-latest` |
|---|---|---|---|
| `--quick` | 4 small datasets, 1 seed per tool, de-dup up to 2,000 records | ~30 s on an idle machine | ~30 s |
| full, v1.0.0 | 19 datasets; Screen 10 seeds; ASReview NB + SVM 3 seeds; de-dup up to 100,000 records | ~40–80 min | ~20–35 min |
| full, v1.0.1 | as v1.0.0, but ASReview on 10 seeds | roughly 3× the ASReview share of v1.0.0 | see `canonical/v1.0.1/full/PROVENANCE.json` |
| `--from-canonical` | no benchmark; tables, figures and checks from `canonical/` | ~1 min | ~1 min |

The full run is CPU-bound and uses every core by default (`--jobs N` to change this). Most of the
time is spent in ASReview's SVM on the three largest datasets. On a busy machine everything is slower:
the quick run took 8–13 minutes on a heavily loaded 4-core i5-6400.

## Outputs and how they map to the paper

Everything is written to `outputs/<protocol>/full/` (or `.../quick/`, or `.../full-canonical/`). File names follow the paper's figure numbers:

| File | Paper |
|---|---|
| `docs/screenshots/step1.png` … `step6.png` | Figures 1–6: the six steps of a screening session (see docs/screenshots/README.md) |
| `table1_wss95.md` / `.csv` | Table 1: WSS@95 per dataset, mean (SD) for Screen and for both ASReview configurations |
| `table2_dedup.md` / `.csv` | Table 2: de-duplication results (unordered pair scoring, with the v1.0.0 directed-ID figure beside it) |
| `figure7_wss95_by_dataset.png` | Figure 7: WSS@95 by dataset, three tools; error bars = Screen's SD across seeds (and ASReview's SD when it has the same number of seeds, i.e. under v1.0.1) |
| `figure8_paired_differences.png` | Figure 8: paired per-dataset differences, with Wilcoxon p |
| `figure9_recall_vs_screened.png` / `.csv` | Figure 9: recall against proportion screened: the mean over datasets at 10%, 20% and 50% (the three numbers in the text), with the full mean curve when the run stored per-seed curves, against random order |
| `supplementary_s1_dedup_scaling.png` | not a paper figure: de-duplication workload, blocked vs all pairs |
| `visual_abstract.png` | Visual abstract |
| `stats.json` | All statistics quoted in the text, plus start-set diagnostics |
| `machine.json` | The machine that ran the benchmark (CPU, cores, OS, Node), its de-duplication timings and total wall time |
| `reproduction_report.md` / `.json` | Expected vs reproduced, PASS/FAIL per number, with the place each number is printed in the paper, and the printed numbers that cannot be checked here and why |

(Before this version the analysis figures were numbered 2–4 in this repository. They are now numbered as in the paper.)

## Reference values

- `expected/paper_values.json` (protocol v1.0.0): an exact extraction of the numbers printed in the paper,
  parsed from the manuscript text by a script, each at its printed number of decimals and with the place it
  is printed (Abstract, Results, Table 1 row, Table 2). 176 printed numbers are checked (including the
  Table 1 SDs, record counts and prevalences, which earlier versions did not check), plus 5 canonical
  v1.0.0 values that are not printed (marked `printed: false`). Six printed numbers cannot be regenerated
  here and are listed with the reason in the report: the 100,000-record de-duplication time (6.6 s in the
  paper, machine-dependent; the canonical Docker run took 19.2 s, the Linux, Windows and macOS CI runs 11.9,
  12.9 and 16.2 s, so the printed 6.6 s does not come from any archived run and should be reported with its
  machine or as approximate); the 36 unit and 49 browser tests (allmeta's suites, not this archive's); and
  the illustrative screenshot values (κ = 0.836, AUC 0.91, 312 records, 17 duplicates).
  `python reproduce.py --protocol v1.0.0 --from-canonical` checks all 181 against the archived canonical results: 181/181 pass.
- `expected/quick_values.json` (v1.0.0 quick): computed independently with allmeta's original benchmark scripts.
- `expected/v1.0.1/quick_values.json` and `full_values.json`: **regression pins**. They were written from one
  run (recorded in the file) and detect any change; they are not an independent check. The independent
  evidence is that the CI quick runs on Linux, Windows, macOS and Docker reproduce the quick pin exactly, and
  that `bench/test_protocol.mjs` ties the v1.0.1 driver to the shipped simulation.

## Per-seed outputs (Extended data)

`canonical/<protocol>/<mode>/results/` holds the per-seed result files of the canonical run of each
protocol (Screen and ASReview per-seed WSS@95, recall, stop points, start-set diagnostics, de-duplication
detail and the job logs), with `SHA256SUMS` and `PROVENANCE.json` (CI run, job, platform, commit). They are
committed, so they are part of every Zenodo release made from this repository. The v1.0.0 Zenodo record
(doi:10.5281/zenodo.23132680) did not contain them: `results/` and `outputs/` were git-ignored.

- `canonical/v1.0.0/full/`: the canonical Docker run behind the paper's numbers (CI run 37199331989, 4 October 2026).
- `canonical/v1.0.1/full/`: the canonical Docker run of protocol v1.0.1.

A maintainer archives a new canonical run with `python ci/package_canonical.py --results <dir> --protocol <p> --mode full --provenance "<CI run, job, commit>"`.

## Determinism

Results are bit-identical across machines (checked by `analysis/compare_runs.py`, which compares
every per-seed value with `==`). Three things make that true:
- **Screen** ranks with JavaScript's stable `Array.prototype.sort` and seeded PRNGs, and Node is pinned to 24.15.0.
- **ASReview's SVM** (scikit-learn `LinearSVC`, `random_state=None`) takes its random seed from NumPy's global generator. `bench/run_asreview.py` therefore calls `np.random.seed(seed)` before every simulation. Without this the result depended on what had run earlier in the process: on Opiods, WSS@95 ranged from 0.269 to 0.277.
- **ASReview ranks** with `np.argsort(-p)`, NumPy's unstable sort, which NumPy 2.x dispatches to CPU-specific SIMD code. Records with exactly tied probabilities were therefore ordered differently on different CPUs. The harness uses `StableMax`, which is the same query strategy with `kind="stable"` (ties broken by record order). This changes ASReview's results only where probabilities tie exactly.

BLAS/OpenMP are also limited to one thread, and `PYTHONHASHSEED=0` is set.

## Notes on the benchmark

- Screen's default settings were tuned on these same 19 datasets, using different seeds. Expect lower work savings on new reviews.
- The benchmark retrains after every decision. In the app, retraining happens when the user selects **Train & rank**.
- Start sets differ between the tools: Screen starts from 20 random records (with the forced-record rule of the protocol, above), ASReview from one randomly drawn relevant and one randomly drawn irrelevant record. Both count these starting records as screened.
- "Relevant" is the dataset's final inclusion label (`label_included`), not title–abstract eligibility.
- **De-duplication scoring.** The app keeps the earlier record of a duplicate pair and flags the later one, while a gold label may sit on either member. The v1.0.0 harness scored "is the labelled record flagged?" (directed record IDs), which counts a correctly found pair as a miss whenever the label sits on the earlier record: that is the "7 of 11" in the paper. The harness now scores unordered pairs (both members in the same duplicate cluster): **11 of 11** author-labelled Nagtegaal pairs are found, and the app makes **6 further links** that the source does not label (their titles are listed in `dedup.json` for adjudication; some look like real unlabelled duplicates). The directed figures (7/11, 10 further flags) are still computed and are what protocol v1.0.0 checks.
- The Nagtegaal file has titles and abstracts only, so the de-duplication rule that uses first author and year, and the DOI pass, cannot fire there. The blocked-vs-exhaustive check uses titles only and the strict threshold.
- The harness fixes a bug in allmeta's `benchmark/run_headless.mjs`: `ML_NGRAM_MAX`, `ML_DF_MAX_FRAC` and `dec` were missing from its extraction lists, so it crashed against the current app. The fix is in `bench/extract.mjs`; it is documented here, not in the paper.

## How to cite

Please cite:
- the article (reference to be added on publication);
- this repository, v1.0.0, doi:[10.5281/zenodo.23132680](https://doi.org/10.5281/zenodo.23132680) (see `CITATION.cff`; a v1.0.1 release with the changes above has not been made yet);
- allmeta v1.6.0, doi:[10.5281/zenodo.23428850](https://doi.org/10.5281/zenodo.23428850) (all versions: [10.5281/zenodo.20516880](https://doi.org/10.5281/zenodo.20516880));
- the original dataset authors listed in [data/README.md](data/README.md).

Releases are archived on Zenodo through the GitHub–Zenodo integration (metadata in `.zenodo.json`).

## Licence

MIT (see `LICENSE`), the same as allmeta. The data keep their own licences (see `data/README.md`).
