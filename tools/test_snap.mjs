import puppeteer from "puppeteer-core";
const base = process.argv[2] || "http://localhost:3000/";
const { webSocketDebuggerUrl } = await (await fetch("http://localhost:9222/json/version")).json();
const browser = await puppeteer.connect({ browserWSEndpoint: webSocketDebuggerUrl, defaultViewport: { width: 1480, height: 940 } });
const page = await browser.newPage();
await page.goto(base, { waitUntil: "domcontentloaded", timeout: 120000 });
await new Promise((r) => setTimeout(r, 9000));

const vh = await page.evaluate(() => window.innerHeight);
const read = () => page.evaluate(() => Math.round(window.scrollY));
const snapType = await page.evaluate(() => getComputedStyle(document.documentElement).scrollSnapType);
console.log("innerHeight", vh, "snapType(html)", snapType, "start", await read());

// keyboard scroll (native scroll path, exercises snap)
await page.evaluate(() => document.body.focus());
await page.keyboard.press("PageDown");
await new Promise((r) => setTimeout(r, 1500));
const a = await read();
console.log("PageDown x1:", a, "=> section", (a / vh).toFixed(2));

await page.keyboard.press("PageDown");
await page.keyboard.press("PageDown");
await new Promise((r) => setTimeout(r, 1700));
const b = await read();
console.log("PageDown x3 total:", b, "=> section", (b / vh).toFixed(2));

// partial scroll then check it snaps to a boundary
await page.evaluate(() => window.scrollBy(0, 220));
await new Promise((r) => setTimeout(r, 1600));
const c = await read();
console.log("after +220 nudge (should snap to a section):", c, "=> section", (c / vh).toFixed(2), "snapped?", Math.abs(c % vh) < 6 || Math.abs((c % vh) - vh) < 6);

await page.close();
await browser.disconnect();
