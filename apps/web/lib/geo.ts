export interface Position {
  lat: number;
  lng: number;
  accuracy: number;
}

export type GeoErrorCode = "unsupported" | "permission_denied" | "unavailable" | "timeout";

export class GeoError extends Error {
  constructor(
    public code: GeoErrorCode,
    message: string,
  ) {
    super(message);
    this.name = "GeoError";
  }
}

/**
 * One-shot position request at check-in time. We never call watchPosition: no continuous
 * tracking and no movement history is collected.
 */
export function getPosition(timeoutMs = 15000): Promise<Position> {
  return new Promise((resolve, reject) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      reject(new GeoError("unsupported", "This browser cannot provide your location."));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude, accuracy: p.coords.accuracy }),
      (err) => {
        if (err.code === err.PERMISSION_DENIED)
          reject(new GeoError("permission_denied", "Location permission was denied. Allow location access to check in."));
        else if (err.code === err.TIMEOUT) reject(new GeoError("timeout", "Getting your location took too long. Try again outdoors or near a window."));
        else reject(new GeoError("unavailable", "Your location is unavailable right now."));
      },
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 0 },
    );
  });
}
