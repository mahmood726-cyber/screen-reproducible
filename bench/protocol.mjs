// Benchmark protocols for the Screen simulation.
//
// Protocol "v1.0.0" is the protocol of the archived v1.0.0 results and of the numbers printed in the
// paper (F1000Research, version as submitted): the SHIPPED simulateActiveLearning() is called verbatim
// (run_screen.mjs does exactly that). It has two properties the audit of 18 Oct 2026 found to differ
// from what the paper describes or from what a reviewer using the app experiences:
//
//   (a) start set. 20 records are drawn at random. If none of them is relevant, the shipped function adds
//       the FIRST relevant record IN FILE ORDER (`for (k = 0; k < N; k++) if (recs[k]._gold) ...`).
//       That record is the same for every seed, so on sparse datasets most seeds share one forced
//       relevant record and the seed-to-seed SD understates the dependence on the starting record.
//   (b) training gate. The simulation ranks as soon as it holds >=1 relevant and >=2 irrelevant records
//       (`nPos >= 1 && nNeg >= 2`). The app's Train button (mlTrainOn) refuses to train until the
//       reviewer has >=2 relevant and >=2 irrelevant records ("Label at least 2 includes and 2 excludes").
//
// Protocol "v1.0.1" (the new default) changes exactly those two things and nothing else:
//
//   (a') start set. Same 20 random records. If a class is missing, the record added is the first record
//        of that class in the SEED'S OWN random permutation (i.e. after the 20 drawn records). This is a
//        uniformly random draw among the remaining records of that class, made with the seed's RNG, and it
//        consumes no extra random numbers. ASReview's harness likewise draws its relevant prior at random.
//   (b') training gate = the app's gate: rank only once >=2 relevant and >=2 irrelevant records are
//        labelled. Until then the simulated reviewer screens records in the seed's random order (the
//        continuation of the same permutation). Note: the shipped function's pre-gate fallback screens in
//        FILE order (its comment says "random shuffle order", but `rest` is rebuilt in index order); under
//        v1.0.0 that branch is unreachable after the start set, under a 2+2 gate it is reachable, so v1.0.1
//        uses the seed's permutation rather than inherit file-order dependence. (In the app itself an
//        untrained queue is shown in import order; random order is the neutral simulation assumption.)
//
// Everything else - vocabulary, NB fit, scoring, per-record retraining, metrics, buscar - is the shipped
// code, called through the same extracted functions. simulate(api, {startDraw:"file", gate:[1,2],
// unranked:"file"}) reproduces the shipped simulateActiveLearning bit for bit; bench/test_protocol.mjs
// checks that on every quick dataset and several seeds before any v1.0.1 number is trusted.

export const PROTOCOLS = {
  "v1.0.0": { startDraw: "file", gate: [1, 2], unranked: "file", shipped: true,
    note: "paper values; shipped simulateActiveLearning called verbatim" },
  "v1.0.1": { startDraw: "rng", gate: [2, 2], unranked: "rng", shipped: false,
    note: "forced start-set record drawn with the seed RNG; app training gate (2 relevant + 2 irrelevant)" },
};

// opts: { records, rngSeed, buscar, startDraw: "file"|"rng", gate: [minPos, minNeg], unranked: "file"|"rng" }
// Returns the same object as the shipped simulateActiveLearning, plus diagnostics in `protocol`.
export function simulate(api, opts) {
  const { normalizeImported, mlBuildVocab, mlFit, mlPredict, mlBuscarP, mulberry32 } = api;
  const startDraw = opts.startDraw || "file", gate = opts.gate || [1, 2], unranked = opts.unranked || "file";
  const src = opts.records || [];
  const recs = src.map((r) => { const rec = normalizeImported(r); rec._gold = r.gold ? 1 : 0; return rec; });
  const N = recs.length;
  if (!N) return { ok: false, msg: "no records" };
  const totalPos = recs.reduce((a, r) => a + r._gold, 0);
  if (totalPos < 2) return { ok: false, msg: "need >=2 relevant" };
  const batch = opts.batch || 100, seedN = opts.seed || 20;
  const V = mlBuildVocab(recs);
  const rng = mulberry32(opts.rngSeed || 1234567);
  const idx = recs.map((_, i) => i);
  for (let s = idx.length - 1; s > 0; s--) { const j = Math.floor(rng() * (s + 1)); const tmp = idx[s]; idx[s] = idx[j]; idx[j] = tmp; }
  const labelledSet = {}, labelled = [], seq = [];
  let found = 0, screened = 0;
  const reveal = (i) => { if (labelledSet[i]) return; labelledSet[i] = 1; labelled.push([recs[i], recs[i]._gold]); seq.push(recs[i]._gold ? 1 : 0); screened++; if (recs[i]._gold) found++; };
  let k;
  for (k = 0; k < idx.length && Object.keys(labelledSet).length < seedN; k++) reveal(idx[k]);
  const startPos = labelled.filter((p) => p[1] === 1).length;
  let forcedPos = null, forcedNeg = null;
  // order in which a "missing class" record is looked for
  const pool = startDraw === "rng" ? idx : recs.map((_, i) => i);
  if (!labelled.some((p) => p[1] === 1)) { for (k = 0; k < N; k++) if (recs[pool[k]]._gold && !labelledSet[pool[k]]) { forcedPos = pool[k]; reveal(pool[k]); break; } }
  if (!labelled.some((p) => p[1] === 0)) { for (k = 0; k < N; k++) if (!recs[pool[k]]._gold && !labelledSet[pool[k]]) { forcedNeg = pool[k]; reveal(pool[k]); break; } }
  const curve = [{ screened, found }];
  let guard = 0, unrankedScreened = 0, firstRankedAt = null;
  const rankOf = unranked === "rng" ? (() => { const r = new Array(N); idx.forEach((v, p) => { r[v] = p; }); return r; })() : null;
  while (screened < N && found < totalPos && guard++ < N + 10) {
    let nPos = 0, i;
    for (i = 0; i < labelled.length; i++) if (labelled[i][1] === 1) nPos++;
    const nNeg = labelled.length - nPos, rest = [];
    for (i = 0; i < N; i++) if (!labelledSet[i]) rest.push(i);
    if (nPos >= gate[0] && nNeg >= gate[1]) {
      if (firstRankedAt === null) firstRankedAt = screened;
      const m = mlFit(labelled, V);
      const sc = {};
      for (i = 0; i < rest.length; i++) sc[rest[i]] = mlPredict(recs[rest[i]], m, V);
      rest.sort((a, b) => sc[b] - sc[a]);
    } else {
      unrankedScreened++;
      if (rankOf) rest.sort((a, b) => rankOf[a] - rankOf[b]);
    }
    reveal(rest[0]);
    curve.push({ screened, found });
  }
  const screenedAtRecall = (rec) => { const need = Math.ceil(rec * totalPos); for (let c = 0; c < curve.length; c++) if (curve[c].found >= need) return curve[c].screened; return N; };
  const s95 = screenedAtRecall(0.95), s100 = screenedAtRecall(1.0);
  const recallAt = (frac) => { const lim = Math.ceil(frac * N); let best = 0; for (let c = 0; c < curve.length; c++) if (curve[c].screened <= lim) best = curve[c].found; return totalPos ? best / totalPos : 0; };
  const conf = 0.95, tgt = 0.95, alpha = 1 - conf;
  let buscarStopAt = N, buscarRecall = 1, buscarP = 1, prevScr = 0;
  const step = Math.max(1, Math.floor(curve.length / 200));
  if (opts.buscar) for (let ci = 0; ci < curve.length; ci += step) {
    const scr = curve[ci].screened; if (scr === prevScr && ci) continue; prevScr = scr;
    const p = mlBuscarP(seq, N, tgt, scr);
    if (p < alpha) { buscarStopAt = scr; buscarRecall = totalPos ? curve[ci].found / totalPos : 1; buscarP = p; break; }
  }
  return {
    ok: true, N, totalPos, prevalence: totalPos / N, batch, seed: seedN, curve,
    screenedAt95: s95, screenedAt100: s100,
    wss95: 0.95 - s95 / N, wss100: 1 - s100 / N,
    recallAt10pct: recallAt(0.10), recallAt20pct: recallAt(0.20), recallAt50pct: recallAt(0.50),
    buscarStopAt, buscarRecall, buscarP, buscarWss: 0.95 - buscarStopAt / N,
    protocol: { startDraw, gate, unranked, startSetRelevant: startPos, forcedRelevantIndex: forcedPos,
      forcedIrrelevantIndex: forcedNeg, unrankedScreenedAfterStart: unrankedScreened, firstRankedAtScreened: firstRankedAt },
  };
}

// Start-set diagnostics for the SHIPPED v1.0.0 protocol (which returns none): which record was forced in.
export function shippedStartDiagnostics(recsGold, rngSeed, mulberry32, seedN = 20) {
  const N = recsGold.length, rng = mulberry32(rngSeed || 1234567), idx = recsGold.map((_, i) => i);
  for (let s = idx.length - 1; s > 0; s--) { const j = Math.floor(rng() * (s + 1)); const tmp = idx[s]; idx[s] = idx[j]; idx[j] = tmp; }
  const start = idx.slice(0, seedN), startPos = start.filter((i) => recsGold[i]).length;
  let forced = null;
  if (!startPos) for (let k = 0; k < N; k++) if (recsGold[k]) { forced = k; break; }
  return { startSetRelevant: startPos, forcedRelevantIndex: forced };
}
