"use client";

import QRCode from "qrcode";
import { useEffect, useRef, useState } from "react";
import { Alert, Spinner } from "@/components/ui/feedback";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { buildPayload, slotFor } from "@/lib/qr";
import type { QRSeed } from "@/types/api";

/**
 * Renders the rotating QR code. The signing seed is fetched ONCE; after that the code is
 * generated on this device (Web Crypto HMAC), so it keeps rotating even if the network drops.
 * The seed is held in memory only and is never written to storage.
 */
export function QRDisplay({ sessionId, onEnded }: { sessionId: string; onEnded?: () => void }) {
  const { api } = useAuth();
  const canvas = useRef<HTMLCanvasElement>(null);
  const [seed, setSeed] = useState<QRSeed | null>(null);
  const [offsetMs, setOffsetMs] = useState(0);
  const [error, setError] = useState<ApiError | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [ended, setEnded] = useState(false);
  const lastSlot = useRef<number>(-1);

  useEffect(() => {
    let cancelled = false;
    api
      .request<QRSeed>(`/sessions/${sessionId}/qr-seed`)
      .then((s) => {
        if (cancelled) return;
        setOffsetMs(new Date(s.server_time).getTime() - Date.now()); // align with the server clock
        setSeed(s);
      })
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e : new ApiError(0, "network_error", "Cannot load the QR code.")));
    return () => {
      cancelled = true;
    };
  }, [api, sessionId]);

  useEffect(() => {
    if (!seed) return;
    const startsAt = new Date(seed.starts_at).getTime();
    const endsAt = new Date(seed.ends_at).getTime();
    async function tick() {
      if (!seed) return;
      const now = Date.now() + offsetMs;
      if (now >= endsAt) {
        setEnded(true);
        onEnded?.();
        return;
      }
      const slot = slotFor(startsAt, now, seed.slot_seconds);
      setSecondsLeft(Math.max(0, Math.ceil((startsAt + (slot + 1) * seed.slot_seconds * 1000 - now) / 1000)));
      if (slot !== lastSlot.current && slot >= 0 && canvas.current) {
        lastSlot.current = slot;
        const payload = await buildPayload(seed.secret, seed.session_id, slot);
        await QRCode.toCanvas(canvas.current, payload, { width: 360, margin: 2, errorCorrectionLevel: "M" });
      }
    }
    void tick();
    const id = window.setInterval(() => void tick(), 500);
    return () => window.clearInterval(id);
  }, [seed, offsetMs, onEnded]);

  if (error)
    return (
      <Alert tone="error" title="Cannot show the QR code">
        {error.message}
      </Alert>
    );
  if (!seed) return <Spinner label="Preparing QR code" />;
  if (ended) return <Alert tone="info" title="Session ended">The QR code is no longer valid.</Alert>;
  return (
    <div className="flex flex-col items-center gap-3">
      <canvas ref={canvas} className="h-auto w-full max-w-[360px] rounded-lg border border-slate-200 bg-white" aria-label="Attendance QR code" />
      <p className="text-sm text-slate-600" aria-live="off">
        New code in <span className="font-semibold tabular-nums">{secondsLeft}s</span>. Students must scan the code currently on screen.
      </p>
    </div>
  );
}
