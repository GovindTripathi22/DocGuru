import type { components } from "@/types/api.generated";
import type { GenerationMode } from "@/types/template";

export type GenerationDocumentType = components["schemas"]["GenerationRequest"]["document_type"];
export type DetailLevel = NonNullable<components["schemas"]["GenerationRequest"]["detail_level"]>;

export interface GenerationPromptOptions {
  prompt: string;
  mode: GenerationMode;
  templateMode?: components["schemas"]["GenerationRequest"]["template_mode"];
  targetPages?: number;
  detailLevel?: DetailLevel;
  targetSlides?: number;
  editAction?: "append" | "insert_after";
  editTargetIndex?: number;
  override?: components["schemas"]["ThemeOverrideRequest"];
  researchEnabled?: boolean;
  customInstructions?: string;
  enabledRuleIndexes?: number[];
  includeImages?: boolean;
  imageMode?: "off" | "search" | "placeholder";
}

export type GenerationRequestPayload = components["schemas"]["GenerationRequest"];

export function buildGenerationPayload(
  templateId: string,
  documentType: GenerationDocumentType,
  options: GenerationPromptOptions,
): GenerationRequestPayload {
  if (options.targetPages !== undefined && options.detailLevel !== undefined) {
    throw new Error("Choose either a page target or a detail preset.");
  }
  if (documentType === "pptx" && (options.targetPages !== undefined || options.detailLevel !== undefined)) {
    throw new Error("Presentations use a slide target.");
  }
  if (documentType !== "pptx" && options.targetSlides !== undefined) {
    throw new Error("Documents use a page or detail target.");
  }

  const payload: GenerationRequestPayload = {
    template_id: templateId,
    prompt: options.prompt,
    document_type: documentType,
    mode: options.mode,
    template_mode: options.templateMode ?? "auto",
    research_enabled:
      documentType !== "pptx" && options.mode.startsWith("create") && options.researchEnabled === true,
    include_images: options.imageMode === "off" ? false : options.includeImages ?? true,
    image_mode: options.imageMode ?? "search",
  };

  if (documentType === "pptx") {
    if (options.targetSlides !== undefined) payload.target_slides = options.targetSlides;
  } else if (options.targetPages !== undefined) {
    payload.target_pages = options.targetPages;
  } else if (options.detailLevel !== undefined) {
    payload.detail_level = options.detailLevel;
  }

  if (options.editAction) payload.edit_action = options.editAction;
  if (options.editTargetIndex !== undefined) payload.edit_target_index = options.editTargetIndex;
  if (options.override) payload.overrides = [options.override];

  if (options.customInstructions) payload.custom_instructions = options.customInstructions;
  if (options.enabledRuleIndexes !== undefined) payload.enabled_rule_indices = options.enabledRuleIndexes;
  return payload;
}
