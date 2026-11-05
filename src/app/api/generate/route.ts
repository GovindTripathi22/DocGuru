import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";
import { AcceptedJobSchema, GenerationResultSchema } from "@/lib/api-schemas";
import { proxyJsonResponse } from "@/lib/api-proxy";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const res = await backendFetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (res.status === 202) return proxyJsonResponse(res, AcceptedJobSchema);
    return proxyJsonResponse(res, GenerationResultSchema);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Failed to communicate with backend";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
