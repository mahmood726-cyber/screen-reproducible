// Figure 1 screenshots of Screen, high resolution (Playwright + installed Google Chrome, headless).
// Viewport 1001 x 900 CSS px (the narrowest width that keeps Screen's two-column layout, so text is large relative
// to each panel), light theme, device scale factor 6: every region is captured as a page clip at
// 6 device pixels per CSS pixel, so no image is ever enlarged. compose.py lays the regions out (tight crops,
// labelled sub-panels) and checks legibility from the font sizes recorded here.
//
//   python docs/screenshots/make_sample.py work
//   (serve allmeta at commit 421ba13: python -m http.server 8092, from its repository root)
//   node docs/screenshots/capture.mjs work http://127.0.0.1:8092
//   python docs/screenshots/compose.py work docs/screenshots
//
// Screen is used from the served allmeta checkout (identical to app/screen/index.html in this repository)
// because step 6 hands counts to the PRISMA Flow app through the browser's localStorage, which needs both
// apps on one origin.
import { chromium } from "playwright";
import { readFileSync, writeFileSync, mkdirSync } from "fs";
const [D, BASE] = [process.argv[2], process.argv[3]];
const OUT = `${D}/regions`; mkdirSync(OUT, { recursive: true });
const DPR = 6;
const gold = JSON.parse(readFileSync(D + "/gold.json", "utf8"));
const b = await chromium.launch({ channel: "chrome" });
const ctx = await b.newContext({ viewport: { width: 1001, height: 900 }, colorScheme: "light", deviceScaleFactor: DPR, acceptDownloads: true });
const p = await ctx.newPage();
const meta = { dpr: DPR, viewport: [1001, 900], regions: {} };
const hideOverlays = () => p.addStyleTag({ content: "#hub-back{display:none!important} .toolbar{position:static!important} .toast,#toast{display:none!important}" });

// page-coordinate rectangle of an element (optionally its N-th ancestor / closest section)
const rect = (sel, opt = {}) => p.evaluate(([sel, opt]) => {
  let e = document.querySelector(sel); if (!e) throw new Error("missing " + sel);
  if (opt.section) e = e.closest("section");
  for (let i = 0; i < (opt.up || 0); i++) e = e.parentElement;
  const r = e.getBoundingClientRect(); return { x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height };
}, [sel, opt]);
const union = (...rs) => { const x = Math.min(...rs.map((r) => r.x)), y = Math.min(...rs.map((r) => r.y));
  return { x, y, w: Math.max(...rs.map((r) => r.x + r.w)) - x, h: Math.max(...rs.map((r) => r.y + r.h)) - y }; };
// capture one region (CSS px, page coordinates) and record the font sizes of the text inside it
async function region(name, r, pad = 6) {
  const c = { x: Math.max(0, Math.floor(r.x - pad)), y: Math.max(0, Math.floor(r.y - pad)), width: Math.ceil(r.w + 2 * pad), height: Math.ceil(r.h + 2 * pad) };
  await p.screenshot({ path: `${OUT}/${name}.png`, clip: c, fullPage: true });
  const fonts = await p.evaluate((c) => {
    const out = [];
    const inside = (rr) => rr.width > 0 && rr.height > 0 && rr.left + scrollX >= c.x - 1 && rr.right + scrollX <= c.x + c.width + 1 && rr.top + scrollY >= c.y - 1 && rr.bottom + scrollY <= c.y + c.height + 1;
    const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = tw.nextNode(); n; n = tw.nextNode()) {
      const t = n.textContent.trim(); if (t.length < 2) continue;
      const el = n.parentElement; const cs = getComputedStyle(el); if (cs.visibility === "hidden" || cs.display === "none") continue;
      const range = document.createRange(); range.selectNodeContents(n); const rr = range.getBoundingClientRect(); if (!inside(rr)) continue;
      let px = parseFloat(cs.fontSize);
      if (el.closest("svg") && el.getScreenCTM) { const m = el.getScreenCTM(); if (m) px = px * Math.hypot(m.a, m.b); }
      out.push([Math.round(px * 100) / 100, t.length, t]);
    }
    return out;
  }, c);
  meta.regions[name] = { clip: c, fonts: fonts.map((f) => f.slice(0, 2)), text: fonts.map((f) => f[2]).join(" ") };
}

await p.goto(BASE + "/screen/index.html"); await p.evaluate(() => localStorage.clear()); await p.reload();
await hideOverlays();
await p.evaluate(() => { const d = document.querySelector("details.alm-task"); if (d) d.open = false; });

// 1. Import via the real file input + re-run de-duplication, then view the flagged duplicates
await p.setInputFiles("#file-import", D + "/wilson_sample.csv"); await p.waitForTimeout(500);
await p.click("#btn-dedup"); await p.selectOption("#f-filter", "duplicate"); await p.waitForTimeout(300);
{ const imp = await rect("#btn-import"), dd = await rect("#btn-dedup");
  await region("s1_toolbar", union(imp, dd));
  const card = await rect(".cardwrap"), badges = await rect(".cardwrap .badges");
  await region("s1_card", { x: card.x, y: card.y, w: card.w, h: badges.y + badges.h - card.y + 6 });
  await region("s1_progress", await rect("#stats", { section: true })); }
meta.step1 = await p.evaluate(() => window.__almScreenpro.counts());

// 2. Review title + include/exclude terms; keyboard decisions
await p.selectOption("#f-filter", "all");
await p.fill("#f-title", "Therapies for Wilson disease");
await p.fill("#f-inc", "Wilson disease, penicillamine, trientine, zinc, chelation, hepatolenticular");
await p.fill("#f-exc", "rat, mice, in vitro, case report, review");
for (const s of ["#f-title", "#f-inc", "#f-exc"]) await p.dispatchEvent(s, "change");
await p.selectOption("#f-sort", "relevance");
await p.evaluate(() => document.activeElement && document.activeElement.blur());
await p.keyboard.press("i");          // include the top-scoring record
await p.keyboard.press("3");          // exclude the next one with reason 3 ("Wrong comparator")
await p.waitForTimeout(300);
{ const card = await rect(".cardwrap .card"), abs = await rect(".cardwrap .abstract");
  await region("s2_card", { x: card.x, y: card.y, w: card.w, h: abs.y + 5 * 24.3 + 14 - card.y });   // header + first five abstract lines
  await region("s2_decide", union(await rect(".cardwrap .decbtns"), await rect(".cardwrap .chips"))); }
meta.step2 = await p.evaluate(() => ({ title: document.querySelector(".cardwrap .ctitle").textContent }));

// 3-5. Realistic ranked screening (reviewer 1: 20 random records, then retrain + 10 top-ranked per round, gold
// labels as decisions; reviewer 2 screens the first 70 of those and disagrees on 5). Same as the paper's figure.
const csv = readFileSync(D + "/wilson_sample.csv", "utf8");
meta.loop = await p.evaluate(([text, gold]) => {
  const api = window.__almScreenpro;
  const recs = api.parse(text, "wilson_sample.csv");
  const base = { title: "Therapies for Wilson disease", incTerms: ["Wilson disease", "penicillamine", "trientine", "zinc", "chelation", "hepatolenticular"],
    excTerms: ["rat", "mice", "in vitro", "case report", "review"] };
  const live = recs.filter((r) => !/-dup$/.test(r.id));
  const order = [];
  const decide = (r) => { r.r1 = { d: gold[r.id] ? "include" : "exclude", reason: "" }; order.push(r.id); };
  live.slice(0, 20).forEach(decide);
  const rounds = [];
  for (let round = 0; round < 30; round++) {
    api.setState({ ...base, records: recs });
    api.mlTrain();
    const st = api.mlStopping();
    rounds.push({ screened: st.screened, found: st.found, buscarP: +st.buscarP.toFixed(4) });
    if (st.buscarP < 0.05) break;
    const und = live.filter((r) => !r.r1 || !r.r1.d).map((r) => [r, api.mlScoreOf(r.id)]).sort((a, b) => b[1] - a[1]);
    und.slice(0, 10).forEach(([r]) => decide(r));
  }
  const byId = Object.fromEntries(live.map((r) => [r.id, r]));
  let flips = 0;
  order.slice(0, 70).forEach((id, k) => {
    const g = gold[id] ? "include" : "exclude";
    let d = g;
    if (flips < 5 && k % 14 === 9) { d = g === "include" ? "exclude" : "include"; flips++; }
    byId[id].r2 = { d, reason: "" };
  });
  api.setState({ ...base, mode: "dual", active: "r1", records: recs });
  return { rounds, decidedR1: order.length };
}, [csv, gold]);
await p.check("#f-dual");
await p.selectOption("#f-filter", "conflict"); await p.waitForTimeout(400);
meta.kappa = await p.evaluate(() => window.__almScreenpro.kappa());
meta.counts = await p.evaluate(() => window.__almScreenpro.counts());
await region("s3_conflicts", await rect("#conflict-panel"));
{ const panel = await rect("#stats", { section: true }), kap = await rect("#kappa");
  const tiles = await p.evaluate(() => { const t = [...document.querySelectorAll("#stats > *")].slice(-2).map((e) => e.getBoundingClientRect()); return Math.min(...t.map((r) => r.top)) + scrollY; });
  await region("s3_kappa", { x: panel.x, y: tiles, w: panel.w, h: kap.y + kap.h - tiles + 18 }, 3); }

// 4. Train & rank (button click), sort by ML relevance
await p.selectOption("#f-filter", "undecided");
await p.click("#btn-train"); await p.waitForTimeout(600);
await p.selectOption("#f-sort", "ml"); await p.waitForTimeout(300);
meta.mlStatus = await p.textContent("#ml-status"); meta.mlPerf = await p.textContent("#ml-perf");
{ const ml = await rect("#btn-train", { section: true }), perf = await rect("#ml-perf");
  const auc = await p.evaluate(() => { const e = document.querySelector("#ml-perf").firstElementChild; const r = e.getBoundingClientRect(); return r.bottom + scrollY; });
  // from the "Train & rank" button down (the panel's intro sentence above it is not part of the figure)
  const btn = await rect("#btn-train");
  await region("s4_ml", { x: ml.x, y: btn.y - 6, w: ml.w, h: auc - btn.y + 10 });
  const card = await rect(".cardwrap .card"), badges = await rect(".cardwrap .badges");
  await region("s4_card", { x: card.x, y: card.y, w: card.w, h: badges.y + badges.h - card.y + 10 });
// 5. Stopping support: the held-out quality + stopping-rule text
  await region("s5_stopping", perf, 3); }

// 6. Exports + hand-off to the PRISMA Flow app (same origin, via localStorage)
await p.evaluate(() => window.scrollTo(0, 0));
const [dl] = await Promise.all([p.waitForEvent("download"), p.click("#btn-export-ris")]);
meta.download = dl.suggestedFilename();
// the toolbar fits on one row only from about 1150 px; capture it at 1400 px (its buttons do not change size)
await p.setViewportSize({ width: 1400, height: 900 }); await p.waitForTimeout(300);
{ const a = await rect("#btn-export-json"), z = await rect("#btn-prisma"); await region("s6_toolbar", union(a, z)); }
await p.click("#btn-prisma"); await p.waitForTimeout(300);
meta.prisma = JSON.parse(await p.evaluate(() => localStorage.getItem("prisma-flow-v1")));
// PRISMA Flow scales its diagram to the window; a wider window makes the diagram the widest region, so it fills
// the figure width (its text size relative to the diagram is fixed by the app: 12 SVG units)
await p.setViewportSize({ width: 1400, height: 900 });
await p.goto(BASE + "/prisma-flow/index.html"); await p.waitForTimeout(1500); await hideOverlays();
{ // the diagram's boxes (the IDENTIFICATION / SCREENING stage labels on the left are cropped away)
  const boxes = await p.evaluate(() => { const s = document.querySelector("svg"), sr = s.getBoundingClientRect();
    const rs = [...s.querySelectorAll("rect")].map((r) => r.getBoundingClientRect()).filter((r) => r.width > 60 && r.height > 20 && r.width < 0.6 * sr.width);
    const x0 = Math.min(...rs.map((r) => r.left)), x1 = Math.max(...rs.map((r) => r.right)), y0 = Math.min(...rs.map((r) => r.top)), y1 = Math.max(...rs.map((r) => r.bottom));
    return { x: x0 + scrollX, y: y0 + scrollY, w: x1 - x0, h: y1 - y0 }; });
  await region("s6_prisma", boxes, 8); }
// guard: no figure may show the outdated description of Naive Bayes as "ASReview's default"
for (const [k, v] of Object.entries(meta.regions)) if (/ASReview.s default/i.test(v.text)) throw new Error(`region ${k} shows "ASReview's default"`);
writeFileSync(`${D}/regions_meta.json`, JSON.stringify(meta, null, 1));
console.log(JSON.stringify({ step1: meta.step1, kappa: meta.kappa, counts: meta.counts, mlPerf: meta.mlPerf, prisma: meta.prisma, regions: Object.keys(meta.regions) }, null, 1).slice(0, 2500));
await b.close();
