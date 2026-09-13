import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function GET(
  req: NextRequest,
  context?: { params?: Promise<{ id: string }> | { id: string } }
) {
  try {
    let id = "";
    if (context && context.params) {
      const resolvedParams = await Promise.resolve(context.params);
      id = resolvedParams?.id || "";
    }
    if (!id) {
      const pathParts = req.nextUrl.pathname.split("/");
      id = pathParts[pathParts.length - 1] || "";
    }

    if (!id) {
      return NextResponse.json({ error: "Missing filename parameter" }, { status: 400 });
    }

    const res = await fetch(`${BACKEND_URL}/api/download/${encodeURIComponent(id)}`);

    if (!res.ok) {
      return NextResponse.json({ error: "File not found in backend" }, { status: res.status });
    }

    const blob = await res.blob();
    const contentType = res.headers.get("Content-Type") || "application/octet-stream";
    const contentDisposition = res.headers.get("Content-Disposition") || `attachment; filename="${id}"`;

    return new NextResponse(blob, {
      status: 200,
      headers: {
        "Content-Type": contentType,
        "Content-Disposition": contentDisposition,
      },
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Failed to download file";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
