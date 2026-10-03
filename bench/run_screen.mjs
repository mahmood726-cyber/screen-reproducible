// Screen active-learning benchmark (headless, no browser).
//
// Runs the shipped Screen ranker (extracted verbatim, see extract.mjs) over one or more
// labelled datasets and writes per-dataset WSS@95, recall@k and stopping-rule fields.
//
//   node bench/run_screen.mjs --dataset cohen_adhd --seeds 101,202 --out results/screen/cohen_adhd.json
//
// Protocol (unchanged from the app's simulateActiveLearning): 20 random records drawn as
// the start set (forced to contain >=1 relevant and >=1 irrelevant), then retrain after
// every revealed record (per-record continuous active learning) until all relevant are found.
import { readFileSync, writeFileSync, mkdirSync } from "fs";
import { gunzipSync } from "zlib";
import { dirname, join } from "path";
import { fileURLToPath } from "url";
import { loadShipped, RANKER, parseCSV } from "./extract.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const arg = (k, d) => { const i = process.argv.indexOf("--" + k); return i > 0 ? process.argv[i + 1] : d; };
const datasets = arg("dataset", "").split(",").filter(Boolean);
const seeds = arg("seeds", "101,202,303,404,505,606,707,808,909,1010").split(",").map(Number);
const out = arg("out");
if (!datasets.length || !out) { console.error("usage: --dataset id[,id] --seeds s1,s2 --out file.json"); process.exit(2); }

const { api, appSha256 } = loadShipped(RANKER);
const manifest = JSON.parse(readFileSync(join(ROOT, "data", "corpora", "manifest.json"), "utf8"));
const mean = (a) => a.reduce((x, y) => x + y, 0) / a.length;
const sd = (a) => { if (a.length < 2) return 0; const m = mean(a); return Math.sqrt(a.reduce((x, y) => x + (y - m) ** 2, 0) / (a.length - 1)); };

const result = { tool: "screen", appSha256, node: process.version, seeds, perDataset: {} };
for (const id of datasets) {
  const meta = manifest.datasets.find((d) => d.id === id);
  if (!meta) throw new Error("unknown dataset " + id);
  const rows = parseCSV(gunzipSync(readFileSync(join(ROOT, "data", "corpora", id + ".csv.gz"))).toString("utf8"));
  const recs = rows.map((r, i) => ({ id: "r" + i, title: r.title || "", abstract: r.abstract || "", keywords: [],
    gold: String(r.label_included).trim() === "1" ? 1 : 0 }));
  const runs = [];
  const t0 = Date.now();
  for (const rngSeed of seeds) {
    const o = api.simulateActiveLearning({ records: recs, batch: 1, rngSeed, buscar: true });
    if (!o || !o.ok) throw new Error(`simulation failed on ${id} seed ${rngSeed}: ${o && o.msg}`);
    runs.push(o);
  }
  const pick = (k) => runs.map((o) => o[k]);
  result.perDataset[id] = {
    label: meta.label, suite: meta.suite, N: runs[0].N, relevant: runs[0].totalPos, prevalence: runs[0].prevalence,
    wss95_per_seed: pick("wss95"), WSS_at_95: mean(pick("wss95")), WSS_at_95_sd: sd(pick("wss95")),
    recall_at_10pct: mean(pick("recallAt10pct")), recall_at_20pct: mean(pick("recallAt20pct")), recall_at_50pct: mean(pick("recallAt50pct")),
    screened_to_95pct_recall_per_seed: pick("screenedAt95"),
    buscar_stop_at_per_seed: pick("buscarStopAt"), buscar_recall_per_seed: pick("buscarRecall"),
    seconds: (Date.now() - t0) / 1000,
  };
  console.log(`[screen] ${id.padEnd(30)} N=${String(runs[0].N).padStart(5)} WSS@95 ${mean(pick("wss95")).toFixed(4)} (${seeds.length} seeds, ${((Date.now() - t0) / 1000).toFixed(0)} s)`);
}
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, JSON.stringify(result, null, 1));
