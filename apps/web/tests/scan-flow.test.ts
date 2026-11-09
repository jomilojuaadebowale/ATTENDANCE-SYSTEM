import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, type Api } from "@/lib/api";
import { GeoError } from "@/lib/geo";
import { queue } from "@/lib/offline-queue";
import { checkIn, flushQueue } from "@/lib/scan-flow";
import type { ScanPayload, ScanResult } from "@/types/api";

const SID = "12345678-1234-4234-8234-123456789abc";
const QR = `v1.${SID}.7.m8XXSJlSyghiEGGVy6Jrq8`;
const POS = { lat: 7.5186, lng: 4.5213, accuracy: 12 };

function result(over: Partial<ScanResult> = {}): ScanResult {
  return { client_uuid: "x", outcome: "recorded", code: "verified", message: "Attendance recorded.", attendance_status: "verified", flag_reason: null, distance_m: 4, session_id: SID, course_code: "CSC 308", ...over };
}

/** A fake API whose /attendance/sync echoes a result per scan, unless told to fail. */
function fakeApi(handler?: (scans: ScanPayload[]) => ScanResult[] | Error) {
  const request = vi.fn(async (_path: string, opts?: { body?: { scans: ScanPayload[] } }) => {
    const scans = opts?.body?.scans ?? [];
    const out = handler ? handler(scans) : scans.map((s) => result({ client_uuid: s.client_uuid }));
    if (out instanceof Error) throw out;
    return { results: out };
  });
  return { api: { request, download: vi.fn() } as unknown as Api, request };
}

async function clearQueue() {
  for (const p of await queue.list()) await queue.remove(p.client_uuid);
}
beforeEach(clearQueue);

describe("checkIn", () => {
  it("rejects non-attendance QR codes without contacting the server or asking for location", async () => {
    const { api, request } = fakeApi();
    const getPos = vi.fn();
    const out = await checkIn(api, "https://example.com", { getPos });
    expect(out.kind).toBe("invalid_qr");
    expect(request).not.toHaveBeenCalled();
    expect(getPos).not.toHaveBeenCalled();
  });

  it("stops with a location error when permission is denied", async () => {
    const { api, request } = fakeApi();
    const out = await checkIn(api, QR, { getPos: async () => Promise.reject(new GeoError("permission_denied", "denied")) });
    expect(out).toMatchObject({ kind: "location_error", error: { code: "permission_denied" } });
    expect(request).not.toHaveBeenCalled();
    expect(await queue.count()).toBe(0);
  });

  it("can send without location when the student chooses to (server will flag it)", async () => {
    const { api, request } = fakeApi();
    const out = await checkIn(api, QR, { allowWithoutLocation: true, getPos: async () => Promise.reject(new GeoError("unavailable", "x")) });
    expect(out.kind).toBe("result");
    const sent = (request.mock.calls[0]?.[1]?.body as { scans: ScanPayload[] }).scans[0];
    expect(sent).toMatchObject({ scan_lat: null, scan_lng: null, accuracy_m: null });
  });

  it("sends the raw facts only (QR text, location, phone time, device id) and returns the server's decision", async () => {
    const { api, request } = fakeApi((scans) => [result({ client_uuid: scans[0]!.client_uuid, outcome: "rejected", code: "outside_radius", message: "You appear to be about 220 m from the venue", attendance_status: null })]);
    const out = await checkIn(api, QR, { getPos: async () => POS, now: () => new Date("2026-10-30T09:00:00Z") });
    const body = request.mock.calls[0]?.[1]?.body as unknown as { scans: Record<string, unknown>[] };
    expect(Object.keys(body.scans[0]!).sort()).toEqual(["accuracy_m", "client_uuid", "device_id", "device_time", "qr_payload", "scan_lat", "scan_lng"]);
    expect(body.scans[0]).toMatchObject({ qr_payload: QR, scan_lat: POS.lat, device_time: "2026-10-30T09:00:00.000Z" });
    expect(out).toMatchObject({ kind: "result", result: { outcome: "rejected", code: "outside_radius" } });
    expect(await queue.count()).toBe(0); // answered by the server: nothing left to retry
  });

  it("keeps the scan queued and does NOT claim success when offline", async () => {
    const { api } = fakeApi(() => new ApiError(0, "network_error", "offline"));
    const out = await checkIn(api, QR, { getPos: async () => POS });
    expect(out.kind).toBe("queued");
    expect(await queue.count()).toBe(1);
    expect((await queue.list())[0]?.payload.qr_payload).toBe(QR);
  });

  it.each([500, 503, 429, 401])("keeps the scan for retry on HTTP %i", async (status) => {
    const { api } = fakeApi(() => new ApiError(status, "x", "x"));
    expect((await checkIn(api, QR, { getPos: async () => POS })).kind).toBe("queued");
    expect(await queue.count()).toBe(1);
  });

  it("drops the scan and shows the error for permanent failures (403)", async () => {
    const { api } = fakeApi(() => new ApiError(403, "account_disabled", "Your account is disabled."));
    const out = await checkIn(api, QR, { getPos: async () => POS });
    expect(out).toMatchObject({ kind: "error", error: { code: "account_disabled" } });
    expect(await queue.count()).toBe(0);
  });
});

describe("flushQueue", () => {
  it("sends queued scans, stores outcomes and empties the queue", async () => {
    const offline = fakeApi(() => new ApiError(0, "network_error", "offline"));
    await checkIn(offline.api, QR, { getPos: async () => POS });
    await checkIn(offline.api, QR, { getPos: async () => POS });
    expect(await queue.count()).toBe(2);

    const online = fakeApi();
    const { sent, remaining } = await flushQueue(online.api);
    expect(sent).toHaveLength(2);
    expect(remaining).toBe(0);
    expect((await queue.outcomes()).length).toBeGreaterThanOrEqual(2);
  });

  it("stops quietly while still offline and keeps everything", async () => {
    const offline = fakeApi(() => new ApiError(0, "network_error", "offline"));
    await checkIn(offline.api, QR, { getPos: async () => POS });
    const { sent, remaining } = await flushQueue(offline.api);
    expect(sent).toHaveLength(0);
    expect(remaining).toBe(1);
  });

  it("does nothing when the queue is empty", async () => {
    const { api, request } = fakeApi();
    expect(await flushQueue(api)).toEqual({ sent: [], remaining: 0 });
    expect(request).not.toHaveBeenCalled();
  });
});
