import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";
import { getStandaloneOutput } from "@/lib/standalone-engine";

function hasExternalBackendEnv(): boolean {
  const url = process.env.BACKEND_URL?.trim();
  const secret = process.env.SESSION_SECRET?.trim();
  return Boolean(url && secret && secret.length >= 32 && !secret.toLowerCase().includes("replace-with"));
}

export async function GET(
  req: NextRequest,
  props: { params: Promise<{ id: string }> },
) {
  try {
    const { id } = await props.params;

    if (!id) {
      return NextResponse.json({ error: "Missing filename parameter" }, { status: 400 });
    }

    const standaloneOutput = getStandaloneOutput(id);
    if (standaloneOutput) {
      const safeFilename = id.replace(/[^\w.\-]/g, "_");
      return new Response(new Uint8Array(standaloneOutput.buffer), {
        status: 200,
        headers: {
          "Content-Type": standaloneOutput.contentType,
          "Content-Disposition": `attachment; filename="${safeFilename}"`,
          "X-Content-Type-Options": "nosniff",
        },
      });
    }

    if (hasExternalBackendEnv()) {
      const res = await backendFetch(`/api/download/${encodeURIComponent(id)}`);

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "File not found" }));
        return NextResponse.json(
          { error: err.error?.message || err.detail || "File not found" },
          { status: res.status },
        );
      }

      const contentType = res.headers.get("Content-Type") || "application/octet-stream";
      const contentDisposition =
        res.headers.get("Content-Disposition") || `attachment; filename="${id}"`;

      return new Response(res.body, {
        status: 200,
        headers: {
          "Content-Type": contentType,
          "Content-Disposition": contentDisposition,
          "X-Content-Type-Options": "nosniff",
        },
      });
    }

    return NextResponse.json({ error: "File not found" }, { status: 404 });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Failed to download file";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
