"use client";

import jsQR from "jsqr";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/feedback";
import { Input } from "@/components/ui/form";

export type CameraProblem = "unsupported" | "denied" | "no_camera" | "failed";

const MESSAGES: Record<CameraProblem, string> = {
  unsupported: "Camera access needs a secure (HTTPS) connection and a modern browser.",
  denied: "Camera permission was denied. Allow camera access in your browser settings, then try again.",
  no_camera: "No camera was found on this device.",
  failed: "The camera could not be started. Close other apps that use it and try again.",
};

export function classifyCameraError(e: unknown): CameraProblem {
  const name = e instanceof DOMException ? e.name : "";
  if (name === "NotAllowedError" || name === "SecurityError" || name === "PermissionDeniedError") return "denied";
  if (name === "NotFoundError" || name === "OverconstrainedError" || name === "DevicesNotFoundError") return "no_camera";
  return "failed";
}

/** Camera scanner with explicit error states and a typed-code fallback. */
export function QRScanner({ onDecode, paused = false }: { onDecode: (text: string) => void; paused?: boolean }) {
  const video = useRef<HTMLVideoElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [problem, setProblem] = useState<CameraProblem | null>(null);
  const [starting, setStarting] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const [manual, setManual] = useState("");
  const handled = useRef(false);

  useEffect(() => {
    handled.current = paused;
  }, [paused]);

  useEffect(() => {
    let stream: MediaStream | null = null;
    let raf = 0;
    let stopped = false;

    async function start() {
      if (!navigator.mediaDevices?.getUserMedia) {
        setProblem("unsupported");
        setStarting(false);
        return;
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false });
      } catch (e) {
        setProblem(classifyCameraError(e));
        setStarting(false);
        return;
      }
      if (stopped || !video.current) return;
      video.current.srcObject = stream;
      await video.current.play().catch(() => undefined);
      setStarting(false);
      const loop = () => {
        const v = video.current;
        const c = canvas.current;
        if (v && c && !handled.current && v.readyState === v.HAVE_ENOUGH_DATA && v.videoWidth > 0) {
          c.width = v.videoWidth;
          c.height = v.videoHeight;
          const ctx = c.getContext("2d", { willReadFrequently: true });
          if (ctx) {
            ctx.drawImage(v, 0, 0, c.width, c.height);
            const img = ctx.getImageData(0, 0, c.width, c.height);
            const code = jsQR(img.data, img.width, img.height, { inversionAttempts: "dontInvert" });
            if (code?.data) {
              handled.current = true;
              onDecode(code.data);
            }
          }
        }
        raf = requestAnimationFrame(loop);
      };
      raf = requestAnimationFrame(loop);
    }
    void start();
    return () => {
      stopped = true;
      cancelAnimationFrame(raf);
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, [onDecode, attempt]);

  return (
    <div className="space-y-4">
      {problem ? (
        <div className="space-y-3">
          <Alert tone="error" title="Camera unavailable">
            {MESSAGES[problem]}
          </Alert>
          {problem !== "unsupported" && problem !== "no_camera" ? (
            <Button
              variant="secondary"
              onClick={() => {
                setProblem(null);
                setStarting(true);
                setAttempt((n) => n + 1);
              }}
            >
              Try the camera again
            </Button>
          ) : null}
        </div>
      ) : (
        <div className="relative overflow-hidden rounded-xl bg-black">
          <video ref={video} className="aspect-square w-full object-cover" playsInline muted aria-label="Camera preview" />
          {starting ? <p className="absolute inset-0 flex items-center justify-center text-sm text-white">Starting camera…</p> : null}
        </div>
      )}
      <canvas ref={canvas} className="hidden" />
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (manual.trim()) onDecode(manual.trim());
        }}
        aria-label="Enter code manually"
      >
        <Input value={manual} onChange={(e) => setManual(e.target.value)} placeholder="Or paste the code text" aria-label="QR code text" />
        <Button type="submit" variant="secondary" disabled={!manual.trim()}>
          Use code
        </Button>
      </form>
    </div>
  );
}
