"use client";

import { useEffect, useState } from "react";
import { Alert } from "@/components/ui/feedback";
import { Card, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { queue, type StoredOutcome } from "@/lib/offline-queue";
import { formatDateTime } from "@/lib/utils";

/** Scans waiting on this phone, and the server's answer to recently synced ones. */
export function PendingScans() {
  const [pending, setPending] = useState(0);
  const [outcomes, setOutcomes] = useState<StoredOutcome[]>([]);

  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        const [n, o] = await Promise.all([queue.count(), queue.outcomes()]);
        if (alive) {
          setPending(n);
          setOutcomes(o);
        }
      } catch {
        /* storage unavailable */
      }
    }
    void load();
    const id = window.setInterval(load, 5000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, []);

  if (pending === 0 && outcomes.length === 0) return null;
  return (
    <Card className="mb-4">
      <CardTitle>Recent scans on this phone</CardTitle>
      {pending > 0 ? (
        <div className="mb-3">
          <Alert tone="warning">{pending} scan(s) not yet sent. They are sent automatically when you are online.</Alert>
        </div>
      ) : null}
      <ul className="divide-y divide-slate-100 text-sm">
        {outcomes.slice(0, 5).map((o) => (
          <li key={o.client_uuid} className="flex items-center justify-between gap-3 py-2">
            <span>
              {o.result.course_code ?? "Scan"} · {formatDateTime(o.at)}
            </span>
            <span className="flex items-center gap-2">
              <Badge value={o.result.outcome === "recorded" ? "verified" : o.result.outcome === "rejected" ? "rejected" : o.result.outcome === "flagged" ? "flagged" : "neutral"} label={o.result.outcome} />
              <span className="hidden text-slate-500 sm:inline">{o.result.message}</span>
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
