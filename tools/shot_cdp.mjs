// Connect to an already-running Edge (remote-debugging-port=9222) and drive the
// landing. Bypasses puppeteer's broken launch handshake with new Edge builds.
import puppeteer from "puppeteer-core";

const base = process.argv[2] || "http://localhost:3000/";
const prefix = process.argv[3] || (process.env.TEMP + "\\gflanding");

const res = await fetch("http://localhost:9222/json/version");
const { webSocketDebuggerUrl } = await res.json();
const browser = await puppeteer.connect({ browserWSEndpoint: webSocketDebuggerUrl,
  defaultViewport: { width: 1480, height: 940 } });

const page = await browser.newPage();
page.on("console", (m) => { if (m.type() === "error") console.log("err:", m.text().slice(0, 160)); });
await page.goto(base, { waitUntil: "networkidle2", timeout: 120000 });
await new Promise((r) => setTimeout(r, 6000));
await page.screenshot({ path: `${prefix}_1_hero.png` });
console.log("hero");

async function key(k, wait = 1800) {
  await page.keyboard.press(k);
  await new Promise((r) => setTimeout(r, wait));
}
const names = ["2_global", "3_loads", "4_hanoi", "5_elnino", "6_problem", "7_cta"];
for (const n of names) { await key("ArrowDown"); await page.screenshot({ path: `${prefix}_${n}.png` }); }
console.log("sections");

await page.evaluate(() => {
  const btns = [...document.querySelectorAll("nav button")];
  btns[btns.length - 1]?.click();
});
await new Promise((r) => setTimeout(r, 1500));
await key("Home", 2500);
await page.screenshot({ path: `${prefix}_8_dark.png` });
console.log("dark");

await page.close();
await browser.disconnect();
