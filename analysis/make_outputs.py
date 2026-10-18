"""Build every table, figure and statistic in the paper from the raw run outputs,
then compare each reported number with the value printed in the paper (or, in quick
mode, with the stored quick-mode reference) and print PASS/FAIL per number.

  python analysis/make_outputs.py --results results/v1.0.0/full --outputs outputs/v1.0.0/full \
      --expected expected/paper_values.json --protocol v1.0.0
Exit code 0 only if every checked number passes.

Figure files are numbered as in the paper: Figures 1-6 are the screenshots in docs/screenshots/,
figure7 = WSS@95 by dataset, figure8 = paired differences, figure9 = recall vs proportion screened.
The de-duplication scaling plot is not a paper figure (supplementary_s1_dedup_scaling.png).
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


def sd_of(v):
    return float(np.std(v, ddof=1)) if v and len(v) > 1 else None


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
            "asreview_nb_wss95_sd": a.get("nb_wss95_sd", sd_of(a.get("nb_wss95_per_seed"))),
            "asreview_svm_wss95_sd": a.get("svm_wss95_sd", sd_of(a.get("svm_wss95_per_seed"))),
            "asreview_seeds": len(a.get("nb_wss95_per_seed") or []),
            "screen_seeds": len(s["wss95_per_seed"]),
            "recall_curve_mean": (np.mean(np.array(s["recall_curve_per_seed"], dtype=float), axis=0).tolist()
                                  if s.get("recall_curve_per_seed") else None),
            "seeds_without_relevant_start": (sum(1 for x in s["start_set_relevant_per_seed"] if x == 0)
                                             if s.get("start_set_relevant_per_seed") else None),
            "distinct_forced_relevant": (len({x for x in s["forced_relevant_index_per_seed"] if x is not None})
                                         if s.get("forced_relevant_index_per_seed") else None),
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
          "buscar_never_fired": int(sum(r["buscar_never_fired"] for r in rows)),
          "records_min": min(r["records"] for r in rows), "records_max": max(r["records"] for r in rows),
          "prevalence_min_pct": min(r["prevalence_pct"] for r in rows), "prevalence_max_pct": max(r["prevalence_pct"] for r in rows)}
    if all(r["seeds_without_relevant_start"] is not None for r in rows):
        # datasets on which >=1 seed's start set had no relevant record, and on which every such seed got the same forced record
        st["datasets_with_forced_relevant"] = int(sum(r["seeds_without_relevant_start"] > 0 for r in rows))
        st["datasets_forced_record_shared_by_all_such_seeds"] = int(sum(r["seeds_without_relevant_start"] > 1 and r["distinct_forced_relevant"] == 1 for r in rows))
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


def f3sd(m, sd):
    if m is None or (isinstance(m, float) and np.isnan(m)):
        return "—"
    return f"{m:.3f}" if sd is None else f"{m:.3f} ({sd:.3f})"


def figures(rows, st, dedup, outdir, protocol):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "svg.hashsalt": "screen-reproducible"})
    meta = {"Software": None}
    C = {"screen": "#1b6ca8", "nb": "#d1802a", "svm": "#7a4f9e"}
    rs = sorted(rows, key=lambda r: r["screen_wss95_mean"])
    names = [r["dataset"].replace("Cohen ", "") for r in rs]
    y = np.arange(len(rs))
    ns = rs[0]["screen_seeds"] if rs else 0
    na = rs[0]["asreview_seeds"] if rs else 0
    # ASReview error bars only where both tools have the same replication (protocol v1.0.1); the paper's
    # Figure 7 (v1.0.0) shows Screen's SD only, as its caption says.
    asr_bars = na == ns and na > 1

    # Figure 7 (paper numbering) — per-dataset WSS@95, three tools, SD error bars
    fig, ax = plt.subplots(figsize=(7, 0.32 * len(rs) + 1.4))
    for key, col, lab, off, bars in (("screen_wss95", C["screen"], f"Screen (mean ± SD, {ns} seeds)", 0, ns > 1),
                                     ("asreview_nb_wss95", C["nb"], f"ASReview NB ({na} seeds)" + (", ± SD" if asr_bars else ""), 0.18, asr_bars),
                                     ("asreview_svm_wss95", C["svm"], f"ASReview SVM, default ({na} seeds)" + (", ± SD" if asr_bars else ""), -0.18, asr_bars)):
        mkey = key + "_mean" if key == "screen_wss95" else key
        vals = [r[mkey] for r in rs]
        if any(v is None for v in vals):
            continue
        sds = [r[key + "_sd"] or 0.0 for r in rs] if bars else None
        ax.errorbar(vals, y + off, xerr=sds, fmt="o", ms=4.5, color=col, ecolor=col, elinewidth=0.9, capsize=2, label=lab, zorder=3)
    ax.axvline(0, color="#888", lw=0.8, ls="--")
    ax.set_yticks(y, names)
    ax.set_xlabel("WSS@95 (0 = no better than random screening order)")
    ax.set_title(f"Figure 7. WSS@95 by dataset (protocol {protocol})", fontsize=10)
    ax.grid(axis="x", color="#ddd", lw=0.6)
    ax.legend(loc="lower right", frameon=False)
    fig.tight_layout()
    fig.savefig(outdir / "figure7_wss95_by_dataset.png", dpi=200, metadata=meta)
    plt.close(fig)

    # Figure 8 — paired differences
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
    fig.suptitle(f"Figure 8. Paired per-dataset differences (positive = Screen better; protocol {protocol})", fontsize=10)
    fig.tight_layout()
    fig.savefig(outdir / "figure8_paired_differences.png", dpi=200, metadata=meta)
    plt.close(fig)

    # Figure 9 — recall against proportion screened. Points: mean over the datasets of each dataset's mean
    # recall (over seeds) at 10%, 20% and 50% screened, exactly the three numbers in the text. When the run
    # stored per-seed recall curves (all runs from this version on) the full mean curve is drawn as well.
    curves = [r["recall_curve_mean"] for r in rows if r.get("recall_curve_mean")]
    fig, ax = plt.subplots(figsize=(5.2, 4.0))
    if curves and len(curves) == len(rows):
        grid = np.linspace(0, 1, len(curves[0]))
        cm = np.array(curves)
        mean_c = cm.mean(axis=0)
        for c in cm:
            ax.plot(100 * grid, 100 * c, color=C["screen"], lw=0.5, alpha=0.18)
        ax.plot(100 * grid, 100 * mean_c, color=C["screen"], lw=2, label=f"Screen, mean of {len(cm)} datasets ({ns} seeds each)")
        with open(outdir / "figure9_recall_vs_screened.csv", "w", newline="", encoding="utf-8") as f:
            wr = csv.writer(f)
            wr.writerow(["proportion_screened"] + [r["dataset_id"] for r in rows] + ["mean"])
            for i, g in enumerate(grid):
                wr.writerow([f"{g:.2f}"] + [f"{c[i]:.6f}" for c in cm] + [f"{mean_c[i]:.6f}"])
    else:
        with open(outdir / "figure9_recall_vs_screened.csv", "w", newline="", encoding="utf-8") as f:
            wr = csv.writer(f)
            wr.writerow(["proportion_screened"] + [r["dataset_id"] for r in rows] + ["mean"])
            for frac in (10, 20, 50):
                vals = [r[f"screen_recall_at_{frac}pct"] for r in rows]
                wr.writerow([f"{frac / 100:.2f}"] + [f"{v:.6f}" for v in vals] + [f"{np.mean(vals):.6f}"])
    pts = [(f, st[f"recall_at_{f}pct_pct"]) for f in (10, 20, 50)]
    ax.plot([p[0] for p in pts], [p[1] for p in pts], "o", color=C["screen"] if not curves else "#15181d", ms=6, zorder=4,
            label=None if curves else f"Screen, mean of {len(rows)} datasets ({ns} seeds each)")
    for frac, v in pts:
        ax.annotate(f"{v:.0f}% at {frac}%", (frac, v), textcoords="offset points", xytext=(6, -12), fontsize=8)
    ax.plot([0, 100], [0, 100], color="#888", ls="--", lw=1, label="Screening in random order (expected)")
    ax.set_xlabel("Records screened (%)")
    ax.set_ylabel("Relevant records found (%)")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 102)
    ax.set_title(f"Figure 9. Recall against proportion screened (protocol {protocol})", fontsize=10)
    ax.grid(color="#eee", lw=0.5)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(outdir / "figure9_recall_vs_screened.png", dpi=200, metadata=meta)
    plt.close(fig)

    # Supplementary Figure S1 (not a paper figure) — de-duplication scaling (deterministic comparison counts)
    sc = dedup["scaling"]
    n = np.array([s["n"] for s in sc], dtype=float)
    fig, ax = plt.subplots(figsize=(5.2, 3.6))
    ax.loglog(n, [s["all_pairs"] for s in sc], "o--", color="#999", label="All pairs, n(n−1)/2 (exhaustive pass)")
    ax.loglog(n, [s["blocked_comparisons"] for s in sc], "o-", color=C["screen"], label="Blocked pass (shipped)")
    for s in sc:
        ax.annotate(f"{s['blocked_comparisons']:,}", (s["n"], s["blocked_comparisons"]), textcoords="offset points", xytext=(4, -10), fontsize=7)
    ax.set_xlabel("Records")
    ax.set_ylabel("Title-pair comparisons")
    ax.set_title("Supplementary Figure S1. De-duplication workload on synthetic corpora", fontsize=9)
    ax.grid(which="both", color="#eee", lw=0.5)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(outdir / "supplementary_s1_dedup_scaling.png", dpi=200, metadata=meta)
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
             "(15 Cohen 2006 + 4 ASReview benchmark sets), shipped code.", f"Protocol {protocol}."]
    if "wins_vs_nb" in st:
        lines += ["", f"vs ASReview NB: Screen better on {st['wins_vs_nb']}/{st['n_datasets']}",
                  f"   mean Δ {st['mean_diff_vs_nb']:+.3f}, Wilcoxon p = {st.get('wilcoxon_p_vs_nb', float('nan')):.3f}"]
    if "wins_vs_svm" in st:
        lines += [f"vs ASReview SVM: Screen better on {st['wins_vs_svm']}/{st['n_datasets']}",
                  f"   mean Δ {st['mean_diff_vs_svm']:+.3f}, Wilcoxon p = {st.get('wilcoxon_p_vs_svm', float('nan')):.3f}"]
    r = dedup["reformatted"]
    npairs = dedup["nagtegaal"].get("pairs")
    lines += ["", f"De-duplication: {r['detected']}/{r['injected']} reformatted duplicates found",
              f"   (precision {r['precision']:.3f}); author-labelled pairs: " +
              (f"{npairs['pairs_detected']}/{npairs['gold_pairs']} found." if npairs else f"{dedup['nagtegaal']['detected']}/{dedup['nagtegaal']['gold_duplicates']}."),
              "", "Settings were tuned on these datasets: expect lower", "performance on new reviews."]
    fig.text(0.53, 0.72, "\n".join(lines), fontsize=9.5, va="top", family="DejaVu Sans")
    fig.savefig(outdir / "visual_abstract.png", dpi=200, metadata=meta)
    plt.close(fig)


def reproduced_values(st, rows, dedup):
    """Every checkable quantity, keyed as in expected/*.json."""
    got = dict(st)
    for r in rows:
        d = r["dataset_id"]
        got[f"screen_wss95[{d}]"] = r["screen_wss95_mean"]
        got[f"screen_wss95_sd[{d}]"] = r["screen_wss95_sd"]
        got[f"records[{d}]"] = r["records"]
        got[f"relevant[{d}]"] = r["relevant"]
        got[f"prevalence_pct[{d}]"] = r["prevalence_pct"]
        for m in ("nb", "svm"):
            if r[f"asreview_{m}_wss95"] is not None:
                got[f"asreview_{m}_wss95[{d}]"] = r[f"asreview_{m}_wss95"]
            if r[f"asreview_{m}_wss95_sd"] is not None:
                got[f"asreview_{m}_wss95_sd[{d}]"] = r[f"asreview_{m}_wss95_sd"]
    got["screen_seeds"] = rows[0]["screen_seeds"] if rows else None
    got["asreview_seeds"] = rows[0]["asreview_seeds"] if rows else None
    for k in ("records", "detected", "gold_duplicates", "flagged_not_in_gold", "recall"):
        got[f"dedup_nagtegaal_{k}"] = dedup["nagtegaal"][k]
    if "pairs" in dedup["nagtegaal"]:
        for k in ("gold_pairs", "pairs_detected", "pair_recall", "extra_links"):
            got[f"dedup_nagtegaal_{k}"] = dedup["nagtegaal"]["pairs"][k]
    for k in ("originals", "injected", "detected", "false_positives", "total_flagged", "precision", "recall", "f1"):
        got[f"dedup_reformatted_{k}"] = dedup["reformatted"][k]
    for k in ("records", "blocked", "brute", "brute_only", "blocked_only"):
        got[f"dedup_blocked_vs_brute_{k}"] = dedup["blocked_vs_brute"][k]
    for s in dedup["scaling"]:
        got[f"dedup_blocked_comparisons[n={s['n']}]"] = s["blocked_comparisons"]
    return got


def compare(got, expected_path):
    exp = json.loads(Path(expected_path).read_text(encoding="utf-8"))
    out = []
    for key, spec in exp["values"].items():
        v, dp = spec["value"], spec["decimals"]
        g = got.get(key)
        ok = g is not None and round(float(g), dp) == round(float(v), dp)
        out.append({"quantity": key, "expected": v, "reproduced": None if g is None else (int(round(float(g))) if dp == 0 else round(float(g), dp + 2)),
                    "decimals": dp, "printed": spec.get("printed", None), "where": spec.get("where", ""), "result": "PASS" if ok else "FAIL"})
    return out, exp


def pin(got, path, protocol, mode, run_info=None):
    """Write the reproduced values as a reference file. Used once per protocol by a maintainer; a file written
    this way is a REGRESSION PIN (it can only detect change), not an independent check."""
    vals = {}
    for k, v in sorted(got.items()):
        if v is None or isinstance(v, (bool, str)) or (isinstance(v, float) and np.isnan(v)):
            continue
        integer = float(v).is_integer() and not any(t in k for t in ("wss95", "p_vs", "mean", "median", "diff", "recall", "precision", "f1", "pct", "_min", "_max"))
        vals[k] = {"value": int(v) if integer else round(float(v), 4), "decimals": 0 if integer else 4}
    doc = {"source": f"Regression pin for protocol {protocol}, {mode} mode, written by analysis/make_outputs.py --pin from the run "
                     f"described in 'run'. It detects any change in these numbers; it is NOT an independent check "
                     f"of them (protocol v1.0.0 is checked against values extracted from the paper, and bench/test_protocol.mjs checks that "
                     f"the v1.0.1 driver equals the shipped simulation under v1.0.0 settings). Cross-platform CI runs that pass against "
                     f"this file are the independent evidence that it is reproducible.", "run": run_info or {}, "values": vals}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")


def machine_info():
    import os
    import platform
    info = {"python": platform.python_version(), "system": platform.system(), "release": platform.release(),
            "version": platform.version(), "machine": platform.machine(), "processor": platform.processor(), "cpus": os.cpu_count()}
    try:
        if platform.system() == "Windows":
            import subprocess
            info["cpu_model"] = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"],
                                               capture_output=True, text=True, timeout=30).stdout.strip()
        elif Path("/proc/cpuinfo").exists():
            info["cpu_model"] = next((l.split(":", 1)[1].strip() for l in Path("/proc/cpuinfo").read_text().splitlines() if l.startswith("model name")), "")
        elif platform.system() == "Darwin":
            import subprocess
            info["cpu_model"] = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception as e:  # informational only
        info["cpu_model_error"] = str(e)
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--outputs", required=True)
    ap.add_argument("--expected", required=True)
    ap.add_argument("--protocol", default="v1.0.1")
    ap.add_argument("--pin", help="write the reproduced values to this reference file (maintainers)")
    ap.add_argument("--wall-seconds", type=float, default=None)
    a = ap.parse_args()
    outdir = Path(a.outputs)
    outdir.mkdir(parents=True, exist_ok=True)
    rows, st = stats(a.results)
    st["protocol"] = a.protocol
    dedup = json.loads((Path(a.results) / "dedup.json").read_text())
    na = rows[0]["asreview_seeds"] if rows else 0

    write_table(outdir / "table1_wss95", ["Dataset", "Records", "Relevant (%)", f"Screen WSS@95 mean (SD), {rows[0]['screen_seeds'] if rows else 0} seeds",
                                          f"ASReview NB mean (SD), {na} seeds", f"ASReview SVM mean (SD), {na} seeds"],
                [[r["dataset"], f"{r['records']:,}", f"{r['relevant']} ({r['prevalence_pct']:.1f})",
                  f3sd(r["screen_wss95_mean"], r["screen_wss95_sd"]), f3sd(r["asreview_nb_wss95"], r["asreview_nb_wss95_sd"]),
                  f3sd(r["asreview_svm_wss95"], r["asreview_svm_wss95_sd"])] for r in rows]
                + [["Mean", "", "", f"{st['screen_mean_all']:.3f}", f3(st.get("asreview_nb_mean")), f3(st.get("asreview_svm_mean"))]])
    n_, r_, b_ = dedup["nagtegaal"], dedup["reformatted"], dedup["blocked_vs_brute"]
    pr = n_.get("pairs")
    t2 = [["Author-labelled duplicates (Nagtegaal 2019; title and abstract only)", f"{n_['records']:,} records, {pr['gold_pairs'] if pr else n_['gold_duplicates']} labelled duplicate pairs",
           (f"{pr['pairs_detected']}/{pr['gold_pairs']} pairs found (unordered scoring, recall {pr['pair_recall']:.2f}); {pr['extra_links']} further links, not labelled in the source (see dedup.json for titles). "
            if pr else "") + f"[v1.0.0 directed-ID scoring: {n_['detected']}/{n_['gold_duplicates']} (recall {n_['recall']:.2f}); {n_['flagged_not_in_gold']} further records flagged]"],
          ["Reformatted duplicates (Cohen ACE, DOI removed, title altered)", f"{r_['originals']:,} originals + {r_['injected']} duplicates",
           f"{r_['detected']}/{r_['injected']} detected (recall {r_['recall']:.3f}); {r_['false_positives']} false positives of {r_['total_flagged']} flagged (precision {r_['precision']:.3f}; F1 {r_['f1']:.3f})"],
          ["Blocked vs exhaustive pass (Nagtegaal subset, titles only, strict threshold)", f"{b_['records']:,} records",
           f"blocked {b_['blocked']}, exhaustive {b_['brute']}, missed by blocking {b_['brute_only']}"]]
    mach = dedup.get("machine")
    for s in dedup["scaling"]:
        t2.append([f"Scaling, synthetic corpus", f"{s['n']:,} records",
                   f"{s['blocked_comparisons']:,} blocked comparisons vs {s['all_pairs']:,.0f} all pairs; {s['blocked_ms']:,} ms blocked" +
                   (f", {s['brute_ms']:,} ms exhaustive" if s["brute_ms"] is not None else "") +
                   (f" (machine-dependent: {mach['cpu']}, {mach['cores']} cores, run in parallel with the other jobs)" if mach else " (times are machine-dependent)")])
    write_table(outdir / "table2_dedup", ["Test", "Input", "Result"], t2)
    figures(rows, st, dedup, outdir, a.protocol)
    (outdir / "stats.json").write_text(json.dumps(st, indent=1))
    # Timings belong to the machine that RAN the benchmark (recorded by run_dedup.mjs); runs from before v1.0.1
    # did not record it. The analysis machine is recorded separately (it differs for --from-canonical).
    mi = {"protocol": a.protocol, "results": str(a.results), "benchmark_machine": mach or "not recorded (run made before v1.0.1)",
          "node": dedup.get("node"), "dedup_blocked_ms": {str(s["n"]): s["blocked_ms"] for s in dedup["scaling"]},
          "wall_seconds_total": a.wall_seconds, "analysis_machine": machine_info()}
    (outdir / "machine.json").write_text(json.dumps(mi, indent=1) + "\n", encoding="utf-8")

    got = reproduced_values(st, rows, dedup)
    if a.pin:
        pin(got, a.pin, a.protocol, Path(a.outputs).name,
            {"results": str(a.results), "benchmark_machine": mach, "node": dedup.get("node"), "appSha256": dedup.get("appSha256")})
        print(f"reference values written to {a.pin} (regression pin)")
    if not Path(a.expected).exists():
        # Fail closed: a run with no reference values has checked nothing.
        msg = (f"NO REFERENCE VALUES: {a.expected} does not exist, so nothing was checked. Outputs are in {outdir}. "
               "A maintainer creates the reference once with --pin from a canonical run; until then this run is unverified.")
        (outdir / "reproduction_report.md").write_text(f"# Reproduction report\n\n0/0 numbers reproduced\n\n{msg}\n", encoding="utf-8")
        print(msg)
        sys.exit(0 if a.pin else 3)
    report, exp = compare(got, a.expected)
    npass = sum(r["result"] == "PASS" for r in report)
    nprinted = sum(1 for r in report if r["printed"])
    lines = ["| Quantity | Where | Expected | Reproduced | Result |", "|---|---|--:|--:|---|"]
    lines += [f"| {r['quantity']} | {r['where'] or ('not printed in the paper' if r['printed'] is False else '')} | {r['expected']} | {r['reproduced']} | {r['result']} |" for r in report]
    summary = f"{npass}/{len(report)} numbers reproduced"
    detail = f"protocol {a.protocol}; reference: {a.expected}" + (f"; {nprinted} of the checked numbers are printed in the paper" if nprinted else "")
    unchecked = exp.get("printed_not_checked") or {}
    tail = ""
    if unchecked:
        tail = "\n\n## Printed in the paper but not checked by this run\n\n| Quantity | Printed | Why not checked |\n|---|---|---|\n" + \
               "\n".join(f"| {k} | {v['printed']} | {v['reason']} |" for k, v in unchecked.items()) + "\n"
    (outdir / "reproduction_report.md").write_text(f"# Reproduction report\n\n{summary}\n\n{detail}\n\n" + "\n".join(lines) + "\n" + tail, encoding="utf-8")
    (outdir / "reproduction_report.json").write_text(json.dumps({"summary": summary, "protocol": a.protocol, "expected": a.expected, "checks": report,
                                                                 "printed_not_checked": unchecked}, indent=1))
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(outdir.glob("*.csv"))}
    (outdir / "SHA256SUMS.tables").write_text("".join(f"{h}  {n}\n" for n, h in hashes.items()))

    width = max(len(r["quantity"]) for r in report)
    print(f"\n{'quantity'.ljust(width)}  {'expected':>10}  {'reproduced':>12}  result")
    for r in report:
        print(f"{r['quantity'].ljust(width)}  {str(r['expected']):>10}  {str(r['reproduced']):>12}  {r['result']}")
    print(f"\n{summary} ({detail}): {'ALL PASS' if npass == len(report) else 'FAILURES PRESENT'}")
    print(f"outputs written to {outdir}")
    sys.exit(0 if npass == len(report) else 1)


if __name__ == "__main__":
    main()
