// Verify discipline layers overlay + space picking.
import puppeteer from "puppeteer-core";
const url = process.argv[2] || "http://localhost:3000/dashboard";
const prefix = process.argv[3] || (process.env.TEMP + "\\gfl");
const browser = await puppeteer.launch({
  executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  headless: "new", args: ["--window-size=1480,1000", "--no-first-run"],
  defaultViewport: { width: 1480, height: 1000 },
});
const page = await browser.newPage();
await page.goto(url, { waitUntil: "networkidle2", timeout: 120000 });
await page.waitForSelector("canvas.viewer-canvas", { timeout: 60000 });
await new Promise((r) => setTimeout(r, 9000));

async function setLayer(label, on) {
  await page.evaluate((label, on) => {
    const lbls = [...document.querySelectorAll("label")];
    const lab = lbls.find((l) => l.textContent?.includes(label));
    const cb = lab?.querySelector('input[type=checkbox]');
    if (cb && cb.checked !== on) cb.click();
  }, label, on);
  await new Promise((r) => setTimeout(r, 1500));
}

// Structural overlay
await setLayer("Structural", true);
await page.screenshot({ path: `${prefix}_structural.png` });
await setLayer("Structural", false);

// HVAC overlay
await setLayer("HVAC", true);
await page.screenshot({ path: `${prefix}_hvac.png` });
await setLayer("HVAC", false);

// Pick a space (click left-lower area where spaces peek out)
const canvas = await page.$("canvas.viewer-canvas");
const box = await canvas.boundingBox();
await page.mouse.click(box.x + box.width * 0.45, box.y + box.height * 0.62);
await new Promise((r) => setTimeout(r, 2500));
const inspector = await page.evaluate(() =>
  [...document.querySelectorAll("h3")].map((h) => h.textContent).join(" | "));
console.log("inspector after space pick:", inspector);
await page.screenshot({ path: `${prefix}_pick.png` });
await browser.close();
