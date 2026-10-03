"""ASReview comparator, run with ASReview's own code (asreview 2.2).

Two configurations, built exactly from asreview.models:
  nb  = ELAS u3: NaiveBayes(alpha=3.822), Balanced(ratio=1.2), Tfidf(stop_words="english"), Max querier, n_query=1
  svm = ELAS u4 (ASReview's current default): SVM(squared_hinge, C=0.11), Balanced(ratio=9.8),
        Tfidf(ngram_range=(1,2), sublinear_tf=True, min_df=1, max_df=0.95), Max querier, n_query=1
Each seed draws 1 relevant + 1 irrelevant prior; priors count as screened.

Determinism: ASReview's SVM is sklearn LinearSVC with random_state=None, so liblinear's
coordinate-descent shuffle is seeded from NumPy's GLOBAL random generator. Without
intervention the SVM result therefore depends on whatever ran earlier in the process
(on Cohen Opiods, WSS@95 moved between 0.269 and 0.277 just by changing the global seed).
We reset the global generator with np.random.seed(seed) immediately before every
simulation, so each (dataset, model, seed) result is independent of run order, process
layout and platform. ASReview's own model settings are not changed.
WSS@95 = 0.95 - (records screened to reach 95% recall)/N, the same definition as Screen's harness.

  python bench/run_asreview.py --dataset cohen_adhd --models nb,svm --seeds 42,7,2024 --out results/asreview/cohen_adhd.json
(Adapted from allmeta benchmark/_embed/asreview_groundtruth.py; logic unchanged.)
"""
import argparse
import gzip
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from asreview.learner import ActiveLearningCycle
from asreview.models.balancers import Balanced
from asreview.models.classifiers import SVM, NaiveBayes
from asreview.models.feature_extractors import Tfidf
from asreview.models.queriers import Max
from asreview.simulation.simulate import Simulate
from sklearn.utils import check_random_state

ROOT = Path(__file__).resolve().parent.parent


def cycle(model):
    if model == "nb":
        return ActiveLearningCycle(querier=Max(), classifier=NaiveBayes(alpha=3.822), balancer=Balanced(ratio=1.2),
                                   feature_extractor=Tfidf(stop_words="english"), n_query=1)
    if model == "svm":
        return ActiveLearningCycle(querier=Max(), classifier=SVM(loss="squared_hinge", C=0.11), balancer=Balanced(ratio=9.8),
                                   feature_extractor=Tfidf(ngram_range=(1, 2), sublinear_tf=True, min_df=1, max_df=0.95), n_query=1)
    raise ValueError(model)


def load(idn):
    with gzip.open(ROOT / "data" / "corpora" / f"{idn}.csv.gz", "rt", encoding="utf-8") as f:
        df = pd.read_csv(f)
    df["title"] = df.get("title", "").fillna("")
    df["abstract"] = df.get("abstract", "").fillna("")
    y = (df["label_included"].astype(str).str.strip() == "1").astype(int).values
    return df[["title", "abstract"]], y


def wss95(labels_in_order, n, total_pos):
    found = 0
    for i, lab in enumerate(labels_in_order, start=1):
        found += int(lab)
        if found >= np.ceil(0.95 * total_pos):
            return 0.95 - i / n
    return 0.95 - 1.0


def run(idn, model, seeds):
    X, y = load(idn)
    n, p = len(y), int(y.sum())
    vals = []
    for s in seeds:
        np.random.seed(s)  # pins LinearSVC's liblinear shuffle (random_state=None -> global RNG)
        r = check_random_state(s)
        inc, exc = np.where(y == 1)[0], np.where(y == 0)[0]
        priors = np.concatenate([r.choice(inc, 1, replace=False), r.choice(exc, 1, replace=False)])
        sim = Simulate(X, y, cycle(model), print_progress=False)
        sim.label(priors)
        sim.review()
        order = sim._results.sort_values("training_set", na_position="first")
        vals.append(float(wss95(list(order["label"].values), n, p)))
    return n, p, vals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--models", default="nb,svm")
    ap.add_argument("--seeds", default="42,7,2024")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    import asreview
    seeds = [int(s) for s in a.seeds.split(",")]
    res = {"tool": "asreview", "asreview": asreview.__version__, "seeds": seeds, "perDataset": {}}
    for idn in a.dataset.split(","):
        row = {}
        for m in a.models.split(","):
            t0 = time.time()
            n, p, vals = run(idn, m, seeds)
            row.update({"N": n, "relevant": p, f"{m}_wss95_per_seed": vals, f"{m}_wss95": float(np.mean(vals)), f"{m}_seconds": time.time() - t0})
            print(f"[asreview] {idn:30s} {m:3s} WSS@95 {np.mean(vals):.4f} ({len(seeds)} seeds, {time.time() - t0:.0f} s)", flush=True)
        res["perDataset"][idn] = row
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
