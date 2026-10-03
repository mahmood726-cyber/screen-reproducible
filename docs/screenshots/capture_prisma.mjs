// Step 6: load the project exported by capture.mjs into Screen served from a local allmeta checkout,
// push counts to PRISMA Flow and capture both.  usage: node capture_prisma.mjs <work-dir> http://127.0.0.1:8091
// (serve allmeta with: python -m http.server 8091 from the allmeta repository root)
import { chromium } from "playwright";
import { writeFileSync } from "fs";
const [D, BASE] = [process.argv[2], process.argv[3]];
const b = await chromium.launch({ channel: "chrome" });
const ctx = await b.newContext({ viewport: { width: 1400, height: 900 }, colorScheme: "light", deviceScaleFactor: 2 });
const p = await ctx.newPage();
const boxes = {};
async function fullWithBoxes(name, sels) {
  await p.evaluate(() => window.scrollTo(0, 0)); await p.waitForTimeout(250);
  await p.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  boxes[name] = await p.evaluate((sels) => Object.fromEntries(Object.entries(sels).map(([k, s]) => {
    let e = document.querySelector(s.css); for (let i = 0; i < (s.up || 0); i++) e = e.parentElement;
    const r = e.getBoundingClientRect(); return [k, [r.left + scrollX, r.top + scrollY, r.width, r.height].map((v) => Math.round(v * 2))];
  })), sels);
}

const logs = []; p.on("console", (m) => logs.push(m.text()));
await p.goto(BASE + "/screen/index.html"); await p.evaluate(() => localStorage.clear()); await p.reload();
await p.evaluate(() => { const d = document.querySelector("details.alm-task"); if (d) d.open = false; });
const proj = JSON.parse((await import("fs")).readFileSync(D + "/project.json", "utf8"));
await p.evaluate((s) => window.__almScreenpro.setState(s), proj);
await p.fill("#f-title", proj.title); await p.check("#f-dual");
await p.waitForTimeout(2500);
const counts = await p.evaluate(() => window.__almScreenpro.counts());
await p.click("#btn-prisma");
await p.waitForTimeout(300);
await p.evaluate(() => window.scrollTo(0, 0));
await p.screenshot({ path: `${D}/step6_screen.png` });
const OUT = D;
await fullWithBoxes("full6", { toolbar: { css: "#btn-import", up: 1 } });
const payload = JSON.parse(await p.evaluate(() => localStorage.getItem("prisma-flow-v1")));
await p.goto(BASE + "/prisma-flow/index.html");
await p.waitForTimeout(1500);
await p.screenshot({ path: `${D}/step6_prisma_viewport.png` });
const svg = p.locator("svg").first();
await svg.scrollIntoViewIfNeeded();
await svg.screenshot({ path: `${D}/step6_prisma_svg.png` });
writeFileSync(`${D}/boxes6.json`, JSON.stringify(boxes, null, 1));
writeFileSync(`${D}/step6_log.json`, JSON.stringify({ counts, payload, consoleToast: logs }, null, 1));
console.log(JSON.stringify({ counts, payload, consoleToast: logs }, null, 1));
await b.close();
