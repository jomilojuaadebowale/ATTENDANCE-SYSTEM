const KEY = "attendance.device_id";

/**
 * A random id generated once per browser install. It identifies the phone for the
 * "one device per student" rule. It is NOT a credential and grants no access.
 */
export function getDeviceId(): string {
  try {
    const existing = localStorage.getItem(KEY);
    if (existing && existing.length >= 8) return existing;
    const fresh = `web-${crypto.randomUUID()}`;
    localStorage.setItem(KEY, fresh);
    return fresh;
  } catch {
    return `web-ephemeral-${crypto.randomUUID()}`;
  }
}
