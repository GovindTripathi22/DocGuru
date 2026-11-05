import { NextResponse } from "next/server";
import { z } from "zod";

import { parseApiJson } from "@/lib/api-schemas";

export async function proxyJsonResponse<T>(
  response: Response,
  schema: z.ZodType<T>,
): Promise<NextResponse> {
  const headers = new Headers();
  for (const name of ["retry-after", "x-request-id"]) {
    const value = response.headers.get(name);
    if (value) headers.set(name, value);
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({
      error: { code: "BACKEND_ERROR", message: "The backend request failed." },
    }));
    return NextResponse.json(body, { status: response.status, headers });
  }

  const parsed = await parseApiJson(response, schema);
  if (!parsed.success) {
    return NextResponse.json(
      {
        error: {
          code: "BACKEND_CONTRACT_INVALID",
          message: "The backend returned data that does not match the expected API response.",
          details: { fields: parsed.issues },
        },
      },
      { status: 502, headers },
    );
  }
  return NextResponse.json(parsed.data, { status: response.status, headers });
}
