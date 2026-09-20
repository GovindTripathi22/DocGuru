import { cookies } from "next/headers";
import crypto from "crypto";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";
const BACKEND_API_KEY = process.env.BACKEND_API_KEY || "";
const SESSION_SECRET = process.env.SESSION_SECRET || "docguru-secret-key-32chars-minimum-pad";

function signSession(sessionId: string): string {
  const hmac = crypto.createHmac("sha256", SESSION_SECRET);
  hmac.update(sessionId);
  return `${sessionId}.${hmac.digest("hex")}`;
}

function verifySession(cookieValue: string): string | null {
  const parts = cookieValue.split(".");
  if (parts.length !== 2) return null;
  const [sessionId, sig] = parts;
  try {
    const hmac = crypto.createHmac("sha256", SESSION_SECRET);
    hmac.update(sessionId);
    const expected = hmac.digest("hex");
    if (crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expected))) {
      return sessionId;
    }
  } catch {
    return null;
  }
  return null;
}

export async function getOrCreateSessionId(): Promise<string> {
  const cookieStore = await cookies();
  const existing = cookieStore.get("docguru_session")?.value;
  if (existing) {
    const verified = verifySession(existing);
    if (verified) return verified;
  }
  const newId = crypto.randomUUID().replace(/-/g, "");
  const signed = signSession(newId);
  cookieStore.set("docguru_session", signed, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
  });
  return newId;
}

export async function backendFetch(
  path: string,
  options: {
    method?: string;
    body?: BodyInit | null;
    headers?: Record<string, string>;
    timeoutMs?: number;
  } = {}
): Promise<Response> {
  const sessionId = await getOrCreateSessionId();
  const headers: Record<string, string> = {
    "X-Session-Id": sessionId,
    ...(options.headers || {}),
  };

  if (BACKEND_API_KEY) {
    headers["X-API-Key"] = BACKEND_API_KEY;
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs || 120000);

  try {
    const res = await fetch(`${BACKEND_URL}${path}`, {
      method: options.method || "GET",
      headers,
      body: options.body,
      signal: controller.signal,
    });
    return res;
  } finally {
    clearTimeout(timeout);
  }
}
