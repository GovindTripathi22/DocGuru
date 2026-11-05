import { spawnSync, spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

const root = process.cwd();
const venvPython = path.join(root, ".venv", process.platform === "win32" ? "Scripts" : "bin", process.platform === "win32" ? "python.exe" : "python");
const pythonCommand = process.env.PYTHON || (existsSync(venvPython) ? venvPython : process.platform === "win32" ? "python" : "python3");
const fixture = spawnSync(pythonCommand, ["scripts/create_e2e_fixture.py"], { cwd: root, stdio: "inherit" });
if (fixture.error || fixture.status !== 0) {
  if (fixture.error) console.error(fixture.error.message);
  process.exit(fixture.status ?? 1);
}

const command = process.platform === "win32" ? "npx.cmd" : "npx";
const runner = spawn(command, ["playwright", "test"], {
  cwd: root,
  stdio: "inherit",
  windowsHide: true,
  shell: process.platform === "win32",
  env: {
    ...process.env,
    BACKEND_URL: "http://127.0.0.1:8010",
    SESSION_SECRET: "playwright-session-secret-for-local-demo-only",
  },
});

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => runner.kill(signal));
}
runner.on("error", (error) => {
  console.error(`Could not start Playwright: ${error.message}`);
  process.exitCode = 1;
});
runner.on("exit", (code, signal) => {
  process.exitCode = code ?? (signal ? 1 : 0);
});
