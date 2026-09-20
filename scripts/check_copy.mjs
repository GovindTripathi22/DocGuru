#!/usr/bin/env node
/**
 * Copy and Hype Phrase Validator (FE-01/02/03/04).
 * Enforces that no banned assurance strings exist in client-facing frontend source files.
 */

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SRC_DIR = path.resolve(__dirname, "../src");

const BANNED_STRINGS = [
  "100%",
  "Zero Theme Drift",
  "Exact Inheritance Verified",
  "Sacred",
  "STYLE LOCK ENFORCED",
  "Running on GPU",
  "Local Engine",
  "AetherStudio",
  "AlphaGo",
  "Fallback Engine",
];

let violations = 0;

function scanDir(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      scanDir(fullPath);
    } else if (/\.(tsx|ts|jsx|js|html|css)$/.test(entry.name)) {
      const content = fs.readFileSync(fullPath, "utf-8");
      for (const banned of BANNED_STRINGS) {
        if (content.toLowerCase().includes(banned.toLowerCase())) {
          console.error(`BANNED STRING DETECTED: "${banned}" in ${fullPath}`);
          violations++;
        }
      }
    }
  }
}

scanDir(SRC_DIR);

if (violations > 0) {
  console.error(`FAILED: Found ${violations} banned hype phrases in src/.`);
  process.exit(1);
} else {
  console.log("SUCCESS: Zero banned hype phrases detected in frontend copy.");
  process.exit(0);
}
