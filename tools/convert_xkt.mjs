// Convert per-layer GLB assets to xeokit XKT.
// Usage: node tools/convert_xkt.mjs <asset_dir>
// <asset_dir> must contain glb/<layer>.glb and metadata/<layer>_metadata.json;
// writes xkt/<layer>.xkt.

import { convert2xkt } from "@xeokit/xeokit-convert";
import fs from "node:fs";
import path from "node:path";

const assetDir = process.argv[2];
if (!assetDir) {
  console.error("usage: node convert_xkt.mjs <asset_dir>");
  process.exit(1);
}

const glbDir = path.join(assetDir, "glb");
const xktDir = path.join(assetDir, "xkt");
const metaDir = path.join(assetDir, "metadata");
fs.mkdirSync(xktDir, { recursive: true });

const layers = fs.readdirSync(glbDir).filter((f) => f.endsWith(".glb"));
let failed = 0;

for (const file of layers) {
  const layer = path.basename(file, ".glb");
  const source = path.join(glbDir, file);
  const metaModelSource = path.join(metaDir, `${layer}_metadata.json`);
  const output = path.join(xktDir, `${layer}.xkt`);
  try {
    await convert2xkt({
      source,
      metaModelSource: fs.existsSync(metaModelSource) ? metaModelSource : undefined,
      output,
      log: () => {},
    });
    const kb = Math.round(fs.statSync(output).size / 1024);
    console.log(`  converted ${layer}.glb -> ${layer}.xkt (${kb} KB)`);
  } catch (err) {
    failed += 1;
    console.error(`  FAILED ${layer}: ${err.message || err}`);
  }
}

process.exit(failed > 0 ? 1 : 0);
