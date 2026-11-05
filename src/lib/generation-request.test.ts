import { describe, expect, it } from "vitest";
import type { GenerationPromptOptions } from "./generation-request";
import { buildGenerationPayload } from "./generation-request";

describe("buildGenerationPayload", () => {
  const common: Pick<GenerationPromptOptions, "prompt" | "mode"> = {
    prompt: "A detailed climate adaptation report",
    mode: "create_document",
  };

  it("separates page targets from detail presets and omits absent fields", () => {
    const pages = buildGenerationPayload("template", "docx", { ...common, targetPages: 8 });
    const detail = buildGenerationPayload("template", "pdf", { ...common, detailLevel: "high" });

    expect(pages).toMatchObject({
      template_id: "template",
      document_type: "docx",
      target_pages: 8,
      research_enabled: false,
      include_images: true,
      image_mode: "search",
    });
    expect(pages).not.toHaveProperty("detail_level");
    expect(detail).toMatchObject({ detail_level: "high" });
    expect(detail).not.toHaveProperty("target_pages");
  });

  it("sends slide targets only for presentations and suppresses their research", () => {
    const payload = buildGenerationPayload("template", "pptx", {
      ...common,
      mode: "create_presentation",
      targetSlides: 12,
      researchEnabled: true,
    });

    expect(payload.target_slides).toBe(12);
    expect(payload.research_enabled).toBe(false);
    expect(payload).not.toHaveProperty("target_pages");
    expect(payload).not.toHaveProperty("detail_level");
  });

  it("rejects incompatible length targets", () => {
    expect(() =>
      buildGenerationPayload("template", "docx", {
        ...common,
        targetPages: 8,
        detailLevel: "medium",
      }),
    ).toThrow(/Choose either a page target or a detail preset/);
    expect(() =>
      buildGenerationPayload("template", "pptx", { ...common, targetPages: 8 }),
    ).toThrow(/Presentations use a slide target/);
    expect(() =>
      buildGenerationPayload("template", "docx", { ...common, targetSlides: 8 }),
    ).toThrow(/Documents use a page or detail target/);
  });

  it("limits research to opted-in document creation and copies selected rule indexes", () => {
    const creation = buildGenerationPayload("template", "docx", {
      ...common,
      detailLevel: "medium",
      researchEnabled: true,
      enabledRuleIndexes: [0, 2],
      customInstructions: "Engineering managers",
      includeImages: false,
      imageMode: "search",
    });
    const edit = buildGenerationPayload("template", "docx", {
      ...common,
      mode: "edit_document",
      detailLevel: "low",
      researchEnabled: true,
    });

    expect(creation).toMatchObject({
      research_enabled: true,
      enabled_rule_indices: [0, 2],
      custom_instructions: "Engineering managers",
      include_images: false,
      image_mode: "search",
    });
    expect(edit.research_enabled).toBe(false);
  });

  it("sends explicit template, edit, and validated color override fields", () => {
    const payload = buildGenerationPayload("template", "docx", {
      ...common,
      templateMode: "fill",
      editAction: "insert_after",
      editTargetIndex: 2,
      override: { target: "heading_color", value: "#23A1EF" },
    });

    expect(payload).toMatchObject({
      template_mode: "fill",
      edit_action: "insert_after",
      edit_target_index: 2,
      overrides: [{ target: "heading_color", value: "#23A1EF" }],
    });
  });
});
