import { existsSync } from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

const root = process.cwd();
const venvPython = path.join(
  root,
  ".venv",
  process.platform === "win32" ? "Scripts" : "bin",
  process.platform === "win32" ? "python.exe" : "python",
);
const python = process.env.PYTHON || (existsSync(venvPython) ? venvPython : process.platform === "win32" ? "python" : "python3");
const schemaPath = path.join(root, ".task-temp", "openapi.json");
const outputPath = path.join(root, "src", "types", "api.generated.ts");

function run(command, args) {
  const result = spawnSync(command, args, {
    cwd: root,
    stdio: "inherit",
    shell: process.platform === "win32",
    env: {
      ...process.env,
      PYTHONPATH: [root, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter),
    },
  });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}

run(python, ["scripts/export_openapi.py", "--output", schemaPath]);
run(process.platform === "win32" ? "npx.cmd" : "npx", ["openapi-typescript", schemaPath, "-o", outputPath]);
