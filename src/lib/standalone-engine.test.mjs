import assert from "node:assert/strict";
import test from "node:test";
import {
  analyzeTemplateBuffer,
  buildZipArchive,
  enhancePromptStandalone,
  executeStandaloneGeneration,
  getSampleTemplatePreset,
  getStandaloneJob,
  getStandaloneOutput,
  readZipEntries,
  validateStandaloneOutput,
} from "./standalone-engine.ts";

test("buildZipArchive and readZipEntries roundtrip binary and XML entries", () => {
  const entries = {
    "[Content_Types].xml": Buffer.from("<Types/>", "utf8"),
    "word/document.xml": Buffer.from(
      "<w:document><w:body><w:p><w:r><w:t>Hello</w:t></w:r></w:p></w:body></w:document>",
      "utf8",
    ),
  };
  const zipBuffer = buildZipArchive(entries);
  const decoded = readZipEntries(zipBuffer);

  assert.equal(decoded.size, 2);
  assert.equal(decoded.get("[Content_Types].xml")?.toString("utf8"), "<Types/>");
  assert.match(decoded.get("word/document.xml")?.toString("utf8") || "", /Hello/);
});

test("getSampleTemplatePreset, analyzeTemplateBuffer, and executeStandaloneGeneration produce valid OpenXML output", () => {
  const preset = getSampleTemplatePreset("executive-docx");
  const loaded = analyzeTemplateBuffer(preset.filename, preset.buffer);
  assert.equal(loaded.document_type, "docx");
  assert.ok(loaded.template_id);
  assert.equal(loaded.template_spec.filename, "executive-architecture-report.docx");
  assert.ok(loaded.template_spec.available_heading_styles?.includes("Heading 1"));

  const { job, result } = executeStandaloneGeneration({
    template_id: loaded.template_id,
    prompt: "Cloud reliability architecture and incident response playbook",
    detail_level: "medium",
    include_images: false,
    overrides: [{ target: "heading_color", value: "#1E40AF" }],
  });

  assert.equal(job.status, "succeeded");
  assert.equal(getStandaloneJob(job.job_id)?.status, "succeeded");
  assert.equal(result.validation?.passed, true);
  assert.ok((result.plan_summary?.length || 0) >= 3);

  const outputRecord = getStandaloneOutput(result.output_filename);
  assert.ok(outputRecord);
  const outputZip = readZipEntries(outputRecord.buffer);
  assert.ok(outputZip.get("word/document.xml"));

  const revalidated = validateStandaloneOutput(loaded.template_id, result.output_filename);
  assert.ok(revalidated);
  assert.equal(revalidated.passed, true);
  const typoComp = revalidated.components?.find((c) => c.name === "Typography & Styles");
  assert.equal(typoComp?.status, "intentional_override");
});

test("surgical edit and presentation slide append modes preserve template structure", () => {
  const docxPreset = getSampleTemplatePreset("executive-docx");
  const docxLoaded = analyzeTemplateBuffer(docxPreset.filename, docxPreset.buffer);

  const editRes = executeStandaloneGeneration({
    template_id: docxLoaded.template_id,
    prompt: "Add a new chapter on zero-trust telemetry",
    mode: "edit_document",
    edit_action: "insert_after",
    edit_target_index: 0,
    overrides: [{ target: "page_border", value: "#0F172A" }],
  });
  assert.equal(editRes.result.validation.passed, true);
  const pageComp = editRes.result.validation.components?.find(
    (c) => c.name === "Page & Margin Setup",
  );
  assert.equal(pageComp?.status, "intentional_override");

  const pptxPreset = getSampleTemplatePreset("strategy-pptx");
  const pptxLoaded = analyzeTemplateBuffer(pptxPreset.filename, pptxPreset.buffer);
  const pptxRes = executeStandaloneGeneration({
    template_id: pptxLoaded.template_id,
    prompt: "Append slides on quantum cryptography readiness",
    mode: "edit_presentation",
    target_slides: 3,
  });
  assert.equal(pptxRes.result.validation.passed, true);
  const pptxOut = getStandaloneOutput(pptxRes.result.output_filename);
  assert.ok(pptxOut);
  const pptxEntries = readZipEntries(pptxOut.buffer);
  // Original slide1.xml + 3 appended slides = 4 slides
  assert.ok(pptxEntries.get("ppt/slides/slide1.xml"));
  assert.ok(pptxEntries.get("ppt/slides/slide4.xml"));
});

test("enhancePromptStandalone expands short prompts deterministically when no API key is configured", async () => {
  const enhanced = await enhancePromptStandalone("Quarterly security review", "pptx");
  assert.match(enhanced.enhanced_prompt, /Quarterly security review/);
  assert.match(enhanced.enhanced_prompt, /presentation deck/i);
});
