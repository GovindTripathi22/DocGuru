import { NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";
import { HealthResponseSchema } from "@/lib/api-schemas";
import { proxyJsonResponse } from "@/lib/api-proxy";
import { getStandaloneHealth } from "@/lib/standalone-engine";

function hasExternalBackendEnv(): boolean {
  const url = process.env.BACKEND_URL?.trim();
  const secret = process.env.SESSION_SECRET?.trim();
  return Boolean(url && secret && secret.length >= 32 && !secret.toLowerCase().includes("replace-with"));
}

export async function GET() {
  if (hasExternalBackendEnv()) {
    try {
      const res = await backendFetch("/api/health", {
        headers: { "Content-Type": "application/json" },
        timeoutMs: 3000,
      });
      if (res.ok) {
        return proxyJsonResponse(res, HealthResponseSchema);
      }
    } catch {
      // Fall back to standalone in-process engine when external backend is unreachable
    }
  }

  return NextResponse.json(getStandaloneHealth(), { status: 200 });
}
