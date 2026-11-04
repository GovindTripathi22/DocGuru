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
