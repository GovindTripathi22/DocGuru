import assert from "node:assert/strict";
import test from "node:test";
import { buildGenerationPayload } from "./generation-request.ts";

test("page targets use a distinct API field and do not send a preset", () => {
  const payload = buildGenerationPayload("template-id", "docx", {
    prompt: "Write about climate adaptation",
    mode: "create_document",
    targetPages: 8,
  });

  assert.equal(payload.target_pages, 8);
  assert.equal("detail_level" in payload, false);
  assert.equal("target_pages_or_slides" in payload, false);
});

test("detail presets use a distinct API field and default research to off", () => {
  const payload = buildGenerationPayload("template-id", "pdf", {
    prompt: "Write about climate adaptation",
    mode: "create_document",
    detailLevel: "medium",
  });

  assert.equal(payload.detail_level, "medium");
  assert.equal("target_pages" in payload, false);
  assert.equal(payload.research_enabled, false);
});

test("presentations send slide count and suppress document research", () => {
  const payload = buildGenerationPayload("template-id", "pptx", {
    prompt: "Create a presentation",
    mode: "create_presentation",
    targetSlides: 12,
    researchEnabled: true,
  });

  assert.equal(payload.target_slides, 12);
  assert.equal(payload.research_enabled, false);
  assert.equal("target_pages" in payload, false);
  assert.equal("detail_level" in payload, false);
});

test("conflicting page and detail targets are rejected", () => {
  assert.throws(
    () =>
      buildGenerationPayload("template-id", "docx", {
        prompt: "Write about climate adaptation",
        mode: "create_document",
        targetPages: 8,
        detailLevel: "high",
      }),
    /Choose either a page target or a detail preset/,
  );
});

test("research is only sent for document creation when opted in", () => {
  const creation = buildGenerationPayload("template-id", "docx", {
    prompt: "Write about climate adaptation",
    mode: "create_document",
    detailLevel: "medium",
    researchEnabled: true,
  });
  const edit = buildGenerationPayload("template-id", "docx", {
    prompt: "Edit the introduction",
    mode: "edit_document",
    detailLevel: "medium",
    researchEnabled: true,
  });

  assert.equal(creation.research_enabled, true);
  assert.equal(edit.research_enabled, false);
});

test("sends only the server-resolved indexes for enabled template rules", () => {
  const payload = buildGenerationPayload("template-id", "docx", {
    prompt: "Write a guide",
    mode: "create_document",
    detailLevel: "medium",
    enabledRuleIndexes: [0, 2],
  });

  assert.deepEqual(payload.enabled_rule_indices, [0, 2]);
});

test("forwards optional seminar metadata fields when provided", () => {
  const payload = buildGenerationPayload("template-id", "docx", {
    prompt: "Write a seminar report on autonomous agents",
    mode: "create_document",
    detailLevel: "medium",
    author: "Aarav Sharma",
    guide: "Dr. R. K. Deshmukh",
    department: "Computer Engineering",
    institution: "PICT Pune",
    academicYear: "2025-2026",
  });

  assert.equal(payload.author, "Aarav Sharma");
  assert.equal(payload.guide, "Dr. R. K. Deshmukh");
  assert.equal(payload.department, "Computer Engineering");
  assert.equal(payload.institution, "PICT Pune");
  assert.equal(payload.academic_year, "2025-2026");
});

test("forwards rule_mode and custom_rules only when ruleMode is custom", () => {
  const docMode = buildGenerationPayload("template-id", "docx", {
    prompt: "Write technical documentation",
    mode: "create_document",
    detailLevel: "medium",
    ruleMode: "document",
    customRules: { font_name: "Arial", body_size_pt: 11 },
  });
  assert.equal(docMode.rule_mode, "document");
  assert.equal("custom_rules" in docMode, false);

  const customMode = buildGenerationPayload("template-id", "docx", {
    prompt: "Write technical documentation",
    mode: "create_document",
    detailLevel: "medium",
    ruleMode: "custom",
    customRules: {
      font_name: "Calibri",
      heading1_size_pt: 18,
      body_size_pt: 11,
      line_spacing: 1.5,
      margin_inches: 0.75,
      page_size: "A4",
    },
  });
  assert.equal(customMode.rule_mode, "custom");
  assert.deepEqual(customMode.custom_rules, {
    font_name: "Calibri",
    heading1_size_pt: 18,
    body_size_pt: 11,
    line_spacing: 1.5,
    margin_inches: 0.75,
    page_size: "A4",
  });
});

