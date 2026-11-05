import { createHmac } from "node:crypto";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { cookiesMock } = vi.hoisted(() => ({ cookiesMock: vi.fn() }));
vi.mock("next/headers", () => ({ cookies: cookiesMock }));

const secret = "test-session-secret-that-is-long-enough";
const sign = (id: string) => `${id}.${createHmac("sha256", secret).update(id).digest("hex")}`;

describe("server backend client", () => {
  beforeEach(() => {
    vi.resetModules();
    process.env.SESSION_SECRET = secret;
    process.env.BACKEND_URL = "http://backend.test";
    process.env.BACKEND_API_KEY = "api-key-for-tests";
  });

  it("creates a signed httpOnly session when the cookie is absent", async () => {
    const set = vi.fn();
    cookiesMock.mockResolvedValue({ get: vi.fn(() => undefined), set });
    const { getOrCreateSessionId } = await import("./backend");

    const id = await getOrCreateSessionId();

    expect(id).toMatch(/^[a-f0-9]{32}$/);
    expect(set).toHaveBeenCalledWith("docguru_session", sign(id), expect.objectContaining({
      httpOnly: true,
      sameSite: "lax",
      path: "/",
    }));
  });

  it("refuses to sign cookies with a placeholder secret", async () => {
    process.env.SESSION_SECRET = "replace-with-random-32-byte-secret";
    cookiesMock.mockResolvedValue({ get: vi.fn(() => undefined), set: vi.fn() });
    const { getOrCreateSessionId } = await import("./backend");
    await expect(getOrCreateSessionId()).rejects.toThrow(/SESSION_SECRET must be configured/);
  });

  it("accepts a valid signed cookie and replaces an invalid signature", async () => {
    const validId = "a".repeat(32);
    const validSet = vi.fn();
    cookiesMock.mockResolvedValue({ get: vi.fn(() => ({ value: sign(validId) })), set: validSet });
    const { getOrCreateSessionId } = await import("./backend");
    expect(await getOrCreateSessionId()).toBe(validId);
    expect(validSet).not.toHaveBeenCalled();

    vi.resetModules();
    const invalidSet = vi.fn();
    cookiesMock.mockResolvedValue({ get: vi.fn(() => ({ value: `${validId}.bad` })), set: invalidSet });
    const reloaded = await import("./backend");
    const replaced = await reloaded.getOrCreateSessionId();
    expect(replaced).not.toBe(validId);
    expect(invalidSet).toHaveBeenCalledOnce();
  });

  it("forwards authenticated session and request options then clears its timeout", async () => {
    const id = "b".repeat(32);
    cookiesMock.mockResolvedValue({ get: vi.fn(() => ({ value: sign(id) })), set: vi.fn() });
    const fetchMock = vi.fn().mockResolvedValue(new Response("ok", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const clearTimeoutSpy = vi.spyOn(globalThis, "clearTimeout");
    const { backendFetch } = await import("./backend");

    const response = await backendFetch("/api/generate", {
      method: "POST",
      body: "payload",
      headers: { "Content-Type": "application/json" },
      timeoutMs: 500,
    });

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith("http://backend.test/api/generate", expect.objectContaining({
      method: "POST",
      body: "payload",
      headers: expect.objectContaining({ "X-Session-Id": id, "X-API-Key": "api-key-for-tests" }),
    }));
    expect(clearTimeoutSpy).toHaveBeenCalled();
  });

  it("clears the request timeout when fetch rejects", async () => {
    cookiesMock.mockResolvedValue({ get: vi.fn(() => ({ value: sign("c".repeat(32)) })), set: vi.fn() });
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    const clearTimeoutSpy = vi.spyOn(globalThis, "clearTimeout");
    const { backendFetch } = await import("./backend");

    await expect(backendFetch("/api/health")).rejects.toThrow("offline");
    expect(clearTimeoutSpy).toHaveBeenCalled();
  });
});
