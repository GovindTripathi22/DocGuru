import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";
import { CancelJobSchema, JobProgressSchema } from "@/lib/api-schemas";
import { proxyJsonResponse } from "@/lib/api-proxy";

export async function GET(
  req: NextRequest,
  props: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await props.params;
    const res = await backendFetch(`/api/jobs/${encodeURIComponent(id)}`);
    return proxyJsonResponse(res, JobProgressSchema);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Failed to fetch job";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function DELETE(
  req: NextRequest,
  props: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await props.params;
    const res = await backendFetch(`/api/jobs/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
    return proxyJsonResponse(res, CancelJobSchema);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Failed to cancel job";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
