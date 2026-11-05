import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";
import { TemplateUploadResponseSchema } from "@/lib/api-schemas";
import { proxyJsonResponse } from "@/lib/api-proxy";

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const file = formData.get("file");

    if (!file) {
      return NextResponse.json({ error: "No file uploaded" }, { status: 400 });
    }

    const backendFormData = new FormData();
    backendFormData.append("file", file);

    const res = await backendFetch("/api/upload", {
      method: "POST",
      body: backendFormData,
    });

    return proxyJsonResponse(res, TemplateUploadResponseSchema);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Failed to communicate with backend";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
