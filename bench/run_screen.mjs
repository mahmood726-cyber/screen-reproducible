// Screen active-learning benchmark (headless, no browser).
//
// Runs the shipped Screen ranker (extracted verbatim, see extract.mjs) over one or more
// labelled datasets and writes per-dataset WSS@95, recall@k, a per-seed recall curve and
// stopping-rule fields.
//
//   node bench/run_screen.mjs --dataset cohen_adhd --seeds 101,202 --protocol v1.0.1 --out results/v1.0.1/full/screen/cohen_adhd.json
//
// --protocol v1.0.0  the shipped simulateActiveLearning, called verbatim (the paper's numbers):
//                    20 random records, a missing class forced in from FILE order, rank once
//                    >=1 relevant + >=2 irrelevant are labelled, then retrain after every record.
// --protocol v1.0.1  (default) bench/protocol.mjs: the forced record is drawn with the seed's RNG and
//                    ranking starts at the app's training gate (>=2 relevant + >=2 irrelevant).
// Sensitivity overrides (v1.0.1 driver only): --start-draw file|rng  --gate P,N  --unranked file|rng
import { readFileSync, writeFileSync, mkdirSync } from "fs";
import { gunzipSync } from "zlib";
import { dirname, join } from "path";
import { fileURLToPath } from "url";
import { loadShipped, RANKER, parseCSV } from "./extract.mjs";
import { PROTOCOLS, simulate, shippedStartDiagnostics } from "./protocol.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const arg = (k, d) => { const i = process.argv.indexOf("--" + k); return i > 0 ? process.argv[i + 1] : d; };
const datasets = arg("dataset", "").split(",").filter(Boolean);
const seeds = arg("seeds", "101,202,303,404,505,606,707,808,909,1010").split(",").map(Number);
const out = arg("out");
const protocolName = arg("protocol", "v1.0.1");
if (!datasets.length || !out) { console.error("usage: --dataset id[,id] --seeds s1,s2 [--protocol v1.0.0|v1.0.1] --out file.json"); process.exit(2); }
if (!PROTOCOLS[protocolName]) { console.error("unknown protocol " + protocolName + " (known: " + Object.keys(PROTOCOLS).join(", ") + ")"); process.exit(2); }
const proto = { ...PROTOCOLS[protocolName] };
const ov = { startDraw: arg("start-draw"), gate: arg("gate"), unranked: arg("unranked") };
if (ov.startDraw || ov.gate || ov.unranked) {
  if (proto.shipped) { console.error("overrides apply to the v1.0.1 driver only"); process.exit(2); }
  if (ov.startDraw) proto.startDraw = ov.startDraw;
  if (ov.gate) proto.gate = ov.gate.split(",").map(Number);
  if (ov.unranked) proto.unranked = ov.unranked;
  proto.note += " [overridden: " + JSON.stringify(ov) + "]";
}
// recall curve on a 1% grid of the proportion screened (same rule as the app's recallAt)
const GRID = Array.from({ length: 101 }, (_, i) => i / 100);
function recallCurve(o) {
  return GRID.map((frac) => { const lim = Math.ceil(frac * o.N); let best = 0; for (const c of o.curve) if (c.screened <= lim) best = c.found; return o.totalPos ? best / o.totalPos : 0; });
}

const { api, appSha256 } = loadShipped(RANKER);
const manifest = JSON.parse(readFileSync(join(ROOT, "data", "corpora", "manifest.json"), "utf8"));
const mean = (a) => a.reduce((x, y) => x + y, 0) / a.length;
const sd = (a) => { if (a.length < 2) return 0; const m = mean(a); return Math.sqrt(a.reduce((x, y) => x + (y - m) ** 2, 0) / (a.length - 1)); };

const result = { tool: "screen", appSha256, node: process.version, seeds,
  protocol: { name: protocolName, startDraw: proto.startDraw, gate: proto.gate, unranked: proto.unranked, shipped: proto.shipped, note: proto.note },
  recall_grid: GRID, perDataset: {} };
for (const id of datasets) {
  const meta = manifest.datasets.find((d) => d.id === id);
  if (!meta) throw new Error("unknown dataset " + id);
  const rows = parseCSV(gunzipSync(readFileSync(join(ROOT, "data", "corpora", id + ".csv.gz"))).toString("utf8"));
  const recs = rows.map((r, i) => ({ id: "r" + i, title: r.title || "", abstract: r.abstract || "", keywords: [],
    gold: String(r.label_included).trim() === "1" ? 1 : 0 }));
  const runs = [];
  const t0 = Date.now();
  for (const rngSeed of seeds) {
    let o;
    if (proto.shipped) {
      o = api.simulateActiveLearning({ records: recs, batch: 1, rngSeed, buscar: true });
      if (o && o.ok) o.protocol = { ...shippedStartDiagnostics(recs.map((r) => r.gold), rngSeed, api.mulberry32), unrankedScreenedAfterStart: 0 };
    } else {
      o = simulate(api, { records: recs, batch: 1, rngSeed, buscar: true, startDraw: proto.startDraw, gate: proto.gate, unranked: proto.unranked });
    }
    if (!o || !o.ok) throw new Error(`simulation failed on ${id} seed ${rngSeed}: ${o && o.msg}`);
    o.recallCurve = recallCurve(o);
    delete o.curve; // large; the 1% recall grid is kept instead
    runs.push(o);
  }
  const pick = (k) => runs.map((o) => o[k]);
  result.perDataset[id] = {
    label: meta.label, suite: meta.suite, N: runs[0].N, relevant: runs[0].totalPos, prevalence: runs[0].prevalence,
    wss95_per_seed: pick("wss95"), WSS_at_95: mean(pick("wss95")), WSS_at_95_sd: sd(pick("wss95")),
    recall_at_10pct: mean(pick("recallAt10pct")), recall_at_20pct: mean(pick("recallAt20pct")), recall_at_50pct: mean(pick("recallAt50pct")),
    screened_to_95pct_recall_per_seed: pick("screenedAt95"),
    buscar_stop_at_per_seed: pick("buscarStopAt"), buscar_recall_per_seed: pick("buscarRecall"),
    recall_at_10pct_per_seed: pick("recallAt10pct"), recall_at_20pct_per_seed: pick("recallAt20pct"), recall_at_50pct_per_seed: pick("recallAt50pct"),
    recall_curve_per_seed: pick("recallCurve"),
    start_set_relevant_per_seed: runs.map((o) => o.protocol.startSetRelevant),
    forced_relevant_index_per_seed: runs.map((o) => o.protocol.forcedRelevantIndex),
    unranked_screened_after_start_per_seed: runs.map((o) => o.protocol.unrankedScreenedAfterStart),
    seconds: (Date.now() - t0) / 1000,
  };
  console.log(`[screen ${protocolName}] ${id.padEnd(30)} N=${String(runs[0].N).padStart(5)} WSS@95 ${mean(pick("wss95")).toFixed(4)} (${seeds.length} seeds, ${((Date.now() - t0) / 1000).toFixed(0)} s)`);
}
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, JSON.stringify(result, null, 1));
