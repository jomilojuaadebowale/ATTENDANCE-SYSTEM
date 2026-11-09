/**
 * Rotating signed QR payloads. MUST stay byte-for-byte compatible with
 * apps/api/app/services/qr_service.py (there is a cross-check test).
 *
 *   v1.<session_id>.<slot>.<signature>
 *   signature = base64url(HMAC-SHA256(secret, "<session_id>:<slot>")).slice(0, 22)
 */
export const QR_VERSION = "v1";
export const SIGNATURE_CHARS = 22;

export interface ParsedQR {
  sessionId: string;
  slot: number;
  signature: string;
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function parseQR(raw: string): ParsedQR | null {
  const parts = raw.trim().split(".");
  if (parts.length !== 4 || parts[0] !== QR_VERSION) return null;
  const [, sessionId, slotText, signature] = parts as [string, string, string, string];
  if (!UUID_RE.test(sessionId) || !/^\d+$/.test(slotText) || signature.length !== SIGNATURE_CHARS) return null;
  return { sessionId, slot: Number(slotText), signature };
}

export function slotFor(startsAtMs: number, nowMs: number, slotSeconds: number): number {
  return Math.floor((nowMs - startsAtMs) / (slotSeconds * 1000));
}

function toBase64Url(bytes: ArrayBuffer): string {
  let bin = "";
  for (const b of new Uint8Array(bytes)) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export async function sign(secret: string, sessionId: string, slot: number): Promise<string> {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = await crypto.subtle.sign("HMAC", key, enc.encode(`${sessionId}:${slot}`));
  return toBase64Url(mac).slice(0, SIGNATURE_CHARS);
}

export async function buildPayload(secret: string, sessionId: string, slot: number): Promise<string> {
  return `${QR_VERSION}.${sessionId}.${slot}.${await sign(secret, sessionId, slot)}`;
}
