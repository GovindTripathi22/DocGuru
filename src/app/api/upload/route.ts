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

      if (hasExternalBackendEnv()) {
        try {
          const backendFormData = new FormData();
          const blob = new Blob([new Uint8Array(sample.buffer)], {
            type:
              sample.documentType === "pptx"
                ? "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                : sample.documentType === "pdf"
                ? "application/pdf"
                : "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          });
          backendFormData.append("file", blob, sample.filename);
          const res = await backendFetch("/api/upload", {
            method: "POST",
            body: backendFormData,
          });
          if (res.ok) {
            const backendData = await res.json();
            if (backendData && typeof backendData.template_id === "string") {
              analyzeTemplateBuffer(sample.filename, sample.buffer, backendData.template_id);
              return NextResponse.json(backendData, { status: 200 });
            }
          }
        } catch {
          // Fall back to standalone analyzed preset
        }
      }

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

    const filename = "name" in file && typeof file.name === "string" ? file.name : "template.docx";
    const arrayBuffer = await file.arrayBuffer();
    const rawBuffer = Buffer.from(arrayBuffer);

    if (hasExternalBackendEnv()) {
      try {
        const backendFormData = new FormData();
        backendFormData.append("file", new Blob([new Uint8Array(rawBuffer)], { type: file.type }), filename);

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

    const analyzed = analyzeTemplateBuffer(filename, rawBuffer);
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
