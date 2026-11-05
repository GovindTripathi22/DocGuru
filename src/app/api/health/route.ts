import { NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";
import { HealthResponseSchema } from "@/lib/api-schemas";
import { proxyJsonResponse } from "@/lib/api-proxy";

export async function GET() {
  try {
    const res = await backendFetch("/api/health", {
      headers: { "Content-Type": "application/json" },
    });

    if (!res.ok) return proxyJsonResponse(res, HealthResponseSchema);
    return proxyJsonResponse(res, HealthResponseSchema);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Failed to communicate with backend";
    return NextResponse.json(
      { status: "offline", model_provider: "offline", model_name: "Unavailable", error: message },
      { status: 503 }
    );
  }
}
