import puppeteer from "puppeteer-core";
const base = process.argv[2] || "http://localhost:3000/";
const prefix = process.argv[3] || (process.env.TEMP + "\\gfr");
const { webSocketDebuggerUrl } = await (await fetch("http://localhost:9222/json/version")).json();
const browser = await puppeteer.connect({ browserWSEndpoint: webSocketDebuggerUrl, defaultViewport: { width: 1480, height: 940 } });
const page = await browser.newPage();
const errs = [];
page.on("pageerror", (e) => errs.push(String(e).slice(0, 200)));
page.on("console", (m) => { if (m.type() === "error") errs.push("c:" + m.text().slice(0, 160)); });

await page.goto(base, { waitUntil: "domcontentloaded", timeout: 120000 });
await new Promise((r) => setTimeout(r, 11000));

async function at(i, name, wait = 1700) {
  await page.evaluate((i) => window.scrollTo(0, i * window.innerHeight), i);
  await new Promise((r) => setTimeout(r, wait));
  await page.screenshot({ path: `${prefix}_${name}.png` });
  console.log(name);
}

await page.screenshot({ path: `${prefix}_hero.png` }); console.log("hero");
await at(1, "global_left");
await at(2, "loads", 2000);

// hover the pie chart -> info popup
await page.hover('img[alt^="Energy share"]');
await new Promise((r) => setTimeout(r, 900));
await page.screenshot({ path: `${prefix}_loads_pie_hover.png` }); console.log("pie hover");
// hover the bar chart
await page.hover('img[alt^="Hanoi commercial"]');
await new Promise((r) => setTimeout(r, 900));
await page.screenshot({ path: `${prefix}_loads_bar_hover.png` }); console.log("bar hover");

await at(3, "hanoi");

// dark hero
await at(0, "back_hero", 700);
await page.evaluate(() => { const b=[...document.querySelectorAll("nav button")]; b[b.length-1]?.click(); });
await new Promise((r) => setTimeout(r, 3500));
await page.screenshot({ path: `${prefix}_dark_hero.png` }); console.log("dark hero");

console.log("ERRORS", errs.length, errs.slice(0, 15));
await page.close();
await browser.disconnect();
