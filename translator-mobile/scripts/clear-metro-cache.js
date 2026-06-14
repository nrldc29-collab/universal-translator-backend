#!/usr/bin/env node
/** Remove corrupted Metro caches (fixes "Unable to deserialize cloned data"). */
const fs = require("fs");
const os = require("os");
const path = require("path");

const cacheRoots = [
  path.join(process.cwd(), "node_modules", ".cache", "metro"),
  path.join(process.cwd(), "node_modules", ".cache", "metro-file-map"),
  path.join(process.cwd(), ".metro"),
  path.join(os.tmpdir(), "anai-translator-metro-cache"),
];

for (const root of cacheRoots) {
  if (!fs.existsSync(root)) continue;
  fs.rmSync(root, { recursive: true, force: true });
  process.stdout.write(`Cleared ${root}\n`);
}
