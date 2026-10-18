// Checks for bench/protocol.mjs. Exit code 0 only if every check passes.
//
//   node bench/test_protocol.mjs [--datasets id,id] [--seeds 101,202,...]
//
// 1. Equivalence control: the v1.0.1 driver with the v1.0.0 settings (file-order forced record,
//    1+2 gate, file-order pre-gate queue) reproduces the SHIPPED simulateActiveLearning exactly
//    (every curve point and every metric, compared with ===). This is what licenses calling the
//    v1.0.1 numbers "the shipped ranker under a different protocol" rather than a re-implementation.
// 2. The app's Train-button gate (mlTrainOn, extracted verbatim) refuses 1 relevant + 2 irrelevant
//    and accepts 2 + 2, i.e. v1.0.1's gate [2,2] is the UI gate.
// 3. Start-set control (planted): on a synthetic corpus whose only relevant records sit at the END of
//    the file, v1.0.0's forced record is the same index for every seed; v1.0.1's varies with the seed.
// 4. Gate control: under v1.0.1 no ranked round happens before 2 relevant + 2 irrelevant are labelled.
import { readFileSync } from "fs";
import { gunzipSync } from "zlib";
import { dirname, join } from "path";
import { fileURLToPath } from "url";
import { loadShipped, RANKER, parseCSV } from "./extract.mjs";
import { simulate, PROTOCOLS } from "./protocol.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const arg = (k, d) => { const i = process.argv.indexOf("--" + k); return i > 0 ? process.argv[i + 1] : d; };
const datasets = arg("datasets", "cohen_antihistamines,cohen_urinaryincontinence,cohen_estrogens,cohen_nsaids").split(",");
const seeds = arg("seeds", "101,202,303").split(",").map(Number);
const { api } = loadShipped(RANKER);
let fails = 0, checks = 0;
const ok = (cond, msg) => { checks++; if (!cond) { fails++; console.log("FAIL " + msg); } else console.log("ok   " + msg); };

function load(id) {
  const rows = parseCSV(gunzipSync(readFileSync(join(ROOT, "data", "corpora", id + ".csv.gz"))).toString("utf8"));
  return rows.map((r, i) => ({ id: "r" + i, title: r.title || "", abstract: r.abstract || "", keywords: [], gold: String(r.label_included).trim() === "1" ? 1 : 0 }));
}
const KEYS = ["N", "totalPos", "screenedAt95", "screenedAt100", "wss95", "wss100", "recallAt10pct", "recallAt20pct", "recallAt50pct", "buscarStopAt", "buscarRecall", "buscarP"];

// 1. equivalence
for (const id of datasets) {
  const recs = load(id);
  for (const s of seeds) {
    const a = api.simulateActiveLearning({ records: recs, batch: 1, rngSeed: s, buscar: true });
    const b = simulate(api, { records: recs, batch: 1, rngSeed: s, buscar: true, startDraw: "file", gate: [1, 2], unranked: "file" });
    const same = KEYS.every((k) => a[k] === b[k]) && a.curve.length === b.curve.length &&
      a.curve.every((c, i) => c.screened === b.curve[i].screened && c.found === b.curve[i].found);
    ok(same, `driver(v1.0.0 settings) === shipped simulateActiveLearning on ${id} seed ${s}`);
  }
}
// 2. UI gate
{
  const mk = (n, g) => Array.from({ length: n }, (_, i) => ({ id: "g" + g + i, title: (g ? "warfarin trial bleeding " : "unrelated survey cohort ") + i, abstract: "text " + i, _g: g }));
  const recs = [...mk(1, 1), ...mk(2, 0)].map(api.normalizeImported);
  const r12 = api.mlTrainOn(recs, (r) => (r.title.startsWith("warfarin") ? 1 : 0), {});
  const recs2 = [...mk(2, 1), ...mk(2, 0)].map(api.normalizeImported);
  const r22 = api.mlTrainOn(recs2, (r) => (r.title.startsWith("warfarin") ? 1 : 0), {});
  ok(r12.ok === false && r22.ok === true, `app gate (mlTrainOn): 1+2 refused (${r12.ok}), 2+2 accepted (${r22.ok}); v1.0.1 gate = ${JSON.stringify(PROTOCOLS["v1.0.1"].gate)}`);
}
// 3. planted start-set control: 400 records, the 6 relevant ones are the last 6 rows of the file
{
  const recs = Array.from({ length: 400 }, (_, i) => ({ id: "p" + i, title: (i >= 394 ? "anticoagulant randomised trial " : "observational survey report ") + "topic" + (i % 37),
    abstract: "words w" + (i % 53) + " w" + (i % 17), keywords: [], gold: i >= 394 ? 1 : 0 }));
  const forcedOld = new Set(), forcedNew = new Set();
  let noRelStart = 0;
  for (const s of [101, 202, 303, 404, 505, 606, 707, 808, 909, 1010]) {
    const a = simulate(api, { records: recs, batch: 1, rngSeed: s, startDraw: "file", gate: [1, 2], unranked: "file" });
    const b = simulate(api, { records: recs, batch: 1, rngSeed: s, startDraw: "rng", gate: [2, 2], unranked: "rng" });
    if (a.protocol.startSetRelevant === 0) { noRelStart++; forcedOld.add(a.protocol.forcedRelevantIndex); forcedNew.add(b.protocol.forcedRelevantIndex); }
  }
  ok(noRelStart >= 5 && forcedOld.size === 1 && [...forcedOld][0] === 394, `v1.0.0 forced record is file-order index 394 for all ${noRelStart} seeds without a relevant start record`);
  ok(forcedNew.size >= 3, `v1.0.1 forced record varies with the seed (${forcedNew.size} distinct of ${noRelStart}: ${[...forcedNew].join(",")})`);
}
// 4. gate under v1.0.1 on a real dataset
for (const id of datasets.slice(0, 2)) {
  const recs = load(id);
  for (const s of seeds) {
    const b = simulate(api, { records: recs, batch: 1, rngSeed: s, startDraw: "rng", gate: [2, 2], unranked: "rng" });
    const p = b.protocol;
    const havePos = p.startSetRelevant + (p.forcedRelevantIndex !== null ? 1 : 0);
    ok(p.firstRankedAtScreened !== null && (havePos >= 2 ? p.unrankedScreenedAfterStart === 0 : p.unrankedScreenedAfterStart >= 1),
      `v1.0.1 on ${id} seed ${s}: start relevant ${p.startSetRelevant}, first ranked round after ${p.firstRankedAtScreened} screened, ${p.unrankedScreenedAfterStart} unranked picks`);
  }
}
console.log(`\n${checks - fails}/${checks} protocol checks passed`);
process.exit(fails ? 1 : 0);
