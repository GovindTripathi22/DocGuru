import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";

export async function GET(
  req: NextRequest,
  props: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await props.params;

    if (!id) {
      return NextResponse.json({ error: "Missing filename parameter" }, { status: 400 });
    }

    const res = await backendFetch(`/api/download/${encodeURIComponent(id)}`);

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "File not found" }));
      return NextResponse.json({ error: err.detail || "File not found" }, { status: res.status });
    }

    const contentType = res.headers.get("Content-Type") || "application/octet-stream";
    const contentDisposition = res.headers.get("Content-Disposition") || `attachment; filename="${id}"`;

    return new Response(res.body, {
      status: 200,
      headers: {
        "Content-Type": contentType,
        "Content-Disposition": contentDisposition,
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Failed to download file";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
