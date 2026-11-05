import { concurrently } from "concurrently";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { spawn } from "node:child_process";

const root = process.cwd();
const envPath = path.join(root, ".env");
const venvDir = path.join(root, ".venv");
const venvBin = path.join(venvDir, process.platform === "win32" ? "Scripts" : "bin");
const venvPython = path.join(venvBin, process.platform === "win32" ? "python.exe" : "python");

for (const [pathToCheck, explanation] of [
  [path.join(root, "node_modules"), "Node packages are missing. Run `npm run setup` first."],
  [envPath, "The .env file is missing. Run `npm run setup` to create it from .env.example."],
  [venvPython, "The project Python environment is missing. Run `npm run setup` first."],
]) {
  if (!existsSync(pathToCheck)) {
    console.error(explanation);
    process.exit(1);
  }
}

const fileEnv = Object.fromEntries(
  readFileSync(envPath, "utf8")
    .split(/\r?\n/u)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#") && line.includes("="))
    .map((line) => {
      const index = line.indexOf("=");
      return [line.slice(0, index).trim(), line.slice(index + 1).trim().replace(/^(["'])(.*)\1$/u, "$2")];
    }),
);
const env = { ...fileEnv, ...process.env };
env.PATH = `${venvBin}${path.delimiter}${env.PATH || ""}`;
env.VIRTUAL_ENV = venvDir;

if (process.argv.includes("--check")) {
  console.log("Local development prerequisites are present.");
  process.exit(0);
}

let ollamaProcess;
if (env.MODEL_PROVIDER === "ollama") {
  const endpoint = (env.MODEL_ENDPOINT || "http://127.0.0.1:11434").replace(/\/$/u, "");
  let reachable = false;
  try {
    const response = await fetch(`${endpoint}/api/tags`, { signal: AbortSignal.timeout(1500) });
    reachable = response.ok;
  } catch {
    reachable = false;
  }

  if (!reachable) {
    console.log("MODEL_PROVIDER=ollama; starting the local Ollama service...");
    ollamaProcess = spawn("ollama", ["serve"], { env, stdio: "inherit", windowsHide: true });
    for (let attempt = 0; attempt < 20; attempt += 1) {
      if (ollamaProcess.exitCode !== null) {
        console.error("Ollama exited before becoming ready. Install Ollama or start it manually.");
        process.exit(1);
      }
      try {
        const response = await fetch(`${endpoint}/api/tags`, { signal: AbortSignal.timeout(1000) });
        if (response.ok) {
          reachable = true;
          break;
        }
      } catch {
        // Keep waiting for Ollama's local API to bind.
      }
      await delay(500);
    }
    if (!reachable) {
      ollamaProcess.kill();
      console.error("Ollama did not become ready within 10 seconds.");
      process.exit(1);
    }
  }
}

const { result } = concurrently(
  [
    { command: "npm:dev:backend", name: "backend", env },
    { command: "npm:dev", name: "frontend", env },
  ],
  { cwd: root, prefix: "name", prefixColors: ["blue", "green"], killOthersOn: ["failure", "success"] },
);

try {
  await result;
} catch (closed) {
  const failures = Array.isArray(closed) ? closed.filter((item) => item.exitCode && item.exitCode !== 0) : [];
  process.exitCode = failures.length ? failures[0].exitCode || 1 : 0;
} finally {
  if (ollamaProcess && ollamaProcess.exitCode === null) ollamaProcess.kill();
}
