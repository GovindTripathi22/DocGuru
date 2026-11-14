import type { components } from "./api.generated";

export type GenerationMode = components["schemas"]["GenerationRequest"]["mode"];

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
  default?: string | null;
  body?: string | null;
  heading1?: string;
  heading2?: string | null;
  all_detected_fonts: string[];
}

export interface TemplateTheme {
  color_scheme?: Record<string, string | null> | null;
  font_scheme?: { major_font?: string | null; minor_font?: string | null } | null;
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
  theme?: TemplateTheme | null;
  available_heading_styles?: string[];
  available_layout_names?: string[];
  extracted_rules?: string[];
  document_outline?: string[];
  style_hash: string;
  header?: HeaderFooterInfo;
  footer?: HeaderFooterInfo;
  table_rules?: Record<string, unknown>[];
  is_institutional_template?: boolean;
  body_anchor_index?: number | null;
  parsed_typography_rules?: Record<string, unknown>;
  has_embedded_rules?: boolean;
  detected_rule_categories?: string[];
  parsed_structural_rules?: Record<string, unknown>;
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

export type RuleMode = "document" | "custom";

export interface CustomRulePreferences {
  font_name?: string;
  heading1_size_pt?: number;
  heading2_size_pt?: number;
  body_size_pt?: number;
  line_spacing?: number;
  body_alignment?: "left" | "center" | "right" | "justify";
  heading1_alignment?: "left" | "center" | "right" | "justify";
  heading1_case?: "uppercase" | "titlecase" | "normal";
  margin_inches?: number;
  page_size?: "A4" | "Letter" | "Legal";
}

export interface PromptData {
  prompt: string;
  mode: GenerationMode;
  templateMode?: "auto" | "fill" | "append";
  ruleMode?: RuleMode;
  customRules?: CustomRulePreferences;
  editAction?: "append" | "insert_after";
  editTargetIndex?: number;
  override?: { target: "table_border" | "page_border" | "heading_color"; value: string };
  targetPages?: number;
  detailLevel?: "low" | "medium" | "high";
  targetSlides?: number;
  researchEnabled?: boolean;
  customInstructions?: string;
  enabledRuleIndexes?: number[];
  includeImages?: boolean;
  imageMode?: "off" | "search" | "placeholder";
  author?: string;
  guide?: string;
  department?: string;
  institution?: string;
  academicYear?: string;
}

export interface ResearchSource {
  id: string;
  title: string;
  url: string;
  snippet?: string;
  published_date?: string | null;
  score?: number | null;
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
