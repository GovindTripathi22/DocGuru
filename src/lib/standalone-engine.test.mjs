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

test("institutional seminar report template keeps front matter, removes formatting tips, and replaces chapters in-place", () => {
  const preset = getSampleTemplatePreset("executive-docx");
  const entries = readZipEntries(preset.buffer);
  const seminarDocXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    <w:p><w:r><w:t>A SEMINAR REPORT ON</w:t></w:r></w:p>
    <w:p><w:r><w:t>&lt;Title&gt;</w:t></w:r></w:p>
    <w:p><w:r><w:t>Formatting Tips: Font Style: Times New Roman(Bold), 14 Pt, Capital, Center Aligned</w:t></w:r></w:p>
    <w:p><w:r><w:t>SUBMITTED BY</w:t></w:r></w:p>
    <w:p><w:r><w:t>Name of Student</w:t></w:r></w:p>
    <w:p><w:r><w:t>GUIDED BY</w:t></w:r></w:p>
    <w:p><w:r><w:t>Prof. Guide Name</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>CERTIFICATE</w:t></w:r></w:p>
    <w:p><w:r><w:t>This is to certify that &lt;Student Name&gt; completed the seminar under &lt;Guide Name&gt;.</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>ABSTRACT</w:t></w:r></w:p>
    <w:p><w:r><w:t>Formatting Rule: Write 150 words in Times New Roman, 12 Pt, 1.5 line spacing.</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>TABLE OF CONTENT</w:t></w:r></w:p>
    <w:p><w:r><w:t>1. Introduction .......................... 1</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>CHAPTER 1: INTRODUCTION</w:t></w:r></w:p>
    <w:p><w:r><w:t>Note: Chapter 1 will be introduction part.</w:t></w:r></w:p>
    <w:p><w:r><w:t>Dummy sample chapter text that must be replaced in-place.</w:t></w:r></w:p>
    <w:sectPr><w:pgSz w:w="12240" w:h="15840" w:orient="portrait"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>
  </w:body>
</w:document>`;
  entries.set("word/document.xml", Buffer.from(seminarDocXml, "utf8"));
  const seminarBuffer = buildZipArchive(entries);

  const analyzed = analyzeTemplateBuffer("seminar-report-template.docx", seminarBuffer);
  assert.equal(analyzed.template_spec.is_institutional_template, true);
  assert.ok((analyzed.template_spec.body_anchor_index ?? -1) > 0);
  assert.equal(analyzed.template_spec.parsed_typography_rules?.font_family, "Times New Roman");

  const { result } = executeStandaloneGeneration({
    template_id: analyzed.template_id,
    prompt: "Federated Learning for Edge IoT Security",
    author: "Aarav Sharma",
    guide: "Dr. R. K. Deshmukh",
    department: "Computer Engineering",
  });

  const outRecord = getStandaloneOutput(result.output_filename);
  assert.ok(outRecord);
  const outXml = readZipEntries(outRecord.buffer).get("word/document.xml")?.toString("utf8") || "";

  // Front matter is preserved and populated
  assert.match(outXml, /CERTIFICATE/);
  assert.match(outXml, /Aarav Sharma/);
  assert.match(outXml, /Dr\. R\. K\. Deshmukh/);
  // Embedded instructions and old sample chapter prose are removed
  assert.doesNotMatch(outXml, /Formatting Tips: Font Style/);
  assert.doesNotMatch(outXml, /Note: Chapter 1 will be introduction part/);
  assert.doesNotMatch(outXml, /Dummy sample chapter text that must be replaced/);
  // Chapters are formatted with Times New Roman and CHAPTER prefix
  assert.match(outXml, /Times New Roman/);
  assert.match(outXml, /CHAPTER 1:/);
});

test("enforces embedded rules from non-institutional docx and strips all written rules across body, tables, and headers", () => {
  const preset = getSampleTemplatePreset("executive-docx");
  const entries = readZipEntries(preset.buffer);
  const ruledDocXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Formatting Guideline: Use Arial font, 16 pt heading left aligned uppercase, 11 pt body text, double spacing (2.0), left margin 1.5 inches, A4 page size.</w:t></w:r></w:p>
    <w:p><w:r><w:t>Required Sections: Overview, Methodology, Conclusion</w:t></w:r></w:p>
    <w:tbl><w:tr><w:tc><w:p><w:r><w:t>Formatting Rule: Keep body text justified.</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
    <w:sectPr><w:pgSz w:w="12240" w:h="15840" w:orient="portrait"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>
  </w:body>
</w:document>`;
  entries.set("word/document.xml", Buffer.from(ruledDocXml, "utf8"));
  entries.set(
    "word/header1.xml",
    Buffer.from(
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>Formatting Tip: Header instruction must be removed</w:t></w:r></w:p></w:hdr>`,
      "utf8",
    ),
  );
  const ruledBuf = buildZipArchive(entries);

  const analyzed = analyzeTemplateBuffer("company-policy-rules.docx", ruledBuf);
  assert.equal(analyzed.template_spec.has_embedded_rules, true);
  assert.equal(analyzed.template_spec.parsed_typography_rules?.font_family, "Arial");
  assert.equal(analyzed.template_spec.parsed_typography_rules?.heading1_size_pt, 16);
  assert.equal(analyzed.template_spec.parsed_typography_rules?.body_size_pt, 11);
  assert.equal(analyzed.template_spec.parsed_typography_rules?.line_spacing, 2);

  const { result } = executeStandaloneGeneration({
    template_id: analyzed.template_id,
    prompt: "Zero Trust Network Rollout Plan",
    rule_mode: "document",
    template_mode: "fill",
  });

  const outRecord = getStandaloneOutput(result.output_filename);
  assert.ok(outRecord);
  const outEntries = readZipEntries(outRecord.buffer);
  const outDocXml = outEntries.get("word/document.xml")?.toString("utf8") || "";
  const outStylesXml = outEntries.get("word/styles.xml")?.toString("utf8") || "";
  const outHeaderXml = outEntries.get("word/header1.xml")?.toString("utf8") || "";

  assert.doesNotMatch(outDocXml, /Formatting Guideline:/);
  assert.doesNotMatch(outDocXml, /Required Sections:/);
  assert.doesNotMatch(outHeaderXml, /Header instruction must be removed/);
  assert.match(outStylesXml, /w:ascii="Arial"/);
  assert.match(outStylesXml, /w:sz w:val="32"/);
  assert.match(outStylesXml, /w:sz w:val="22"/);
  assert.match(outDocXml, /w:line="480"/);
  assert.match(outDocXml, /w:left="2160"/);
  assert.match(outDocXml, /w:w="11906"/);
  assert.match(outDocXml, /OVERVIEW/);
  assert.match(outDocXml, /METHODOLOGY/);
  assert.ok(
    result.validation.components?.some((c) => c.name === "Rule Enforcement"),
  );
});

test("supports custom preferences mode when template has no embedded rules or user overrides document rules", () => {
  const preset = getSampleTemplatePreset("executive-docx");
  const rulelessEntries = readZipEntries(preset.buffer);
  rulelessEntries.set(
    "word/document.xml",
    Buffer.from(
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>1. Overview</w:t></w:r></w:p>
    <w:p><w:r><w:t>Plain content paragraph without any embedded formatting rules.</w:t></w:r></w:p>
    <w:sectPr><w:pgSz w:w="12240" w:h="15840" w:orient="portrait"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>
  </w:body>
</w:document>`,
      "utf8",
    ),
  );
  const rulelessBuf = buildZipArchive(rulelessEntries);
  const analyzed = analyzeTemplateBuffer("plain-template.docx", rulelessBuf);
  assert.equal(analyzed.template_spec.has_embedded_rules, false);

  const { result } = executeStandaloneGeneration({
    template_id: analyzed.template_id,
    prompt: "Data Platform Modernization Strategy",
    rule_mode: "custom",
    custom_rules: {
      font_name: "Georgia",
      heading1_size_pt: 18,
      body_size_pt: 11,
      line_spacing: 1.5,
      body_alignment: "justify",
      heading1_alignment: "center",
      heading1_case: "uppercase",
      margin_inches: 0.75,
      page_size: "A4",
    },
  });

  const outRecord = getStandaloneOutput(result.output_filename);
  assert.ok(outRecord);
  const outEntries = readZipEntries(outRecord.buffer);
  const outDocXml = outEntries.get("word/document.xml")?.toString("utf8") || "";
  const outStylesXml = outEntries.get("word/styles.xml")?.toString("utf8") || "";

  assert.match(outStylesXml, /w:ascii="Georgia"/);
  assert.match(outStylesXml, /w:sz w:val="36"/);
  assert.match(outStylesXml, /w:sz w:val="22"/);
  assert.match(outDocXml, /w:pgMar w:top="1080" w:right="1080" w:bottom="1080" w:left="1080"/);
  assert.match(outDocXml, /w:w="11906"/);
  const ruleComp = result.validation.components?.find((c) => c.name === "Rule Enforcement");
  assert.equal(ruleComp?.status, "intentional_override");
  assert.match(ruleComp?.detail || "", /Georgia/);

  // Also verify switching a rule-bearing template to rule_mode="custom" overrides its embedded rules
  const ruledAnalyzed = analyzeTemplateBuffer(preset.filename, preset.buffer);
  assert.equal(ruledAnalyzed.template_spec.has_embedded_rules, true);
  const overrideRes = executeStandaloneGeneration({
    template_id: ruledAnalyzed.template_id,
    prompt: "Override Document Rules With Custom",
    rule_mode: "custom",
    custom_rules: { font_name: "Verdana", body_size_pt: 10 },
  });
  const overrideOut = getStandaloneOutput(overrideRes.result.output_filename);
  assert.ok(overrideOut);
  const overrideStyles = readZipEntries(overrideOut.buffer).get("word/styles.xml")?.toString("utf8") || "";
  assert.match(overrideStyles, /w:ascii="Verdana"/);
  assert.match(overrideStyles, /w:sz w:val="20"/);
});

