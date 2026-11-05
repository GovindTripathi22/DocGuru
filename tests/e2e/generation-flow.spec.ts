import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const templateResponse = {
  template_id: "template-e2e",
  original_filename: "research-template.docx",
  document_type: "docx",
  template_spec: {
    filename: "research-template.docx",
    document_type: "docx",
    total_pages_or_slides: 3,
    style_hash: "fingerprint-e2e",
    page: {
      width_pt: 612,
      height_pt: 792,
      orientation: "portrait",
      margins: { top_pt: 72, bottom_pt: 72, left_pt: 72, right_pt: 72 },
    },
    fonts: { default: "Aptos", all_detected_fonts: ["Aptos"] },
    available_heading_styles: ["Heading 1"],
    table_rules: [],
  },
};

const result = {
  success: true,
  output_filename: "grid-integration.docx",
  download_url: "/api/download/grid-integration.docx",
  template_id: "template-e2e",
  generation_mode: "live",
  plan_summary: [{ title: "Grid resilience" }],
  validation: { passed: true, status: "passed", issues: [], components: [] },
  research_sources: [
    { id: "source-1", title: "Grid Integration Review", url: "https://example.test/grid", published_date: "2026-01-01" },
  ],
  warnings: ["Search results were not independently verified."],
};

test("uploads a template, submits the chosen page target, and displays sourced results accessibly", async ({ page }) => {
  await page.route("**/api/health", (route) => route.fulfill({
    json: { status: "ready", mode: "live", ready: true, model_provider: "google_ai", model_name: "test-model", capabilities: { research: true } },
  }));
  await page.route("**/api/upload", (route) => route.fulfill({ json: templateResponse }));
  let generatePayload: Record<string, unknown> | undefined;
  await page.route("**/api/generate", async (route) => {
    generatePayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({ status: 202, json: { job_id: "job-e2e", status: "queued", stage: "queued", message: "Accepted" } });
  });
  await page.route("**/api/jobs/job-e2e", (route) => route.fulfill({
    json: { job_id: "job-e2e", status: "succeeded", stage: "done", progress: 1, message: "Complete", warnings: [], result },
  }));

  await page.goto("/");
  await expect(page.getByText("Ready", { exact: true })).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles({
    name: "research-template.docx",
    mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    buffer: Buffer.from("test docx"),
  });

  await expect(page.getByRole("heading", { name: "research-template.docx" })).toBeVisible();
  await page.getByRole("textbox", { name: "Document prompt" }).fill("Write a detailed grid integration report");
  await page.getByRole("button", { name: "Choose pages" }).click();
  await page.getByLabel("Approximate page count (1–50)").fill("8");
  await page.getByRole("checkbox", { name: /Research sources/i }).check();

  const promptViolations = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(promptViolations.violations, JSON.stringify(promptViolations.violations, null, 2)).toEqual([]);

  await page.getByRole("button", { name: /Generate using this template/i }).click();
  await expect(page.getByRole("heading", { name: "Research sources" })).toBeVisible();
  expect(generatePayload).toMatchObject({
    template_id: "template-e2e",
    target_pages: 8,
    research_enabled: true,
  });
  expect(generatePayload).not.toHaveProperty("detail_level");
  await expect(page.getByRole("link", { name: "Grid Integration Review" })).toHaveAttribute("href", "https://example.test/grid");
  await expect(page.getByText("Search results were not independently verified.")).toBeVisible();

  const resultViolations = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(resultViolations.violations, JSON.stringify(resultViolations.violations, null, 2)).toEqual([]);
});

test("failed validation shows a red result and disables the normal download", async ({ page }) => {
  await page.route("**/api/health", (route) => route.fulfill({
    json: { status: "ready", mode: "demo", ready: true, model_provider: "demo", model_name: "demo", capabilities: {} },
  }));
  await page.route("**/api/upload", (route) => route.fulfill({ json: templateResponse }));
  await page.route("**/api/generate", (route) => route.fulfill({
    status: 202,
    json: { job_id: "job-failed", status: "queued", stage: "queued", message: "Accepted" },
  }));
  await page.route("**/api/jobs/job-failed", (route) => route.fulfill({
    json: {
      job_id: "job-failed",
      status: "succeeded",
      stage: "done",
      progress: 1,
      message: "Complete",
      warnings: [],
      result: {
        ...result,
        validation: {
          passed: false,
          status: "failed",
          issues: ["Template margin differs from the uploaded file."],
          components: [{ name: "Page setup", status: "changed", detail: "Margin drift detected" }],
        },
      },
    },
  }));

  await page.goto("/");
  await page.locator('input[type="file"]').setInputFiles({
    name: "research-template.docx",
    mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    buffer: Buffer.from("test docx"),
  });
  await page.getByRole("textbox", { name: "Document prompt" }).fill("Write a report about grid resilience");
  await page.getByRole("button", { name: /Generate using this template/i }).click();

  await expect(page.getByRole("heading", { name: "Template Drift Detected" })).toBeVisible();
  await expect(page.getByText("Template margin differs from the uploaded file.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Download Disabled (Drift Detected)" })).toBeVisible();
  await expect(page.getByText("Identical", { exact: true })).toHaveCount(0);

  const violations = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  expect(violations.violations, JSON.stringify(violations.violations, null, 2)).toEqual([]);
});
