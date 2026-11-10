import { z } from "zod";

const DocumentTypeSchema = z.enum(["docx", "pptx", "pdf"]);

export const HealthResponseSchema = z.object({
  status: z.string(),
  version: z.string(),
  model_provider: z.string(),
  model_name: z.string(),
  mode: z.enum(["live", "demo", "misconfigured"]),
  ready: z.boolean(),
  time: z.number(),
  capabilities: z.object({
    images: z.boolean(),
    image_placeholders: z.boolean(),
    preview: z.boolean(),
    edit_pptx: z.boolean(),
    max_upload_mb: z.number(),
    research: z.boolean(),
  }).passthrough(),
}).passthrough();

export const ValidationReportSchema = z.object({
  status: z.enum(["passed", "failed", "not_applicable"]),
  passed: z.boolean(),
  components: z.array(z.object({
    name: z.string(),
    status: z.enum(["identical", "changed", "intentional_override"]),
    detail: z.string().nullable().optional(),
  }).passthrough()).default([]),
  issues: z.array(z.string()).default([]),
  warnings: z.array(z.string()).default([]),
}).passthrough();

export const GenerationResultSchema = z.object({
  success: z.boolean(),
  output_id: z.string().optional(),
  output_filename: z.string().optional(),
  filename: z.string().optional(),
  download_url: z.string(),
  template_id: z.string().optional(),
  generation_mode: z.string(),
  validation: ValidationReportSchema,
  warnings: z.array(z.string()),
  research_sources: z.array(z.object({
    id: z.string(),
    title: z.string(),
    url: z.string(),
  }).passthrough()).optional(),
  timings: z.record(z.string(), z.number()).optional(),
  execution_time_sec: z.number().optional(),
  model: z.string().optional(),
}).passthrough();

export const JobProgressSchema = z.object({
  job_id: z.string(),
  status: z.enum(["queued", "running", "succeeded", "failed", "cancelled"]),
  stage: z.enum([
    "queued",
    "analyzing",
    "planning_outline",
    "researching",
    "writing_sections",
    "fetching_images",
    "assembling",
    "validating",
    "done",
    "failed",
    "cancelled",
  ]),
  progress: z.number().min(0).max(1),
  message: z.string(),
  current: z.record(z.string(), z.number()).nullable().optional(),
  warnings: z.array(z.string()).default([]),
  result: GenerationResultSchema.nullable().optional(),
  error: z.record(z.string(), z.unknown()).nullable().optional(),
}).passthrough();

export const AcceptedJobSchema = z.object({
  job_id: z.string(),
  status: z.enum(["queued", "running"]),
  stage: z.string(),
  message: z.string(),
}).passthrough();

export const CancelJobSchema = z.object({
  job_id: z.string(),
  status: z.enum(["queued", "running", "cancelled", "succeeded", "failed"]),
  message: z.string(),
}).passthrough();

export const TemplateUploadResponseSchema = z.object({
  success: z.literal(true),
  template_id: z.string(),
  original_filename: z.string(),
  document_type: DocumentTypeSchema,
  extracted_rules: z.array(z.string()),
  document_outline: z.array(z.string()),
  template_spec: z.object({
    filename: z.string(),
    document_type: DocumentTypeSchema,
    total_pages_or_slides: z.number(),
  }).passthrough(),
}).passthrough();

export async function parseApiJson<T>(response: Response, schema: z.ZodType<T>) {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return { success: false as const, issues: ["Response body is not valid JSON."] };
  }
  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    return {
      success: false as const,
      issues: parsed.error.issues.map((issue) => issue.path.join(".") || "response").slice(0, 10),
    };
  }
  return { success: true as const, data: parsed.data };
}
