import { describe, expect, it } from "vitest";

import {
  AcceptedJobSchema,
  HealthResponseSchema,
  JobProgressSchema,
  TemplateUploadResponseSchema,
  ValidationReportSchema,
} from "./api-schemas";

describe("backend response contracts", () => {
  it("accepts the documented health payload and rejects missing capabilities", () => {
    const health = {
      status: "healthy",
      app_name: "DocGuru",
      version: "1.0.0",
      model_provider: "demo",
      model_name: "demo",
      mode: "demo",
      ready: true,
      time: 1,
      capabilities: {
        images: true,
        image_placeholders: false,
        preview: false,
        edit_pptx: true,
        max_upload_mb: 25,
        research: false,
      },
    };
    expect(HealthResponseSchema.safeParse(health).success).toBe(true);
    expect(HealthResponseSchema.safeParse({ ...health, capabilities: {} }).success).toBe(false);
  });

  it("accepts uploaded template metadata while retaining additional analyzer fields", () => {
    const upload = {
      success: true,
      template_id: "a".repeat(32) + ".docx",
      original_filename: "brief.docx",
      document_type: "docx",
      extracted_rules: [],
      document_outline: ["Introduction"],
      template_spec: {
        filename: "brief.docx",
        document_type: "docx",
        total_pages_or_slides: 1,
        fonts: { all_detected_fonts: ["Aptos"] },
      },
    };
    expect(TemplateUploadResponseSchema.safeParse(upload).success).toBe(true);
    expect(TemplateUploadResponseSchema.safeParse({ ...upload, template_id: 7 }).success).toBe(false);
  });

  it("checks job progress and nested validation results", () => {
    expect(AcceptedJobSchema.safeParse({
      job_id: "abc",
      status: "queued",
      stage: "queued",
      message: "Accepted",
    }).success).toBe(true);

    const job = {
      job_id: "abc",
      status: "succeeded",
      stage: "done",
      progress: 1,
      message: "Done",
      warnings: [],
      result: {
        success: true,
        download_url: "/api/download/out.docx",
        generation_mode: "demo",
        validation: {
          status: "passed",
          passed: true,
          components: [],
          issues: [],
          warnings: [],
        },
        warnings: [],
      },
    };
    expect(JobProgressSchema.safeParse(job).success).toBe(true);
    expect(JobProgressSchema.safeParse({ ...job, progress: 1.5 }).success).toBe(false);
  });

  it("accepts all supported validation states", () => {
    for (const status of ["passed", "failed", "not_applicable"] as const) {
      expect(ValidationReportSchema.safeParse({
        status,
        passed: status !== "failed",
        components: [],
        issues: [],
        warnings: [],
      }).success).toBe(true);
    }
  });
});
