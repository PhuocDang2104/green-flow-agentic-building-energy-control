// Drive the cinematic landing: screenshot hero, advance sections, toggle dark.
import puppeteer from "puppeteer-core";

const base = process.argv[2] || "http://localhost:3000/";
const prefix = process.argv[3] || (process.env.TEMP + "\\gflanding");

const browser = await puppeteer.launch({
  executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  headless: "new",
  userDataDir: process.env.TEMP + "\\gf_landing_" + Date.now(),
  args: ["--window-size=1480,940", "--no-first-run", "--no-default-browser-check"],
  defaultViewport: { width: 1480, height: 940 },
});
const page = await browser.newPage();
page.on("console", (m) => { if (m.type() === "error") console.log("err:", m.text().slice(0, 160)); });
await page.goto(base, { waitUntil: "networkidle2", timeout: 120000 });
await new Promise((r) => setTimeout(r, 6000)); // earth + first reveal

await page.screenshot({ path: `${prefix}_1_hero.png` });
console.log("hero shot");

async function key(k, times = 1, wait = 1700) {
  for (let i = 0; i < times; i++) {
    await page.keyboard.press(k);
    await new Promise((r) => setTimeout(r, wait));
  }
}

await key("ArrowDown", 1); await page.screenshot({ path: `${prefix}_2_global.png` });
await key("ArrowDown", 1); await page.screenshot({ path: `${prefix}_3_loads.png` });
await key("ArrowDown", 1); await page.screenshot({ path: `${prefix}_4_hanoi.png` });
await key("ArrowDown", 1); await page.screenshot({ path: `${prefix}_5_elnino.png` });
await key("ArrowDown", 1); await page.screenshot({ path: `${prefix}_6_problem.png` });
await key("ArrowDown", 1); await page.screenshot({ path: `${prefix}_7_cta.png` });
console.log("section shots done");

// dark mode toggle (click the theme button in the nav, last button)
await page.evaluate(() => {
  const btns = [...document.querySelectorAll("nav button")];
  btns[btns.length - 1]?.click();
});
await new Promise((r) => setTimeout(r, 1500));
await key("Home", 1, 1500);
await new Promise((r) => setTimeout(r, 2500));
await page.screenshot({ path: `${prefix}_8_dark_hero.png` });
console.log("dark shot done");

await browser.close();
