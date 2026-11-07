import { randomBytes } from "node:crypto";
import { spawnSync } from "node:child_process";
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";

const root = process.cwd();
const python = process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");
const venv = path.join(root, ".venv");
const venvPython = path.join(venv, process.platform === "win32" ? "Scripts" : "bin", process.platform === "win32" ? "python.exe" : "python");

function run(command, args) {
  const result = spawnSync(command, args, { cwd: root, stdio: "inherit", shell: process.platform === "win32" });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}

if (!existsSync(path.join(root, "package-lock.json"))) {
  throw new Error("package-lock.json is missing; run setup from the project root.");
}

console.log("Installing the Node.js dependencies...");
run(process.platform === "win32" ? "npm.cmd" : "npm", ["ci"]);

console.log("Creating the project Python environment...");
mkdirSync(venv, { recursive: true });
if (!existsSync(venvPython)) run(python, ["-m", "venv", venv]);
run(venvPython, ["-m", "pip", "install", "--upgrade", "pip"]);
const reqFile = existsSync(path.join(root, "backend/requirements-dev.lock"))
  ? "backend/requirements-dev.lock"
  : "backend/requirements-dev.txt";
run(venvPython, ["-m", "pip", "install", "-r", reqFile]);

const envFile = path.join(root, ".env");
if (!existsSync(envFile)) {
  copyFileSync(path.join(root, ".env.example"), envFile);
  console.log("Created .env from .env.example. Review MODEL_PROVIDER and add provider keys before live generation.");
} else {
  console.log("Kept the existing .env file unchanged.");
}

const envText = readFileSync(envFile, "utf8");
const sessionSecret = "SESSION_SECRET=" + randomBytes(32).toString("base64url");
if (!/^SESSION_SECRET=/mu.test(envText)) {
  writeFileSync(
    envFile,
    envText + (envText.endsWith("\n") ? "" : "\n") + sessionSecret + "\n",
    "utf8",
  );
  console.log("Added a generated SESSION_SECRET to .env; existing settings were kept.");
} else if (envText.includes("SESSION_SECRET=replace-with-random-32-byte-secret")) {
  writeFileSync(
    envFile,
    envText.replace("SESSION_SECRET=replace-with-random-32-byte-secret", sessionSecret),
    "utf8",
  );
  console.log("Generated a local SESSION_SECRET in .env.");
}

console.log("Setup complete. Start both services with npm run dev:all.");
