import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

const venvPython = path.join(process.cwd(), ".venv", process.platform === "win32" ? "Scripts" : "bin", process.platform === "win32" ? "python.exe" : "python");
const python = process.env.PYTHON || (existsSync(venvPython) ? venvPython : process.platform === "win32" ? "python" : "python3");
const env = {
  ...process.env,
  MODEL_PROVIDER: "demo",
  API_KEYS: "",
  GEMINI_API_KEY: "",
  TAVILY_API_KEY: "",
  MIN_FREE_MB: "1",
  MAX_UPLOAD_MB: "25",
  CORS_ORIGINS: "http://127.0.0.1:3000",
  IMAGE_PLACEHOLDERS: "false",
  PORT: "8010",
};

const child = spawn(
  python,
  ["-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8010"],
  { env, stdio: "inherit", windowsHide: true },
);

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => child.kill(signal));
}

child.on("exit", (code, signal) => {
  process.exitCode = code ?? (signal ? 1 : 0);
});
child.on("error", (error) => {
  console.error(`Could not start the demo backend: ${error.message}`);
  process.exitCode = 1;
});
