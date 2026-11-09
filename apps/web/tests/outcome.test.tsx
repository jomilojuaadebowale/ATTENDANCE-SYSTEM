import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { OutcomeView } from "@/features/check-in";
import { ApiError } from "@/lib/api";
import { GeoError } from "@/lib/geo";
import type { CheckInResult } from "@/lib/scan-flow";
import type { ScanResult } from "@/types/api";

const base: ScanResult = { client_uuid: "x", outcome: "recorded", code: "verified", message: "Attendance recorded.", attendance_status: "verified", flag_reason: null, distance_m: 12.4, session_id: "s", course_code: "CSC 308" };
const show = (outcome: CheckInResult, extra: Partial<React.ComponentProps<typeof OutcomeView>> = {}) => render(<OutcomeView outcome={outcome} onAgain={() => undefined} {...extra} />);

describe("<OutcomeView /> feedback", () => {
  it("success: only for a server-confirmed result", () => {
    show({ kind: "result", result: base });
    expect(screen.getByText("Attendance recorded")).toBeInTheDocument();
    expect(screen.getByText(/CSC 308/)).toBeInTheDocument();
    expect(screen.getByText(/about 12 m/)).toBeInTheDocument();
  });

  it("queued (offline): says it is NOT recorded yet", () => {
    show({ kind: "queued", message: "Saved on this phone." });
    expect(screen.getByText(/saved, not yet confirmed/i)).toBeInTheDocument();
    expect(screen.getByText(/not recorded until the server confirms/i)).toBeInTheDocument();
    expect(screen.queryByText("Attendance recorded")).not.toBeInTheDocument();
  });

  it.each([
    ["outside_radius", "You appear to be about 220 m from the venue (limit 75 m)."],
    ["qr_expired", "This QR code has expired. Scan the code currently on screen."],
    ["not_enrolled", "You are not enrolled in this course."],
    ["session_closed", "This session has ended."],
  ])("rejection %s shows the server's reason and not a success message", (code, message) => {
    show({ kind: "result", result: { ...base, outcome: "rejected", code, message, attendance_status: null, distance_m: null } });
    expect(screen.getByText("Not recorded")).toBeInTheDocument();
    expect(screen.getByText(message)).toBeInTheDocument();
    expect(screen.queryByText("Attendance recorded")).not.toBeInTheDocument();
  });

  it("flagged: recorded but pending review", () => {
    show({ kind: "result", result: { ...base, outcome: "flagged", code: "low_accuracy", message: "Flagged for review.", attendance_status: "flagged" } });
    expect(screen.getByText("Recorded, pending review")).toBeInTheDocument();
  });

  it("duplicate", () => {
    show({ kind: "result", result: { ...base, outcome: "duplicate", code: "already_recorded", message: "Your attendance for this session was already recorded." } });
    expect(screen.getByText("Already recorded")).toBeInTheDocument();
  });

  it("invalid QR and hard errors", () => {
    show({ kind: "invalid_qr", message: "This is not an attendance QR code." });
    expect(screen.getByText("Not an attendance code")).toBeInTheDocument();
    show({ kind: "error", error: new ApiError(403, "account_disabled", "Your account is disabled.") });
    expect(screen.getByText("Your account is disabled.")).toBeInTheDocument();
  });

  it("location denied: explains why and offers the flagged fallback", async () => {
    const retry = vi.fn();
    show({ kind: "location_error", error: new GeoError("permission_denied", "Location permission was denied. Allow location access to check in.") }, { onRetryWithoutLocation: retry });
    expect(screen.getByText(/we need your location/i)).toBeInTheDocument();
    expect(screen.getByText(/allow location access/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /send without location/i }));
    expect(retry).toHaveBeenCalled();
  });

  it("lets the student scan again", async () => {
    const again = vi.fn();
    show({ kind: "invalid_qr", message: "x" }, { onAgain: again });
    await userEvent.click(screen.getByRole("button", { name: /scan another code/i }));
    expect(again).toHaveBeenCalled();
  });
});
