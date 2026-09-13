import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const file = formData.get("file");

    if (!file) {
      return NextResponse.json({ error: "No file uploaded" }, { status: 400 });
    }

    const backendFormData = new FormData();
    backendFormData.append("file", file);

    const res = await fetch(`${BACKEND_URL}/api/upload`, {
      method: "POST",
      body: backendFormData,
    });

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({ detail: "Upload failed" }));
      return NextResponse.json({ error: errorData.detail || "Upload failed" }, { status: res.status });
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Failed to communicate with backend";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
