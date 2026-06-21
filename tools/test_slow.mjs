import puppeteer from "puppeteer-core";
const base = process.argv[2] || "http://localhost:3000/";
const { webSocketDebuggerUrl } = await (await fetch("http://localhost:9222/json/version")).json();
const browser = await puppeteer.connect({ browserWSEndpoint: webSocketDebuggerUrl, defaultViewport: { width: 1480, height: 940 } });
const page = await browser.newPage();
await page.emulateMediaFeatures([{ name: "prefers-reduced-motion", value: "no-preference" }]);
await page.goto(base, { waitUntil: "domcontentloaded", timeout: 120000 });
await new Promise((r) => setTimeout(r, 9000));
const vh = await page.evaluate(() => window.innerHeight);
const y = () => page.evaluate(() => Math.round(window.scrollY));

await page.evaluate(() => document.body.focus());
console.log("start", await y());
await page.keyboard.press("ArrowDown");      // should ease toward section 1 (940) over ~1.15s
await new Promise((r) => setTimeout(r, 300));
const mid = await y();
await new Promise((r) => setTimeout(r, 1100));
const end = await y();
console.log("vh", vh, "@300ms", mid, "(eased, 0<mid<vh:", mid > 20 && mid < vh - 20, ")", "@1.4s", end, "=> section", (end / vh).toFixed(2));

// nav dot click should also glide slowly
await page.evaluate(() => { const d=[...document.querySelectorAll(".gf-dot")]; d[3]?.click(); });
await new Promise((r) => setTimeout(r, 300));
const m2 = await y();
await new Promise((r) => setTimeout(r, 1200));
const e2 = await y();
console.log("dot->3 @300ms", m2, "@1.5s", e2, "=> section", (e2 / vh).toFixed(2));

await page.close();
await browser.disconnect();
