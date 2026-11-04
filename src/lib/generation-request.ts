export type GenerationDocumentType = "docx" | "pptx" | "pdf";
export type DetailLevel = "low" | "medium" | "high";

export interface GenerationPromptOptions {
  prompt: string;
  mode: string;
  targetPages?: number;
  detailLevel?: DetailLevel;
  targetSlides?: number;
  researchEnabled?: boolean;
  customInstructions?: string;
  includeImages?: boolean;
  imageMode?: "search" | "generate" | "auto";
}

export interface GenerationRequestPayload {
  template_id: string;
  prompt: string;
  document_type: GenerationDocumentType;
  mode: string;
  target_pages?: number;
  detail_level?: DetailLevel;
  target_slides?: number;
  research_enabled: boolean;
  custom_instructions?: string;
  include_images: boolean;
  image_mode: "search" | "generate" | "auto";
}

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
    research_enabled:
      documentType !== "pptx" && options.mode.startsWith("create") && options.researchEnabled === true,
    include_images: options.includeImages ?? true,
    image_mode: options.imageMode ?? "auto",
  };

  if (documentType === "pptx") {
    if (options.targetSlides !== undefined) payload.target_slides = options.targetSlides;
  } else if (options.targetPages !== undefined) {
    payload.target_pages = options.targetPages;
  } else if (options.detailLevel !== undefined) {
    payload.detail_level = options.detailLevel;
  }

  if (options.customInstructions) payload.custom_instructions = options.customInstructions;
  return payload;
}
