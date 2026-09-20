import { NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";

export async function GET() {
  try {
    const res = await backendFetch("/api/health", {
      headers: { "Content-Type": "application/json" },
    });

    if (!res.ok) {
      return NextResponse.json(
        { status: "error", error: "Backend health check returned non-OK" },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Failed to communicate with backend";
    return NextResponse.json(
      { status: "offline", model_provider: "offline", model_name: "Unavailable", error: message },
      { status: 503 }
    );
  }
}
