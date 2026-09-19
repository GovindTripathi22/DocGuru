export interface TemplatePageMargins {
  top_pt: number;
  bottom_pt: number;
  left_pt: number;
  right_pt: number;
}

export interface TemplatePageSpec {
  width_pt: number;
  height_pt: number;
  orientation: string;
  margins: TemplatePageMargins;
}

export interface SlideDimensions {
  width_inches: number;
  height_inches: number;
  aspect_ratio: string;
}

export interface TemplateFonts {
  default: string;
  heading1?: string;
  all_detected_fonts: string[];
}

export interface HeaderFooterInfo {
  has_content: boolean;
  text_preview?: string;
}

export interface TemplateSpec {
  filename: string;
  document_type: "docx" | "pptx" | "pdf";
  total_pages_or_slides: number;
  page?: TemplatePageSpec;
  slide_dimensions?: SlideDimensions;
  fonts?: TemplateFonts;
  available_heading_styles?: string[];
  available_layout_names?: string[];
  extracted_rules?: string[];
  document_outline?: string[];
  style_hash: string;
  header?: HeaderFooterInfo;
  footer?: HeaderFooterInfo;
  table_rules?: Record<string, unknown>[];
}

export interface ValidationReport {
  passed: boolean;
  original_style_hash: string;
  generated_style_hash: string;
  hash_match: boolean;
  font_drift_detected: boolean;
  border_drift_detected: boolean;
  margin_drift_detected: boolean;
  layout_drift_detected: boolean;
  header_footer_preserved: boolean;
  table_formatting_preserved: boolean;
  issues: string[];
}

export interface SlidePlan {
  slide_number: number;
  title: string;
  layout_name: string;
  content?: string[];
}

export interface SectionPlan {
  title: string;
  heading_style: string;
  content?: string[];
}

export interface GenerationPlan {
  slides?: SlidePlan[];
  sections?: SectionPlan[];
}

export interface PromptData {
  prompt: string;
  mode: string;
  targetPagesOrSlides?: number;
  customInstructions?: string;
  includeImages?: boolean;
  imageMode?: "search" | "generate" | "auto";
}

export interface TemplateUploadResponse {
  template_id: string;
  original_filename: string;
  document_type: "docx" | "pptx" | "pdf";
  template_spec: TemplateSpec;
  extracted_rules?: string[];
  document_outline?: string[];
  status?: string;
}

export interface GenerationResult {
  success: boolean;
  output_filename: string;
  download_url: string;
  template_spec: TemplateSpec;
  plan: GenerationPlan;
  validation: ValidationReport;
  execution_time_sec: number;
  message?: string;
}
