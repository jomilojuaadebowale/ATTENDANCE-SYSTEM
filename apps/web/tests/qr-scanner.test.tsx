import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QRScanner, classifyCameraError } from "@/features/qr-scanner";

function stubCamera(impl: () => Promise<MediaStream>) {
  vi.stubGlobal("navigator", { ...navigator, mediaDevices: { getUserMedia: vi.fn(impl) } });
}
afterEach(() => vi.unstubAllGlobals());
const domError = (name: string) => new DOMException("x", name);

describe("classifyCameraError", () => {
  it.each([
    ["NotAllowedError", "denied"],
    ["SecurityError", "denied"],
    ["NotFoundError", "no_camera"],
    ["OverconstrainedError", "no_camera"],
    ["AbortError", "failed"],
    ["NotReadableError", "failed"],
  ])("%s -> %s", (name, expected) => expect(classifyCameraError(domError(name))).toBe(expected));
  it("treats unknown errors as failed", () => expect(classifyCameraError(new Error("boom"))).toBe("failed"));
});

describe("<QRScanner />", () => {
  it("explains a denied camera permission and offers a retry", async () => {
    stubCamera(() => Promise.reject(domError("NotAllowedError")));
    render(<QRScanner onDecode={() => undefined} />);
    expect(await screen.findByText(/camera permission was denied/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try the camera again/i })).toBeInTheDocument();
  });

  it("explains a missing camera (no retry button)", async () => {
    stubCamera(() => Promise.reject(domError("NotFoundError")));
    render(<QRScanner onDecode={() => undefined} />);
    expect(await screen.findByText(/no camera was found/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /try the camera again/i })).not.toBeInTheDocument();
  });

  it("explains insecure contexts / unsupported browsers", async () => {
    vi.stubGlobal("navigator", { ...navigator, mediaDevices: undefined });
    render(<QRScanner onDecode={() => undefined} />);
    expect(await screen.findByText(/needs a secure \(https\) connection/i)).toBeInTheDocument();
  });

  it("retries the camera when asked", async () => {
    const getUserMedia = vi.fn().mockRejectedValueOnce(domError("NotReadableError")).mockRejectedValueOnce(domError("NotAllowedError"));
    vi.stubGlobal("navigator", { ...navigator, mediaDevices: { getUserMedia } });
    render(<QRScanner onDecode={() => undefined} />);
    await userEvent.click(await screen.findByRole("button", { name: /try the camera again/i }));
    expect(await screen.findByText(/camera permission was denied/i)).toBeInTheDocument();
    expect(getUserMedia).toHaveBeenCalledTimes(2);
  });

  it("still lets the student type a code when the camera is broken", async () => {
    stubCamera(() => Promise.reject(domError("NotFoundError")));
    const onDecode = vi.fn();
    render(<QRScanner onDecode={onDecode} />);
    await screen.findByText(/no camera was found/i);
    const submit = screen.getByRole("button", { name: /use code/i });
    expect(submit).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/qr code text/i), "v1.abc");
    await userEvent.click(submit);
    expect(onDecode).toHaveBeenCalledWith("v1.abc");
  });
});
