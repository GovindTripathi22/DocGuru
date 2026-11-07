import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";
import { AcceptedJobSchema, GenerationResultSchema } from "@/lib/api-schemas";
import { proxyJsonResponse } from "@/lib/api-proxy";
import { executeStandaloneGeneration } from "@/lib/standalone-engine";

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
        const res = await backendFetch("/api/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });

        if (res.status === 202) return proxyJsonResponse(res, AcceptedJobSchema);
        if (res.ok) return proxyJsonResponse(res, GenerationResultSchema);
      } catch {
        // Fall back to standalone generation
      }
    }

    const { job } = executeStandaloneGeneration(body);
    return NextResponse.json(
      {
        job_id: job.job_id,
        status: "queued",
        stage: "queued",
        message: "Job accepted for processing.",
      },
      { status: 202 },
    );
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Failed to initiate document generation";
    return NextResponse.json(
      { error: { code: "GENERATION_FAILED", message }, detail: message },
      { status: 500 },
    );
  }
}
