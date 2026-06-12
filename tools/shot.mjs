// Quick page screenshot helper: node tools/shot.mjs <url> <out.png> [waitMs]
import puppeteer from "puppeteer-core";

const [url, out, waitMs = "6000"] = process.argv.slice(2);
const browser = await puppeteer.launch({
  executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  headless: "new",
  args: ["--window-size=1480,1000", "--no-first-run"],
  defaultViewport: { width: 1480, height: 1000 },
});
const page = await browser.newPage();
page.on("console", (m) => { if (m.type() === "error") console.log("err:", m.text().slice(0, 150)); });
await page.goto(url, { waitUntil: "networkidle2", timeout: 120000 });
await new Promise((r) => setTimeout(r, Number(waitMs)));
await page.screenshot({ path: out, fullPage: false });
console.log("saved", out);
await browser.close();
