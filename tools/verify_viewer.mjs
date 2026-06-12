// Drive Edge headless against the running web app: wait for the xeokit scene,
// click a zone volume, toggle the Energy heatmap, screenshot each step.
// Usage: node tools/verify_viewer.mjs [url] [outPrefix]

import puppeteer from "puppeteer-core";

const url = process.argv[2] || "http://localhost:3000/dashboard";
const prefix = process.argv[3] || (process.env.TEMP + "\\gf_verify");

const browser = await puppeteer.launch({
  executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  headless: "new",
  args: ["--window-size=1480,1000", "--no-first-run"],
  defaultViewport: { width: 1480, height: 1000 },
});

const page = await browser.newPage();
page.on("console", (m) => {
  const t = m.text();
  if (t.includes("[viewer]") || m.type() === "error") console.log("console:", t.slice(0, 180));
});
await page.goto(url, { waitUntil: "networkidle2", timeout: 120000 });
await page.waitForSelector("canvas.viewer-canvas", { timeout: 60000 });
await new Promise((r) => setTimeout(r, 9000));

await page.screenshot({ path: `${prefix}_1_default.png` });
console.log("shot 1: default view");

// click the centre of the large open-office block
const canvas = await page.$("canvas.viewer-canvas");
const box = await canvas.boundingBox();
await page.mouse.click(box.x + box.width * 0.38, box.y + box.height * 0.47);
await new Promise((r) => setTimeout(r, 2500));
await page.screenshot({ path: `${prefix}_2_picked.png` });
const selected = await page.evaluate(() =>
  document.querySelector("h3")?.textContent || "");
console.log("shot 2: after pick — inspector shows:",
  await page.evaluate(() => {
    const panels = [...document.querySelectorAll("h3")];
    return panels.map((p) => p.textContent).join(" | ");
  }));

// switch to Energy heatmap
await page.evaluate(() => {
  const btn = [...document.querySelectorAll("button")]
    .find((b) => b.textContent?.trim() === "Energy");
  btn?.click();
});
await new Promise((r) => setTimeout(r, 2000));
await page.screenshot({ path: `${prefix}_3_energy.png` });
console.log("shot 3: energy heatmap");

await browser.close();
