import { describe, expect, it } from "vitest";

import { proxyJsonResponse } from "./api-proxy";
import { HealthResponseSchema } from "./api-schemas";

describe("proxyJsonResponse", () => {
  it("forwards valid API data and request metadata", async () => {
    const response = new Response(JSON.stringify({
      status: "healthy",
      version: "1.0.0",
      model_provider: "demo",
      model_name: "demo",
      mode: "demo",
      ready: true,
      time: 1,
      capabilities: {
        images: true,
        image_placeholders: false,
        preview: false,
        edit_pptx: true,
        max_upload_mb: 25,
        research: false,
      },
    }), { status: 200, headers: { "X-Request-ID": "request-1" } });

    const result = await proxyJsonResponse(response, HealthResponseSchema);

    expect(result.status).toBe(200);
    expect(result.headers.get("X-Request-ID")).toBe("request-1");
    expect((await result.json()).mode).toBe("demo");
  });

  it("returns a typed 502 instead of forwarding a broken success payload", async () => {
    const result = await proxyJsonResponse(
      new Response(JSON.stringify({ status: "healthy" }), { status: 200 }),
      HealthResponseSchema,
    );

    expect(result.status).toBe(502);
    expect(await result.json()).toMatchObject({
      error: { code: "BACKEND_CONTRACT_INVALID" },
    });
  });

  it("preserves backend error status and body", async () => {
    const result = await proxyJsonResponse(
      new Response(JSON.stringify({ error: { code: "LLM_NOT_CONFIGURED" } }), { status: 503 }),
      HealthResponseSchema,
    );

    expect(result.status).toBe(503);
    expect(await result.json()).toMatchObject({ error: { code: "LLM_NOT_CONFIGURED" } });
  });
});
