import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";
import { ValidationReportSchema } from "@/lib/api-schemas";
import { proxyJsonResponse } from "@/lib/api-proxy";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const res = await backendFetch("/api/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    return proxyJsonResponse(res, ValidationReportSchema);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Failed to communicate with backend";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
