// Screen de-duplication benchmark (headless, no browser).
//
// Same four tests and the same fixed seeds as allmeta's benchmark/run_benchmark.mjs,
// but driving the verbatim-extracted dedup code in a Node vm instead of a browser page:
//   1. recall on the Nagtegaal 2019 author-labelled duplicates
//   2. recall/precision on 200 reformatted Cohen ACE duplicates (DOI dropped, title mangled)
//   3. blocked vs exhaustive (brute-force) agreement on 1,500 Nagtegaal records
//   4. scaling on synthetic corpora (comparison counts are deterministic; times are not)
//
//   node bench/run_dedup.mjs --out results/dedup.json [--sizes 2000,10000,50000,100000]
import { readFileSync, writeFileSync, mkdirSync } from "fs";
import { gunzipSync } from "zlib";
import { dirname, join } from "path";
import { fileURLToPath } from "url";
import { loadShipped, DEDUP, parseCSV } from "./extract.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const arg = (k, d) => { const i = process.argv.indexOf("--" + k); return i > 0 ? process.argv[i + 1] : d; };
const out = arg("out");
const sizes = arg("sizes", "2000,10000,50000,100000").split(",").map(Number);
const BRUTE_MAX = 12000;
if (!out) { console.error("usage: --out file.json"); process.exit(2); }

const { api, appSha256 } = loadShipped(DEDUP);
// Mirrors the app's setState({records}) + runDedup(): normalise every record, then dedup.
function dupIds(records, opts) {
  const recs = records.map(api.normalizeImported);
  const info = api.dedupCore(recs, opts || {});
  return { ids: recs.filter((r) => r.dup).map((r) => r.id), edges: recs.filter((r) => r.dup).map((r) => [r.id, r.dupOf]), info };
}
// Unordered scoring. The app keeps the EARLIER record of a duplicate pair and flags the later one, while a
// gold label may sit on either member. Scoring "is the labelled record flagged?" (directed IDs, the v1.0.0
// metric, kept below as `detected`) therefore counts a correctly found pair as a miss whenever the label sits
// on the earlier record. Here a gold pair counts as found when both members end up in the same duplicate
// cluster (union-find over the app's record -> dupOf links), and an app link is an extra flag when its two
// records are not in the same gold cluster.
function clusters(edges) {
  const parent = new Map();
  const find = (x) => { if (!parent.has(x)) parent.set(x, x); while (parent.get(x) !== x) { parent.set(x, parent.get(parent.get(x))); x = parent.get(x); } return x; };
  for (const [a, b] of edges) { const ra = find(a), rb = find(b); if (ra !== rb) parent.set(ra, rb); }
  return (x) => find(x);
}
function pairScore(goldEdges, appEdges) {
  const g = clusters(goldEdges), a = clusters(appEdges);
  const found = goldEdges.filter(([x, y]) => a(x) === a(y));
  const missed = goldEdges.filter(([x, y]) => a(x) !== a(y));
  const extra = appEdges.filter(([x, y]) => g(x) !== g(y));
  return { gold_pairs: goldEdges.length, pairs_detected: found.length, pair_recall: round(found.length / goldEdges.length),
    pairs_missed: missed, app_links: appEdges.length, extra_links: extra.length, extra_links_list: extra };
}
function mulberry32(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const round = (x, n = 4) => Math.round(x * 10 ** n) / 10 ** n;
const nag = parseCSV(readFileSync(join(ROOT, "data", "dedup", "nagtegaal_2019.csv"), "utf8"));
const ace = parseCSV(gunzipSync(readFileSync(join(ROOT, "data", "corpora", "cohen_aceinhibitors.csv.gz"))).toString("utf8"));
import os from "os";
const res = { tool: "screen-dedup", appSha256, node: process.version,
  machine: { cpu: (os.cpus()[0] || {}).model || "unknown", cores: os.cpus().length, platform: os.platform(), release: os.release(), arch: os.arch(), total_mem_gb: Math.round(os.totalmem() / 2 ** 30) } };

// 1. Nagtegaal gold
{
  const recs = nag.map((r) => ({ id: r.record_id, title: r.title || "", abstract: r.abstract || "", doi: "" }));
  const idset = new Set(recs.map((r) => r.id)), gold = new Set();
  for (const r of nag) { const d = String(r.duplicate_record_id || "").trim(); if (d && idset.has(d) && d !== r.record_id) gold.add(r.record_id); }
  const goldEdges = [];
  for (const r of nag) { const d = String(r.duplicate_record_id || "").trim(); if (d && idset.has(d) && d !== r.record_id) goldEdges.push([r.record_id, d]); }
  const { ids, edges } = dupIds(recs);
  const flagged = new Set(ids); let hit = 0; for (const g of gold) if (flagged.has(g)) hit++;
  res.nagtegaal = { records: recs.length, fields_used: "title, abstract (the file has no authors, year or DOI, so the author+year assist rule and the DOI pass cannot fire)",
    gold_duplicates: gold.size, detected: hit, recall: round(hit / gold.size),
    total_flagged: ids.length, flagged_not_in_gold: ids.filter((i) => !gold.has(i)).length,
    scoring_note: "detected/recall/flagged_not_in_gold = v1.0.0 directed-ID scoring (the paper's 7/11 and 10); pairs = unordered scoring (v1.0.1)",
    pairs: pairScore(goldEdges, edges) };
  // titles of the extra links, for adjudication (they are not labelled as duplicates in the source file)
  const titleOf = new Map(nag.map((r) => [r.record_id, (r.title || "").slice(0, 160)]));
  res.nagtegaal.pairs.extra_links_list = res.nagtegaal.pairs.extra_links_list.map(([x, y]) => ({ flagged: x, kept: y, flagged_title: titleOf.get(x), kept_title: titleOf.get(y) }));
}
// 2. reformatted Cohen ACE duplicates (seed 20260608, as in allmeta)
{
  const base = ace.slice(0, 1200).map((r, i) => ({ id: "o" + i, title: r.title || "", abstract: (r.abstract || "").slice(0, 400),
    authors: (r.authors || "").split(";").map((s) => s.trim()).filter(Boolean), year: r.year || "", doi: "10.0/orig" + i })).filter((r) => r.title.length > 25);
  const rng = mulberry32(20260608), K = 200, idxs = base.map((_, i) => i);
  for (let s = idxs.length - 1; s > 0; s--) { const j = Math.floor(rng() * (s + 1)); [idxs[s], idxs[j]] = [idxs[j], idxs[s]]; }
  const dups = [];
  for (let i = 0; i < K; i++) {
    const o = base[idxs[i]];
    let t = o.title.toLowerCase().replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim();
    const w = t.split(" "); if (w.length > 6) t = w.slice(0, Math.max(6, w.length - 2)).join(" ");
    dups.push({ id: "dup" + i, title: t, abstract: o.abstract, authors: o.authors, year: o.year, doi: "" });
  }
  const { ids, edges } = dupIds(base.concat(dups));
  const dupSet = new Set(dups.map((d) => d.id)), flagged = new Set(ids);
  const reformattedPairs = pairScore(dups.map((d, i) => [d.id, base[idxs[i]].id]), edges);
  let tp = 0; for (const d of dups) if (flagged.has(d.id)) tp++;
  const fp = ids.filter((i) => !dupSet.has(i)).length, rec = tp / K, prec = tp / ids.length;
  res.reformatted = { originals: base.length, injected: K, detected: tp, missed: K - tp, recall: round(rec),
    total_flagged: ids.length, false_positives: fp, precision: round(prec), f1: round(2 * prec * rec / (prec + rec)),
    pairs: { gold_pairs: reformattedPairs.gold_pairs, pairs_detected: reformattedPairs.pairs_detected, pair_recall: reformattedPairs.pair_recall,
      app_links: reformattedPairs.app_links, extra_links: reformattedPairs.extra_links } };
}
// 3. blocked vs exhaustive on 1,500 Nagtegaal records (strict threshold, as in allmeta)
{
  const recs = nag.slice(0, 1500).map((r) => ({ id: r.record_id, title: r.title || "", abstract: "", doi: "" }));
  const b = new Set(dupIds(recs).ids), x = new Set(dupIds(recs, { brute: true }).ids);
  let both = 0, bOnly = 0, xOnly = 0;
  b.forEach((i) => (x.has(i) ? both++ : bOnly++)); x.forEach((i) => { if (!b.has(i)) xOnly++; });
  res.blocked_vs_brute = { records: recs.length, blocked: b.size, brute: x.size, in_both: both, blocked_only: bOnly, brute_only: xOnly };
}
// 4. scaling (synthetic corpus generator identical to allmeta's)
function makeCorpus(n) {
  const VOCAB = Math.max(3000, n / 4), rng = mulberry32(99 + n), recs = []; let last = "";
  for (let i = 0; i < n; i++) {
    if (i % 11 === 0 && i > 0 && last) { recs.push({ id: "x" + i, title: last + " .", abstract: "", doi: "" }); continue; }
    const len = 8 + Math.floor(rng() * 5), ws = [];
    for (let k = 0; k < len; k++) ws.push("w" + Math.floor(rng() * VOCAB));
    last = ws.join(" ") + " s" + i;
    recs.push({ id: "x" + i, title: last, abstract: "", doi: "10.5/d" + i });
  }
  return recs;
}
res.scaling = [];
for (const n of sizes) {
  const corpus = makeCorpus(n);
  let t = process.hrtime.bigint(); const b = dupIds(corpus); const blockedMs = Number(process.hrtime.bigint() - t) / 1e6;
  let bruteMs = null, bruteComparisons = null;
  if (n <= BRUTE_MAX) { t = process.hrtime.bigint(); const x = dupIds(corpus, { brute: true }); bruteMs = Number(process.hrtime.bigint() - t) / 1e6; bruteComparisons = x.info.comparisons; }
  res.scaling.push({ n, blocked_comparisons: b.info.comparisons, blocked_merges: b.info.merges, all_pairs: n * (n - 1) / 2,
    brute_comparisons: bruteComparisons, blocked_ms: Math.round(blockedMs), brute_ms: bruteMs == null ? null : Math.round(bruteMs) });
  console.log(`[dedup] n=${n}: blocked ${Math.round(blockedMs)} ms, ${b.info.comparisons} comparisons` + (bruteMs != null ? `; exhaustive ${Math.round(bruteMs)} ms` : ""));
}
console.log(`[dedup] Nagtegaal directed ${res.nagtegaal.detected}/${res.nagtegaal.gold_duplicates}, pairs ${res.nagtegaal.pairs.pairs_detected}/${res.nagtegaal.pairs.gold_pairs} (+${res.nagtegaal.pairs.extra_links} extra links); reformatted ${res.reformatted.detected}/200 precision ${res.reformatted.precision}; blocked=brute ${res.blocked_vs_brute.blocked}/${res.blocked_vs_brute.brute}`);
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, JSON.stringify(res, null, 1));
