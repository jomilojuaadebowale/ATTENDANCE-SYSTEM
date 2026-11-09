import { ApiError, type Api } from "@/lib/api";
import { getDeviceId } from "@/lib/device";
import { GeoError, getPosition, type Position } from "@/lib/geo";
import { queue } from "@/lib/offline-queue";
import { parseQR } from "@/lib/qr";
import type { ScanPayload, ScanResult } from "@/types/api";

export type CheckInResult =
  | { kind: "invalid_qr"; message: string }
  | { kind: "location_error"; error: GeoError }
  | { kind: "result"; result: ScanResult }
  | { kind: "queued"; message: string }
  | { kind: "error"; error: ApiError };

/** Errors that mean "try again later": keep the scan in the queue. */
function isRetryable(e: ApiError): boolean {
  return e.isNetwork || e.status >= 500 || e.status === 401 || e.status === 429;
}

export async function submitScans(api: Api, scans: ScanPayload[]): Promise<ScanResult[]> {
  const res = await api.request<{ results: ScanResult[] }>("/attendance/sync", {
    method: "POST",
    body: { scans },
  });
  return res.results;
}

/**
 * The whole student check-in, in the order that keeps scans safe:
 *   1. read the QR text   2. get ONE location fix   3. save the scan locally
 *   4. ask the server (it decides)   5. only then tell the student what happened.
 * The UI must show "recorded" only for a `result` whose outcome came from the server.
 */
export async function checkIn(
  api: Api,
  qrText: string,
  opts: { allowWithoutLocation?: boolean; getPos?: () => Promise<Position>; now?: () => Date } = {},
): Promise<CheckInResult> {
  if (!parseQR(qrText)) return { kind: "invalid_qr", message: "This is not an attendance QR code." };

  let pos: Position | null = null;
  try {
    pos = await (opts.getPos ?? getPosition)();
  } catch (e) {
    if (!opts.allowWithoutLocation) return { kind: "location_error", error: e as GeoError };
  }

  const payload: ScanPayload = {
    client_uuid: crypto.randomUUID(),
    qr_payload: qrText.trim(),
    device_id: getDeviceId(),
    device_time: (opts.now?.() ?? new Date()).toISOString(),
    scan_lat: pos?.lat ?? null,
    scan_lng: pos?.lng ?? null,
    accuracy_m: pos?.accuracy ?? null,
  };
  await queue.add(payload); // saved first, so a dead network or a closed tab cannot lose it

  try {
    const [result] = await submitScans(api, [payload]);
    if (!result) throw new ApiError(500, "empty_response", "The server returned no result.");
    await queue.remove(payload.client_uuid);
    await queue.saveOutcome(result);
    return { kind: "result", result };
  } catch (e) {
    const err = e instanceof ApiError ? e : new ApiError(0, "network_error", "Cannot reach the server.");
    if (isRetryable(err)) {
      return { kind: "queued", message: "Saved on this phone. It will be sent automatically when you are back online." };
    }
    await queue.remove(payload.client_uuid);
    return { kind: "error", error: err };
  }
}

/** Send everything waiting in the queue. Safe to call repeatedly (server is idempotent). */
export async function flushQueue(api: Api): Promise<{ sent: ScanResult[]; remaining: number }> {
  const pending = await queue.list();
  if (pending.length === 0) return { sent: [], remaining: 0 };
  const sent: ScanResult[] = [];
  for (let i = 0; i < pending.length; i += 50) {
    const chunk = pending.slice(i, i + 50);
    try {
      const results = await submitScans(api, chunk.map((p) => p.payload));
      for (const r of results) {
        await queue.remove(r.client_uuid);
        await queue.saveOutcome(r);
        sent.push(r);
      }
    } catch (e) {
      if (e instanceof ApiError && !isRetryable(e)) {
        for (const p of chunk) await queue.remove(p.client_uuid);
      } else break; // still offline: stop, try later
    }
  }
  return { sent, remaining: await queue.count() };
}
