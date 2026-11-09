"use client";

import { WifiOff } from "lucide-react";
import { useEffect, useState } from "react";
import { useOnline } from "@/hooks/use-online";
import { useAuth } from "@/lib/auth";
import { queue } from "@/lib/offline-queue";
import { flushQueue } from "@/lib/scan-flow";

/** Shows connection state and automatically sends queued scans when the network returns. */
export function OfflineBanner() {
  const { api, me } = useAuth();
  const online = useOnline();
  const [pending, setPending] = useState(0);
  const student = me?.role === "student";

  useEffect(() => {
    if (!student) return;
    let cancelled = false;
    async function sync() {
      try {
        if (navigator.onLine) await flushQueue(api);
        const n = await queue.count();
        if (!cancelled) setPending(n);
      } catch {
        /* IndexedDB unavailable (private mode): nothing queued */
      }
    }
    void sync();
    const id = window.setInterval(sync, 20000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [api, student, online]);

  if (online && pending === 0) return null;
  return (
    <div role="status" className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-center text-sm text-amber-900">
      <WifiOff className="mr-1 inline h-4 w-4" aria-hidden />
      {!online ? "You are offline. " : ""}
      {pending > 0 ? `${pending} scan${pending === 1 ? "" : "s"} saved on this phone, waiting to send.` : "Scans you take will be saved and sent when you reconnect."}
    </div>
  );
}
