import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import path from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const venvPython = path.resolve(".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const python = process.env.PYTHON || (existsSync(venvPython) ? venvPython : process.platform === "win32" ? "python" : "python3");
const fixturePath = path.resolve("tests/.tmp/e2e-template.docx");

async function expectNoSeriousAccessibilityViolations(page: import("@playwright/test").Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(
    results.violations.filter((violation) => ["serious", "critical"].includes(violation.impact || "")),
  ).toEqual([]);
}

test("demo backend accepts a real template, reports a job, and returns a reopenable DOCX", async ({ page }) => {
  const jobResponses: Array<{ stage: string; status: string; progress: number }> = [];
  page.on("response", async (response) => {
    if (!response.url().includes("/api/jobs/") || response.request().method() !== "GET") return;
    try {
      const job = await response.json();
      jobResponses.push({ stage: job.stage, status: job.status, progress: job.progress });
    } catch {
      // The final job result assertion below reports the actionable test failure.
    }
  });

  const landingResponse = await page.goto("/");
  expect(landingResponse?.headers()["content-security-policy"]).toContain("default-src 'self'");
  await expect(page.getByText(/DEMO CONTENT MODE/)).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);
  await page.locator('input[type="file"]').setInputFiles(fixturePath);
  await expect(page.getByRole("heading", { name: "e2e-template.docx" })).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);
  await page.getByRole("textbox", { name: "Document prompt" }).fill(
    "Create a concise implementation guide for safer software releases.",
  );
  await page.getByRole("button", { name: "Choose pages" }).click();
  await page.getByLabel("Approximate page count (1–50)").fill("1");
  await page.getByRole("button", { name: /Generate using this template/i }).click();

  await expect(page.getByRole("heading", { name: "Template checks passed" })).toBeVisible({ timeout: 120_000 });
  await expectNoSeriousAccessibilityViolations(page);
  expect(jobResponses.length).toBeGreaterThan(0);
  expect(jobResponses.every((job) => job.progress >= 0 && job.progress <= 1)).toBe(true);
  expect(jobResponses.some((job) => job.status === "succeeded")).toBe(true);

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download Artifact" }).click();
  const download = await downloadPromise;
  const outputPath = path.resolve("tests/.tmp", download.suggestedFilename());
  await download.saveAs(outputPath);

  const bytes = await readFile(outputPath);
  expect(bytes.subarray(0, 2).toString("ascii")).toBe("PK");
  const reopened = execFileSync(python, ["scripts/verify_e2e_artifact.py", outputPath], { encoding: "utf8" });
  expect(reopened).toContain("Reopened generated DOCX");
});
