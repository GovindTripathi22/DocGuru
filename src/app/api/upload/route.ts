import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";
import { TemplateUploadResponseSchema } from "@/lib/api-schemas";
import { proxyJsonResponse } from "@/lib/api-proxy";
import {
  analyzeTemplateBuffer,
  getSampleTemplatePreset,
  type SamplePresetId,
} from "@/lib/standalone-engine";

function hasExternalBackendEnv(): boolean {
  const url = process.env.BACKEND_URL?.trim();
  const secret = process.env.SESSION_SECRET?.trim();
  return Boolean(url && secret && secret.length >= 32 && !secret.toLowerCase().includes("replace-with"));
}

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const preset = formData.get("preset");
    const file = formData.get("file");

    if (
      typeof preset === "string" &&
      (preset === "executive-docx" || preset === "strategy-pptx" || preset === "reference-pdf")
    ) {
      const sample = getSampleTemplatePreset(preset as SamplePresetId);
      const analyzed = analyzeTemplateBuffer(sample.filename, sample.buffer);
      return NextResponse.json(analyzed, { status: 200 });
    }

    if (!file || !(file instanceof Blob)) {
      return NextResponse.json(
        {
          error: { code: "BAD_REQUEST", message: "No file uploaded" },
          detail: "No file uploaded",
        },
        { status: 400 },
      );
    }

    if (hasExternalBackendEnv()) {
      try {
        const backendFormData = new FormData();
        backendFormData.append("file", file);

        const res = await backendFetch("/api/upload", {
          method: "POST",
          body: backendFormData,
        });

        if (res.status !== 401 && res.status !== 502 && res.status !== 504) {
          return proxyJsonResponse(res, TemplateUploadResponseSchema);
        }
      } catch {
        // Fall back to standalone OpenXML/PDF analyzer
      }
    }

    const filename = "name" in file && typeof file.name === "string" ? file.name : "template.docx";
    const arrayBuffer = await file.arrayBuffer();
    const analyzed = analyzeTemplateBuffer(filename, Buffer.from(arrayBuffer));
    return NextResponse.json(analyzed, { status: 200 });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Failed to analyze uploaded template";
    return NextResponse.json(
      {
        error: { code: "UPLOAD_ERROR", message },
        detail: message,
      },
      { status: 400 },
    );
  }
}
