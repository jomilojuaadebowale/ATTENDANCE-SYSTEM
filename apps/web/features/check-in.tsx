"use client";

import { MapPin } from "lucide-react";
import { useCallback, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, Spinner } from "@/components/ui/feedback";
import { QRScanner } from "@/features/qr-scanner";
import { useAuth } from "@/lib/auth";
import { checkIn, type CheckInResult } from "@/lib/scan-flow";

type Phase = { name: "scanning" } | { name: "working"; qr: string } | { name: "done"; outcome: CheckInResult; qr: string };

/** What the student reads after the SERVER has answered. Never claims success on its own. */
export function OutcomeView({ outcome, onRetryWithoutLocation, onAgain }: { outcome: CheckInResult; onRetryWithoutLocation?: () => void; onAgain: () => void }) {
  let body;
  switch (outcome.kind) {
    case "invalid_qr":
      body = <Alert tone="error" title="Not an attendance code">{outcome.message}</Alert>;
      break;
    case "location_error":
      body = (
        <div className="space-y-3">
          <Alert tone="error" title="We need your location to check you in">
            {outcome.error.message}
          </Alert>
          {onRetryWithoutLocation ? (
            <div className="space-y-2 text-sm text-slate-600">
              <p>You can still send the scan without location. It will be flagged for your lecturer to review and may not count automatically.</p>
              <Button variant="secondary" onClick={onRetryWithoutLocation}>
                Send without location
              </Button>
            </div>
          ) : null}
        </div>
      );
      break;
    case "queued":
      body = <Alert tone="warning" title="Saved, not yet confirmed">{outcome.message} Your attendance is not recorded until the server confirms it.</Alert>;
      break;
    case "error":
      body = <Alert tone="error" title="Check-in failed">{outcome.error.message}</Alert>;
      break;
    case "result": {
      const r = outcome.result;
      const tone = r.outcome === "recorded" ? "success" : r.outcome === "flagged" || r.outcome === "duplicate" ? "warning" : "error";
      const title =
        r.outcome === "recorded" ? "Attendance recorded" : r.outcome === "flagged" ? "Recorded, pending review" : r.outcome === "duplicate" ? "Already recorded" : "Not recorded";
      body = (
        <Alert tone={tone} title={title}>
          <p>{r.message}</p>
          {r.course_code ? <p className="mt-1">Course: {r.course_code}</p> : null}
          {r.distance_m !== null ? <p>Distance from venue: about {Math.round(r.distance_m)} m</p> : null}
          {r.attendance_status ? <p className="mt-1"><Badge value={r.attendance_status} /></p> : null}
        </Alert>
      );
      break;
    }
  }
  return (
    <div className="space-y-4">
      {body}
      <Button onClick={onAgain}>Scan another code</Button>
    </div>
  );
}

export function CheckIn() {
  const { api } = useAuth();
  const [phase, setPhase] = useState<Phase>({ name: "scanning" });

  const run = useCallback(
    async (qr: string, allowWithoutLocation = false) => {
      setPhase({ name: "working", qr });
      const outcome = await checkIn(api, qr, { allowWithoutLocation });
      setPhase({ name: "done", outcome, qr });
    },
    [api],
  );
  const onDecode = useCallback((text: string) => void run(text), [run]);

  if (phase.name === "working")
    return (
      <div className="space-y-2">
        <Spinner label="Getting your location and checking in" />
        <p className="text-xs text-slate-500">Allow the location prompt if your browser asks.</p>
      </div>
    );
  if (phase.name === "done") {
    const qr = phase.qr;
    return (
      <OutcomeView
        outcome={phase.outcome}
        onRetryWithoutLocation={phase.outcome.kind === "location_error" ? () => void run(qr, true) : undefined}
        onAgain={() => setPhase({ name: "scanning" })}
      />
    );
  }
  return (
    <div className="space-y-4">
      <div className="flex gap-2 rounded-lg bg-slate-100 p-3 text-sm text-slate-600">
        <MapPin className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        <p>
          Your location is read <strong>once</strong>, when you scan, to confirm you are in the lecture venue. It is not tracked in the background.
        </p>
      </div>
      <QRScanner onDecode={onDecode} />
    </div>
  );
}
