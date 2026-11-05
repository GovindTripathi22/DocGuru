import { cp, mkdir, stat } from "node:fs/promises";
import path from "node:path";

const root = process.cwd();
const standaloneDir = path.join(root, ".next", "standalone");
const staticDir = path.join(root, ".next", "static");

await stat(path.join(standaloneDir, "server.js"));
await stat(staticDir);
await mkdir(path.join(standaloneDir, ".next"), { recursive: true });
await cp(staticDir, path.join(standaloneDir, ".next", "static"), { recursive: true, force: true });

const publicDir = path.join(root, "public");
try {
  await stat(publicDir);
  await cp(publicDir, path.join(standaloneDir, "public"), { recursive: true, force: true });
} catch (error) {
  if (error?.code !== "ENOENT") throw error;
}

console.log("Prepared standalone server with static and public assets.");
