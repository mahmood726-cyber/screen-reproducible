"""Build the live results page (GitHub Pages) from one CI run's artefacts. Standard library only.

  python ci/build_site.py --runs runs --mode full --canonical full-docker \
      --platform "Docker (canonical)=full-docker" --platform "Linux=full-ubuntu-latest" ... \
      --compare success --site pages --title "..." --repo owner/name --sha <sha> --run-id <id> --links "Paper DOI=https://..."

Writes pages/<mode>/index.html (PASS/FAIL table of the canonical run, per-platform summary, figures) and
pages/<mode>/meta.json, then rebuilds pages/index.html from every <mode>/meta.json present, so a quick run
never overwrites the page of the latest full run. Nothing here changes any result: it only reads
outputs/<mode>/reproduction_report.md, stats.json and figures produced by reproduce.py.
"""
import argparse
import html
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

CSS = """:root{--bg:#f6f4ef;--panel:#fff;--ink:#15181d;--muted:#5c6470;--ok:#1d7a3a;--bad:#b0261d;--border:#d9d5cc;--accent:#2c5e8a}
@media (prefers-color-scheme:dark){:root{--bg:#141618;--panel:#1c1f23;--ink:#e7e4dc;--muted:#98a0ae;--ok:#5cc27a;--bad:#f07b72;--border:#2f343a;--accent:#6aa6d4}}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--ink)}
main{max-width:1100px;margin:0 auto;padding:1.2rem 1rem 3rem}h1{font-size:1.5rem;margin:.2rem 0}h2{font-size:1.1rem;margin:1.6rem 0 .5rem}
.panel{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:1rem 1.1rem;margin-top:1rem}
.banner{font-size:1.15rem;font-weight:700}.ok{color:var(--ok)}.bad{color:var(--bad)}.muted{color:var(--muted);font-size:.9rem}
table{border-collapse:collapse;width:100%;font-size:.88rem;font-variant-numeric:tabular-nums}th,td{text-align:left;padding:.3rem .5rem;border-bottom:1px solid var(--border)}
.scroll{overflow-x:auto}a{color:var(--accent)}figure{margin:1rem 0}figure img{max-width:100%;height:auto;border:1px solid var(--border);border-radius:6px;background:#fff}
figcaption{color:var(--muted);font-size:.85rem}code{font-size:.85em}"""


def find_report(art_dir, mode):
    hits = [p for p in Path(art_dir).rglob("reproduction_report.md") if p.parent.name == mode] or list(Path(art_dir).rglob("reproduction_report.md"))
    return hits[0] if hits else None


def summary_line(report):
    if not report:
        return None, "no report (run did not finish)"
    m = re.search(r"(\d+)/(\d+) numbers reproduced", report.read_text(encoding="utf-8"))
    if not m:
        return None, "report unreadable"
    a, b = int(m.group(1)), int(m.group(2))
    return a == b, f"{a}/{b} numbers reproduced"


def md_table_to_html(md):
    rows = [l.strip() for l in md.splitlines() if l.strip().startswith("|")]
    if len(rows) < 2:
        return "<p>(no table)</p>"
    cells = lambda r: [c.strip() for c in r.strip("|").split("|")]
    head, body = cells(rows[0]), [cells(r) for r in rows[2:]]
    def td(c):
        cls = ' class="ok"' if c == "PASS" else (' class="bad"' if c == "FAIL" else "")
        return f"<td{cls}>{html.escape(c)}</td>"
    return ('<div class="scroll"><table><thead><tr>' + "".join(f"<th>{html.escape(h)}</th>" for h in head) + "</tr></thead><tbody>"
            + "".join("<tr>" + "".join(td(c) for c in r) + "</tr>" for r in body) + "</tbody></table></div>")


def page(title, body):
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta name="color-scheme" content="light dark"><title>{html.escape(title)}</title><style>{CSS}</style></head><body><main>{body}</main></body></html>\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True); ap.add_argument("--mode", required=True); ap.add_argument("--canonical", required=True)
    ap.add_argument("--platform", action="append", default=[]); ap.add_argument("--compare", default="")
    ap.add_argument("--site", required=True); ap.add_argument("--title", required=True); ap.add_argument("--repo", required=True)
    ap.add_argument("--sha", required=True); ap.add_argument("--run-id", required=True); ap.add_argument("--links", action="append", default=[])
    ap.add_argument("--mode-note", default="")
    a = ap.parse_args()
    runs, site = Path(a.runs), Path(a.site)
    out = site / a.mode
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    repo_url = f"https://github.com/{a.repo}"
    run_url, commit_url = f"{repo_url}/actions/runs/{a.run_id}", f"{repo_url}/commit/{a.sha}"
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    plats = []
    for spec in a.platform:
        label, art = spec.split("=", 1)
        ok, line = summary_line(find_report(runs / art, a.mode))
        plats.append({"platform": label, "artifact": art, "ok": ok, "summary": line})
    canon = find_report(runs / a.canonical, a.mode)
    all_ok = bool(plats) and all(p["ok"] for p in plats) and a.compare in ("", "success")
    figs = []
    if canon:
        for png in sorted(canon.parent.glob("*.png")):
            shutil.copy2(png, out / png.name); figs.append(png.name)
        for extra in ("reproduction_report.md", "stats.json"):
            if (canon.parent / extra).exists():
                shutil.copy2(canon.parent / extra, out / extra)
    meta = {"mode": a.mode, "all_ok": all_ok, "when": when, "sha": a.sha, "run_id": a.run_id, "run_url": run_url,
            "platforms": plats, "compare": a.compare, "mode_note": a.mode_note}
    (out / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")

    links = " · ".join(f'<a href="{html.escape(u)}">{html.escape(t)}</a>' for t, u in (l.split("=", 1) for l in a.links))
    plat_rows = "".join(f'<tr><td>{html.escape(p["platform"])}</td><td class="{"ok" if p["ok"] else "bad"}">{html.escape(p["summary"])}</td></tr>' for p in plats)
    cmp_row = ""
    if a.compare:
        cmp_row = (f'<tr><td>Cross-platform comparison (corpus and engine output bit-identical on the strict platforms)</td>'
                   f'<td class="{"ok" if a.compare == "success" else "bad"}">{html.escape(a.compare)}</td></tr>')
    body = (f'<p class="muted"><a href="../">All runs</a> · <a href="{repo_url}">Repository</a>{" · " + links if links else ""}</p>'
            f'<h1>{html.escape(a.title)}: latest verified {html.escape(a.mode)} run</h1>'
            f'<div class="panel"><div class="banner {"ok" if all_ok else "bad"}">{"ALL PASS on every platform" if all_ok else "FAILURES PRESENT"}</div>'
            f'<p class="muted">Run <a href="{run_url}">{html.escape(a.run_id)}</a> on commit <a href="{commit_url}"><code>{html.escape(a.sha[:7])}</code></a>, published {when}.'
            f'{" " + html.escape(a.mode_note) if a.mode_note else ""}</p>'
            f'<div class="scroll"><table><thead><tr><th>Platform</th><th>Result</th></tr></thead><tbody>{plat_rows}{cmp_row}</tbody></table></div></div>'
            f'<h2>Every checked number (canonical run: {html.escape(a.canonical)})</h2>'
            f'<div class="panel">{md_table_to_html(canon.read_text(encoding="utf-8")) if canon else "<p class=bad>No report from the canonical run.</p>"}'
            f'<p class="muted">Also as <a href="reproduction_report.md">reproduction_report.md</a> and <a href="stats.json">stats.json</a>; '
            f'every run\'s full outputs are artefacts of <a href="{run_url}">the run</a>.</p></div>'
            + (f'<h2>Figures from this run</h2><div class="panel">' + "".join(f'<figure><img src="{f}" alt="{html.escape(f)}" loading="lazy"><figcaption>{html.escape(f)}</figcaption></figure>' for f in figs) + "</div>" if figs else ""))
    (out / "index.html").write_text(page(f"{a.title}: {a.mode} run", body), encoding="utf-8")

    # root index: one card per mode present
    cards = []
    for mj in sorted(site.glob("*/meta.json")):
        m = json.loads(mj.read_text(encoding="utf-8"))
        cards.append(f'<div class="panel"><h2 style="margin-top:0"><a href="{m["mode"]}/">Latest {html.escape(m["mode"])} run</a></h2>'
                     f'<div class="banner {"ok" if m["all_ok"] else "bad"}">{"ALL PASS on every platform" if m["all_ok"] else "FAILURES PRESENT"}</div>'
                     f'<p class="muted">{html.escape(m.get("mode_note", ""))} Commit <code>{html.escape(m["sha"][:7])}</code>, published {html.escape(m["when"])}, '
                     f'<a href="{html.escape(m["run_url"])}">CI run</a>.</p>'
                     + "<ul>" + "".join(f'<li>{html.escape(p["platform"])}: <span class="{"ok" if p["ok"] else "bad"}">{html.escape(p["summary"])}</span></li>' for p in m["platforms"]) + "</ul></div>")
    root = (f'<p class="muted"><a href="{repo_url}">Repository</a>{" · " + links if links else ""}</p><h1>{html.escape(a.title)}</h1>'
            f'<p>Results of the most recent continuous-integration runs, published automatically. Each run rebuilds everything from scratch on '
            f'Docker, Linux, Windows and macOS and checks every number in the paper against <code>expected/</code>.</p>' + "".join(cards))
    (site / "index.html").write_text(page(a.title, root), encoding="utf-8")
    (site / ".nojekyll").write_text("")
    print(f"site: {out} ({'ALL PASS' if all_ok else 'FAILURES'}), {len(figs)} figures; index lists {len(cards)} mode(s)")


if __name__ == "__main__":
    main()
