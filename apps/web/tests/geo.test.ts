import { afterEach, describe, expect, it, vi } from "vitest";
import { GeoError, getPosition } from "@/lib/geo";

function mockGeolocation(behaviour: "ok" | "denied" | "unavailable" | "timeout") {
  const getCurrentPosition = vi.fn((success: PositionCallback, error: PositionErrorCallback) => {
    if (behaviour === "ok") success({ coords: { latitude: 7.5186, longitude: 4.5213, accuracy: 12 } } as GeolocationPosition);
    else {
      const code = { denied: 1, unavailable: 2, timeout: 3 }[behaviour];
      error({ code, PERMISSION_DENIED: 1, POSITION_UNAVAILABLE: 2, TIMEOUT: 3, message: "" } as GeolocationPositionError);
    }
  });
  vi.stubGlobal("navigator", { geolocation: { getCurrentPosition } });
  return getCurrentPosition;
}
afterEach(() => vi.unstubAllGlobals());

describe("getPosition", () => {
  it("returns one high-accuracy fix", async () => {
    const spy = mockGeolocation("ok");
    expect(await getPosition()).toEqual({ lat: 7.5186, lng: 4.5213, accuracy: 12 });
    expect((spy.mock.calls[0] as unknown[] | undefined)?.[2]).toMatchObject({ enableHighAccuracy: true, maximumAge: 0 });
  });

  it.each([
    ["denied", "permission_denied"],
    ["unavailable", "unavailable"],
    ["timeout", "timeout"],
  ] as const)("maps %s to %s", async (behaviour, code) => {
    mockGeolocation(behaviour);
    await expect(getPosition()).rejects.toMatchObject({ name: "GeoError", code });
  });

  it("reports unsupported browsers", async () => {
    vi.stubGlobal("navigator", {});
    const err = await getPosition().catch((e: unknown) => e);
    expect(err).toBeInstanceOf(GeoError);
    expect((err as GeoError).code).toBe("unsupported");
  });

  it("never tracks continuously", () => {
    const watch = vi.fn();
    vi.stubGlobal("navigator", { geolocation: { getCurrentPosition: vi.fn(), watchPosition: watch } });
    void getPosition();
    expect(watch).not.toHaveBeenCalled();
  });
});
