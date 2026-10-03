// Screenshots of Screen (usage: node capture.mjs <work-dir with wilson_sample.csv + gold.json> <out-dir>)
// Needs Playwright 1.59.1 and an installed Google Chrome (channel "chrome").
// Screenshots of Screen for the paper's Operation section (Chrome headless, 1400x900, light theme).
import { chromium } from "playwright";
import { readFileSync, writeFileSync } from "fs";
const [D, OUT] = [process.argv[2], process.argv[3]];
import { pathToFileURL, fileURLToPath } from "url";
import { dirname, join } from "path";
const APP = pathToFileURL(join(dirname(fileURLToPath(import.meta.url)), "..", "..", "app", "screen", "index.html")).href;
const gold = JSON.parse(readFileSync(D + "/gold.json", "utf8"));
const b = await chromium.launch({ channel: "chrome" });
const ctx = await b.newContext({ viewport: { width: 1400, height: 900 }, colorScheme: "light", deviceScaleFactor: 2, acceptDownloads: true });
const p = await ctx.newPage();
const boxes = {};
async function fullWithBoxes(name, sels) {
  await p.evaluate(() => window.scrollTo(0, 0)); await p.waitForTimeout(250);
  await p.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  boxes[name] = await p.evaluate((sels) => Object.fromEntries(Object.entries(sels).map(([k, s]) => {
    let e = document.querySelector(s.css); for (let i = 0; i < (s.up || 0); i++) e = e.parentElement; if (s.section) e = e.closest("section");
    const r = e.getBoundingClientRect(); return [k, [r.left + scrollX, r.top + scrollY, r.width, r.height].map((v) => Math.round(v * 2))];
  })), sels);
}

const log = {};
await p.goto(APP); await p.evaluate(() => localStorage.clear()); await p.reload();
const collapse = () => p.evaluate(() => { const d = document.querySelector("details.alm-task"); if (d) d.open = false; });
const top = async () => { await p.evaluate(() => window.scrollTo(0, 0)); await p.waitForTimeout(350); };
const el = async (sel, name) => { await p.locator(sel).first().scrollIntoViewIfNeeded(); await p.waitForTimeout(250); await p.locator(sel).first().screenshot({ path: `${OUT}/${name}.png` }); };
await collapse();

// 1. Import via the real file input + re-run de-duplication, then view the flagged duplicates
await p.setInputFiles("#file-import", D + "/wilson_sample.csv");
await p.waitForTimeout(500);
log.importToast = await p.textContent(".toast, #toast").catch(() => null);
await p.click("#btn-dedup");
await p.selectOption("#f-filter", "duplicate");
await top(); await p.screenshot({ path: `${OUT}/step1.png` });
log.afterImport = await p.evaluate(() => window.__almScreenpro.counts());

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
await top(); await p.screenshot({ path: `${OUT}/step2.png` });

// 3-5. Realistic ranked screening: reviewer 1 screens 20 random records, then repeatedly
// retrains and screens the 10 top-ranked undecided records (decisions = the dataset's gold
// labels). Reviewer 2 independently screens the first 70 of those records.
const csv = readFileSync(D + "/wilson_sample.csv", "utf8");
log.loop = await p.evaluate(([text, gold]) => {
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
    const t = api.mlTrain();
    const st = api.mlStopping();
    rounds.push({ screened: st.screened, found: st.found, buscarP: +st.buscarP.toFixed(4) });
    if (st.buscarP < 0.05) break;
    const und = live.filter((r) => !r.r1 || !r.r1.d).map((r) => [r, api.mlScoreOf(r.id)]).sort((a, b) => b[1] - a[1]);
    und.slice(0, 10).forEach(([r]) => decide(r));
  }
  // reviewer 2 screens the first 70 records reviewer 1 screened; disagrees on 5
  const byId = Object.fromEntries(live.map((r) => [r.id, r]));
  let flips = 0;
  order.slice(0, 70).forEach((id, k) => {
    const g = gold[id] ? "include" : "exclude";
    let d = g;
    if (flips < 5 && k % 14 === 9) { d = g === "include" ? "exclude" : "include"; flips++; }
    byId[id].r2 = { d, reason: "" };
  });
  api.setState({ ...base, mode: "dual", active: "r1", records: recs });
  return { rounds, decidedR1: order.length, foundTotal: Object.values(gold).filter(Boolean).length };
}, [csv, gold]);
// sync the visible controls with the loaded project (dual mode, terms) through the real UI
await p.check("#f-dual");
await p.selectOption("#f-filter", "conflict");
await p.waitForTimeout(400);
log.kappa = await p.evaluate(() => window.__almScreenpro.kappa());
log.counts = await p.evaluate(() => window.__almScreenpro.counts());
await el("#conflict-panel", "step3_right");
await el("#stats", "step3_left_stats"); await el("#kappa", "step3_left_kappa");
await p.locator("#stats").first().locator("xpath=ancestor::section[1]").screenshot({ path: `${OUT}/step3_left.png` });
await p.locator("#f-dual").locator("xpath=ancestor::section[1]").screenshot({ path: `${OUT}/step3_reviewers.png` });
await p.locator(".cardwrap").first().screenshot({ path: `${OUT}/step3_card.png` });
await fullWithBoxes("full3", { reviewers: { css: "#f-dual", section: 1 }, progress: { css: "#stats", section: 1 }, conflicts: { css: "#conflict-panel" }, card: { css: ".cardwrap" } });
await top(); await p.screenshot({ path: `${OUT}/step3_top.png` });

// 4. Train & rank (button click), sort by ML relevance
await p.selectOption("#f-filter", "undecided");
await p.click("#btn-train");
await p.waitForTimeout(600);
await p.selectOption("#f-sort", "ml");
await p.waitForTimeout(300);
log.mlStatus = await p.textContent("#ml-status");
log.mlPerf = await p.textContent("#ml-perf");
log.topTerms = await p.evaluate(() => window.__almScreenpro.mlTopTerms());
await p.locator("#btn-train").locator("xpath=ancestor::section[1]").screenshot({ path: `${OUT}/step4_left.png` });
await fullWithBoxes("full4", { ml: { css: "#btn-train", section: 1 }, mlterms: { css: "#ml-terms" }, mlperf: { css: "#ml-perf" }, mlstatus: { css: "#ml-status" }, card: { css: ".cardwrap" }, progress: { css: "#stats" }, kappa: { css: "#kappa" } });
await top(); await p.screenshot({ path: `${OUT}/step4_top.png` });
await p.locator(".cardwrap").first().screenshot({ path: `${OUT}/step4_right.png` });

// 6. Exports + send counts to PRISMA Flow
await top();
const [dl] = await Promise.all([p.waitForEvent("download"), p.click("#btn-export-ris")]);
log.download = dl.suggestedFilename();
const [dj] = await Promise.all([p.waitForEvent("download"), p.click("#btn-export-json")]);
await dj.saveAs(`${OUT}/project.json`);
await p.click("#btn-prisma");
await p.waitForTimeout(200);
await p.screenshot({ path: `${OUT}/step6.png` });
log.prisma = JSON.parse(await p.evaluate(() => localStorage.getItem("prisma-flow-v1")));
writeFileSync(`${OUT}/boxes.json`, JSON.stringify(boxes, null, 1));
writeFileSync(`${OUT}/shots_log.json`, JSON.stringify(log, null, 1));
console.log(JSON.stringify(log, null, 1).slice(0, 3000));
await b.close();
