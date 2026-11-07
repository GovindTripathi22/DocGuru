import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";
import { enhancePromptStandalone } from "@/lib/standalone-engine";

function hasExternalBackendEnv(): boolean {
  const url = process.env.BACKEND_URL?.trim();
  const secret = process.env.SESSION_SECRET?.trim();
  return Boolean(url && secret && secret.length >= 32 && !secret.toLowerCase().includes("replace-with"));
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();

    if (hasExternalBackendEnv()) {
      try {
        const res = await backendFetch("/api/enhance-prompt", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          timeoutMs: 4000,
        });

        if (res.ok) {
          const data = await res.json();
          return NextResponse.json(data);
        }
      } catch {
        // Fall back to standalone prompt enhancer
      }
    }

    const enhanced = await enhancePromptStandalone(
      typeof body?.prompt === "string" ? body.prompt : "",
      body?.document_type === "pptx" || body?.document_type === "pdf" ? body.document_type : "docx",
    );
    return NextResponse.json(enhanced, { status: 200 });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Failed to enhance prompt";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
