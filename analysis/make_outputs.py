"""Build every table, figure and statistic in the paper from the raw run outputs,
then compare each reported number with the value printed in the paper (or, in quick
mode, with the stored quick-mode reference) and print PASS/FAIL per number.

  python analysis/make_outputs.py --results results/full --outputs outputs/full --expected expected/paper_values.json
Exit code 0 only if every checked number passes.
"""
import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon

ROOT = Path(__file__).resolve().parent.parent


def load_dir(d):
    merged = {}
    for f in sorted(Path(d).glob("*.json")):
        merged.update(json.loads(f.read_text())["perDataset"])
    return merged


def stats(results_dir):
    man = json.loads((ROOT / "data" / "corpora" / "manifest.json").read_text(encoding="utf-8"))
    sc = load_dir(Path(results_dir) / "screen")
    asr = load_dir(Path(results_dir) / "asreview")
    order = [d["id"] for d in man["datasets"] if d["id"] in sc]
    label = {d["id"]: d["label"] for d in man["datasets"]}
    rows = []
    for d in order:
        s, a = sc[d], asr.get(d, {})
        rows.append({
            "dataset_id": d, "dataset": label[d], "suite": s["suite"], "records": s["N"], "relevant": s["relevant"],
            "prevalence_pct": 100 * s["prevalence"], "screen_wss95_mean": s["WSS_at_95"], "screen_wss95_sd": s["WSS_at_95_sd"],
            "asreview_nb_wss95": a.get("nb_wss95"), "asreview_svm_wss95": a.get("svm_wss95"),
            "screen_recall_at_10pct": s["recall_at_10pct"], "screen_recall_at_20pct": s["recall_at_20pct"],
            "screen_recall_at_50pct": s["recall_at_50pct"],
            "buscar_never_fired": all(x == s["N"] for x in s["buscar_stop_at_per_seed"]),
        })
    w = np.array([r["screen_wss95_mean"] for r in rows])
    st = {"n_datasets": len(rows), "screen_mean_all": w.mean(), "screen_median_all": float(np.median(w)),
          "screen_min": w.min(), "screen_max": w.max(),
          "screen_mean_cohen": float(np.mean([r["screen_wss95_mean"] for r in rows if r["suite"] == "Cohen 2006"] or [np.nan])),
          "screen_mean_synergy": float(np.mean([r["screen_wss95_mean"] for r in rows if r["suite"] != "Cohen 2006"] or [np.nan])),
          "recall_at_10pct_pct": 100 * np.mean([r["screen_recall_at_10pct"] for r in rows]),
          "recall_at_20pct_pct": 100 * np.mean([r["screen_recall_at_20pct"] for r in rows]),
          "recall_at_50pct_pct": 100 * np.mean([r["screen_recall_at_50pct"] for r in rows]),
          "buscar_never_fired": int(sum(r["buscar_never_fired"] for r in rows))}
    for m in ("nb", "svm"):
        b = np.array([r[f"asreview_{m}_wss95"] for r in rows], dtype=float)
        if np.isnan(b).any():
            continue
        dl = w - b
        st[f"asreview_{m}_mean"] = b.mean()
        st[f"wins_vs_{m}"] = int((dl > 0).sum())
        st[f"mean_diff_vs_{m}"] = dl.mean()
        st[f"median_diff_vs_{m}"] = float(np.median(dl))
        if len(rows) >= 6:
            t = wilcoxon(w, b)
            st[f"wilcoxon_W_vs_{m}"] = float(t.statistic)
            st[f"wilcoxon_p_vs_{m}"] = float(t.pvalue)
    return rows, {k: float(v) if isinstance(v, (np.floating, float)) else v for k, v in st.items()}


def write_table(path_base, header, rows):
    with open(f"{path_base}.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(header)
        wr.writerows(rows)
    md = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    md += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    Path(f"{path_base}.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def f3(x):
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.3f}"


def figures(rows, st, dedup, outdir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "svg.hashsalt": "screen-reproducible"})
    meta = {"Software": None}
    C = {"screen": "#1b6ca8", "nb": "#d1802a", "svm": "#7a4f9e"}
    rs = sorted(rows, key=lambda r: r["screen_wss95_mean"])
    names = [r["dataset"].replace("Cohen ", "") for r in rs]
    y = np.arange(len(rs))

    # Figure 1 — per-dataset WSS@95, three tools
    fig, ax = plt.subplots(figsize=(7, 0.32 * len(rs) + 1.4))
    for key, col, lab, off in (("screen_wss95_mean", C["screen"], "Screen (10 seeds)", 0),
                               ("asreview_nb_wss95", C["nb"], "ASReview NB (3 seeds)", 0.18),
                               ("asreview_svm_wss95", C["svm"], "ASReview SVM, default (3 seeds)", -0.18)):
        vals = [r[key] for r in rs]
        if any(v is None for v in vals):
            continue
        ax.scatter(vals, y + off, s=22, color=col, label=lab, zorder=3)
    ax.axvline(0, color="#888", lw=0.8, ls="--")
    ax.set_yticks(y, names)
    ax.set_xlabel("WSS@95 (0 = no better than random screening order)")
    ax.set_title("Figure 1. Work saved at 95% recall, by dataset")
    ax.grid(axis="x", color="#ddd", lw=0.6)
    ax.legend(loc="lower right", frameon=False)
    fig.tight_layout()
    fig.savefig(outdir / "figure1_wss95_by_dataset.png", dpi=200, metadata=meta)
    plt.close(fig)

    # Figure 2 — paired differences
    have = [m for m in ("nb", "svm") if f"asreview_{m}_mean" in st]
    fig, axes = plt.subplots(1, max(1, len(have)), figsize=(3.6 * max(1, len(have)) + 1, 0.3 * len(rs) + 1.6), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, m in zip(axes, have):
        d = [r["screen_wss95_mean"] - r[f"asreview_{m}_wss95"] for r in rs]
        ax.barh(y, d, color=[C["screen"] if v > 0 else C[m] for v in d])
        ax.axvline(0, color="#333", lw=0.8)
        ax.axvline(np.mean(d), color="#333", lw=0.8, ls=":")
        p = st.get(f"wilcoxon_p_vs_{m}")
        ax.set_title(f"Screen − ASReview {m.upper()}\nmean {np.mean(d):+.3f}" + (f", Wilcoxon p = {p:.3f}" if p is not None else ""), fontsize=9)
        ax.set_xlabel("Difference in WSS@95")
        ax.grid(axis="x", color="#ddd", lw=0.6)
    axes[0].set_yticks(y, names)
    fig.suptitle("Figure 2. Paired per-dataset differences (positive = Screen better)", fontsize=10)
    fig.tight_layout()
    fig.savefig(outdir / "figure2_paired_differences.png", dpi=200, metadata=meta)
    plt.close(fig)

    # Figure 3 — de-duplication scaling (deterministic comparison counts)
    sc = dedup["scaling"]
    n = np.array([s["n"] for s in sc], dtype=float)
    fig, ax = plt.subplots(figsize=(5.2, 3.6))
    ax.loglog(n, [s["all_pairs"] for s in sc], "o--", color="#999", label="All pairs, n(n−1)/2 (exhaustive pass)")
    ax.loglog(n, [s["blocked_comparisons"] for s in sc], "o-", color=C["screen"], label="Blocked pass (shipped)")
    for s in sc:
        ax.annotate(f"{s['blocked_comparisons']:,}", (s["n"], s["blocked_comparisons"]), textcoords="offset points", xytext=(4, -10), fontsize=7)
    ax.set_xlabel("Records")
    ax.set_ylabel("Title-pair comparisons")
    ax.set_title("Figure 3. De-duplication workload on synthetic corpora", fontsize=10)
    ax.grid(which="both", color="#eee", lw=0.5)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(outdir / "figure3_dedup_scaling.png", dpi=200, metadata=meta)
    plt.close(fig)

    # Visual abstract
    fig = plt.figure(figsize=(10, 5.2))
    fig.text(0.02, 0.94, "Screen: offline, browser-only title–abstract screening", fontsize=15, weight="bold")
    fig.text(0.02, 0.885, "No install · no account · no upload. Naive Bayes active learning, dual review with Cohen's κ, de-duplication, PRISMA counts.",
             fontsize=9.5, color="#333")
    ax = fig.add_axes([0.06, 0.12, 0.4, 0.62])
    tools = [("Screen", st["screen_mean_all"], C["screen"])]
    if "asreview_nb_mean" in st:
        tools.append(("ASReview NB", st["asreview_nb_mean"], C["nb"]))
    if "asreview_svm_mean" in st:
        tools.append(("ASReview SVM\n(default)", st["asreview_svm_mean"], C["svm"]))
    ax.bar([t[0] for t in tools], [t[1] for t in tools], color=[t[2] for t in tools])
    for i, t in enumerate(tools):
        ax.text(i, t[1] + 0.01, f"{t[1]:.3f}", ha="center", fontsize=10)
    ax.set_ylim(0, max(t[1] for t in tools) * 1.25)
    ax.set_ylabel(f"Mean WSS@95 across {st['n_datasets']} datasets")
    ax.spines[["top", "right"]].set_visible(False)
    lines = [f"Benchmark: {st['n_datasets']} public labelled review datasets",
             "(15 Cohen 2006 + 4 SYNERGY), shipped code run unchanged."]
    if "wins_vs_nb" in st:
        lines += ["", f"vs ASReview NB: Screen better on {st['wins_vs_nb']}/{st['n_datasets']}",
                  f"   mean Δ {st['mean_diff_vs_nb']:+.3f}, Wilcoxon p = {st.get('wilcoxon_p_vs_nb', float('nan')):.2f}  (no difference)"]
    if "wins_vs_svm" in st:
        lines += [f"vs ASReview SVM: Screen better on {st['wins_vs_svm']}/{st['n_datasets']}",
                  f"   mean Δ {st['mean_diff_vs_svm']:+.3f}, Wilcoxon p = {st.get('wilcoxon_p_vs_svm', float('nan')):.3f}  (ASReview slightly better)"]
    r = dedup["reformatted"]
    lines += ["", f"De-duplication: {r['detected']}/{r['injected']} reformatted duplicates found",
              f"   (precision {r['precision']:.3f}); {dedup['nagtegaal']['detected']}/{dedup['nagtegaal']['gold_duplicates']} author-labelled.",
              "", "Settings were tuned on these datasets: expect lower", "performance on new reviews."]
    fig.text(0.53, 0.72, "\n".join(lines), fontsize=9.5, va="top", family="DejaVu Sans")
    fig.savefig(outdir / "visual_abstract.png", dpi=200, metadata=meta)
    plt.close(fig)


def compare(st, rows, dedup, expected_path):
    exp = json.loads(Path(expected_path).read_text())
    got = dict(st)
    for r in rows:
        got[f"screen_wss95[{r['dataset_id']}]"] = r["screen_wss95_mean"]
        if r["asreview_nb_wss95"] is not None:
            got[f"asreview_nb_wss95[{r['dataset_id']}]"] = r["asreview_nb_wss95"]
        if r["asreview_svm_wss95"] is not None:
            got[f"asreview_svm_wss95[{r['dataset_id']}]"] = r["asreview_svm_wss95"]
    for k in ("detected", "gold_duplicates", "flagged_not_in_gold"):
        got[f"dedup_nagtegaal_{k}"] = dedup["nagtegaal"][k]
    for k in ("detected", "false_positives", "total_flagged", "precision", "recall", "f1"):
        got[f"dedup_reformatted_{k}"] = dedup["reformatted"][k]
    for k in ("blocked", "brute", "brute_only"):
        got[f"dedup_blocked_vs_brute_{k}"] = dedup["blocked_vs_brute"][k]
    for s in dedup["scaling"]:
        got[f"dedup_blocked_comparisons[n={s['n']}]"] = s["blocked_comparisons"]
    out = []
    for key, spec in exp["values"].items():
        v, dp = spec["value"], spec["decimals"]
        g = got.get(key)
        ok = g is not None and round(float(g), dp) == round(float(v), dp)
        out.append({"quantity": key, "expected": v, "reproduced": None if g is None else (int(round(float(g))) if dp == 0 else round(float(g), dp + 2)), "decimals": dp, "result": "PASS" if ok else "FAIL"})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--outputs", required=True)
    ap.add_argument("--expected", required=True)
    a = ap.parse_args()
    outdir = Path(a.outputs)
    outdir.mkdir(parents=True, exist_ok=True)
    rows, st = stats(a.results)
    dedup = json.loads((Path(a.results) / "dedup.json").read_text())

    write_table(outdir / "table1_wss95", ["Dataset", "Records", "Relevant (%)", "Screen WSS@95 mean (SD)", "ASReview NB", "ASReview SVM"],
                [[r["dataset"], f"{r['records']:,}", f"{r['relevant']} ({r['prevalence_pct']:.1f})",
                  f"{r['screen_wss95_mean']:.3f} ({r['screen_wss95_sd']:.3f})", f3(r["asreview_nb_wss95"]), f3(r["asreview_svm_wss95"])] for r in rows]
                + [["Mean", "", "", f"{st['screen_mean_all']:.3f}", f3(st.get("asreview_nb_mean")), f3(st.get("asreview_svm_mean"))]])
    n_, r_, b_ = dedup["nagtegaal"], dedup["reformatted"], dedup["blocked_vs_brute"]
    t2 = [["Author-labelled duplicates (Nagtegaal 2019)", f"{n_['records']:,} records, {n_['gold_duplicates']} labelled duplicates",
           f"{n_['detected']}/{n_['gold_duplicates']} detected (recall {n_['recall']:.2f}); {n_['flagged_not_in_gold']} further records flagged"],
          ["Reformatted duplicates (Cohen ACE, DOI removed, title mangled)", f"{r_['originals']:,} originals + {r_['injected']} duplicates",
           f"{r_['detected']}/{r_['injected']} detected (recall {r_['recall']:.3f}); {r_['false_positives']} false positives of {r_['total_flagged']} flagged (precision {r_['precision']:.3f}; F1 {r_['f1']:.3f})"],
          ["Blocked vs exhaustive pass (Nagtegaal subset)", f"{b_['records']:,} records",
           f"blocked {b_['blocked']}, exhaustive {b_['brute']}, missed by blocking {b_['brute_only']}"]]
    for s in dedup["scaling"]:
        t2.append([f"Scaling, synthetic corpus", f"{s['n']:,} records",
                   f"{s['blocked_comparisons']:,} blocked comparisons vs {s['all_pairs']:,.0f} all pairs; {s['blocked_ms']:,} ms blocked" +
                   (f", {s['brute_ms']:,} ms exhaustive" if s["brute_ms"] is not None else "") + " (times are machine-dependent)"])
    write_table(outdir / "table2_dedup", ["Test", "Input", "Result"], t2)
    figures(rows, st, dedup, outdir)
    (outdir / "stats.json").write_text(json.dumps(st, indent=1))

    report = compare(st, rows, dedup, a.expected)
    npass = sum(r["result"] == "PASS" for r in report)
    lines = ["| Quantity | Expected | Reproduced | Result |", "|---|--:|--:|---|"]
    lines += [f"| {r['quantity']} | {r['expected']} | {r['reproduced']} | {r['result']} |" for r in report]
    summary = f"{npass}/{len(report)} numbers reproduced"
    (outdir / "reproduction_report.md").write_text(f"# Reproduction report\n\n{summary}\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
    (outdir / "reproduction_report.json").write_text(json.dumps({"summary": summary, "checks": report}, indent=1))
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(outdir.glob("*.csv"))}
    (outdir / "SHA256SUMS.tables").write_text("".join(f"{h}  {n}\n" for n, h in hashes.items()))

    width = max(len(r["quantity"]) for r in report)
    print(f"\n{'quantity'.ljust(width)}  {'expected':>10}  {'reproduced':>12}  result")
    for r in report:
        print(f"{r['quantity'].ljust(width)}  {str(r['expected']):>10}  {str(r['reproduced']):>12}  {r['result']}")
    print(f"\n{summary}: {'ALL PASS' if npass == len(report) else 'FAILURES PRESENT'}")
    print(f"outputs written to {outdir}")
    sys.exit(0 if npass == len(report) else 1)


if __name__ == "__main__":
    main()
