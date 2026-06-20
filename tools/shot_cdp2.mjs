// Connect to a running Edge (remote-debugging-port=9222) and capture the landing.
import puppeteer from "puppeteer-core";

const base = process.argv[2] || "http://localhost:3000/";
const prefix = process.argv[3] || (process.env.TEMP + "\\gfl2");

const { webSocketDebuggerUrl } = await (await fetch("http://localhost:9222/json/version")).json();
const browser = await puppeteer.connect({
  browserWSEndpoint: webSocketDebuggerUrl,
  defaultViewport: { width: 1480, height: 940 },
});

const page = await browser.newPage();
const errs = [];
page.on("console", (m) => { if (m.type() === "error") errs.push(m.text().slice(0, 200)); });
page.on("pageerror", (e) => errs.push("PAGEERR: " + String(e).slice(0, 200)));

await page.goto(base, { waitUntil: "domcontentloaded", timeout: 120000 });
await new Promise((r) => setTimeout(r, 13000)); // hero: 8k texture + first reveal
await page.screenshot({ path: `${prefix}_1_hero.png` });
console.log("hero");

async function down(name, wait = 3000) {
  await page.keyboard.press("ArrowDown");
  await new Promise((r) => setTimeout(r, wait));
  await page.screenshot({ path: `${prefix}_${name}.png` });
  console.log(name);
}
await down("2_global");
await down("3_loads", 4500);   // building grows
await down("4_hanoi", 3500);   // pie flip
await down("5_elnino");
await down("6_problem");
await down("7_cta");

// dark mode toggle (last nav button), back to hero
await page.evaluate(() => {
  const btns = [...document.querySelectorAll("nav button")];
  btns[btns.length - 1]?.click();
});
await new Promise((r) => setTimeout(r, 1200));
await page.keyboard.press("Home");
await new Promise((r) => setTimeout(r, 4000));
await page.screenshot({ path: `${prefix}_8_dark_hero.png` });
console.log("dark hero");
// dark section 2 (building energy)
await page.keyboard.press("ArrowDown");
await new Promise((r) => setTimeout(r, 1800));
await page.keyboard.press("ArrowDown");
await new Promise((r) => setTimeout(r, 4500));
await page.screenshot({ path: `${prefix}_9_dark_loads.png` });
console.log("dark loads");

console.log("CONSOLE ERRORS:", errs.length);
for (const e of errs.slice(0, 25)) console.log("  -", e);

await page.close();
await browser.disconnect();
