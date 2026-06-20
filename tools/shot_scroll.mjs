import puppeteer from "puppeteer-core";
const base = process.argv[2] || "http://localhost:3000/";
const prefix = process.argv[3] || (process.env.TEMP + "\\gfscroll");
const { webSocketDebuggerUrl } = await (await fetch("http://localhost:9222/json/version")).json();
const browser = await puppeteer.connect({ browserWSEndpoint: webSocketDebuggerUrl, defaultViewport: { width: 1480, height: 940 } });
const page = await browser.newPage();
const errs = [];
page.on("pageerror", (e) => errs.push(String(e).slice(0, 200)));
page.on("console", (m) => { if (m.type() === "error") errs.push("c:" + m.text().slice(0, 160)); });

await page.goto(base, { waitUntil: "domcontentloaded", timeout: 120000 });
await new Promise((r) => setTimeout(r, 11000)); // hero textures

// disable snap so we can sample arbitrary scroll progress for the scrub checks
await page.evaluate(() => { document.documentElement.style.scrollSnapType = "none"; });

async function at(p, name, wait = 1500) {
  await page.evaluate((p) => window.scrollTo(0, p * window.innerHeight), p);
  await new Promise((r) => setTimeout(r, wait));
  await page.screenshot({ path: `${prefix}_${name}.png` });
  console.log(name);
}

await page.screenshot({ path: `${prefix}_p00_hero.png` }); console.log("hero");
await at(0.5, "p05_hero_to_global", 1400);
await at(1.0, "p10_global");
await at(1.5, "p15_global_to_loads", 1800);
await at(2.0, "p20_loads", 2200);
await at(2.5, "p25_pie_mid", 1800);
await at(3.0, "p30_hanoi", 1800);
await at(4.0, "p40_elnino");
await at(6.0, "p60_cta");

// dark mode at hero
await at(0.0, "back_hero", 800);
await page.evaluate(() => { const b=[...document.querySelectorAll("nav button")]; b[b.length-1]?.click(); });
await new Promise((r) => setTimeout(r, 3500));
await page.screenshot({ path: `${prefix}_p00_dark_hero.png` }); console.log("dark hero");
await at(2.0, "p20_dark_loads", 2200);

console.log("ERRORS", errs.length, errs.slice(0, 20));
await page.close();
await browser.disconnect();
