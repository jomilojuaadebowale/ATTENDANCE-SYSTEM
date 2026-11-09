"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Alert, ErrorState, Spinner } from "@/components/ui/feedback";
import { Field, Select, Textarea } from "@/components/ui/form";
import { Stat } from "@/components/ui/stat";
import { Table, Td, Th } from "@/components/ui/table";
import { QRDisplay } from "@/features/qr-display";
import { useFetch } from "@/hooks/use-fetch";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDateTime, formatTime, titleCase } from "@/lib/utils";
import type { ClassSession, ManualMarkResult, ManualReason, RosterEntry, SessionRoster } from "@/types/api";

const REASONS: ManualReason[] = ["no_phone", "phone_dead", "network_failure", "app_problem", "other"];

export function SessionConsole({ sessionId }: { sessionId: string }) {
  const { api } = useAuth();
  const session = useFetch<ClassSession>(`/sessions/${sessionId}`);
  const roster = useFetch<SessionRoster>(`/sessions/${sessionId}/roster`);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [reason, setReason] = useState<ManualReason>("no_phone");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [review, setReview] = useState<{ entry: RosterEntry; action: "approve" | "reject" } | null>(null);
  const [reviewReason, setReviewReason] = useState("");

  const open = session.data?.status === "open";
  const { reload: reloadRoster } = roster;
  const { reload: reloadSession } = session;

  // Live totals: poll the roster while the session is open.
  useEffect(() => {
    if (!open) return;
    const id = window.setInterval(() => void reloadRoster(), 5000);
    return () => window.clearInterval(id);
  }, [open, reloadRoster]);

  const refresh = useCallback(async () => {
    await Promise.all([reloadRoster(), reloadSession()]);
  }, [reloadRoster, reloadSession]);

  async function act<T>(fn: () => Promise<T>, ok: (r: T) => string) {
    setBusy(true);
    setMessage(null);
    try {
      const r = await fn();
      setMessage({ tone: "success", text: ok(r) });
      await refresh();
    } catch (e) {
      setMessage({ tone: "error", text: e instanceof ApiError ? e.message : "Something went wrong." });
    } finally {
      setBusy(false);
    }
  }

  const markable = useMemo(() => roster.data?.entries.filter((e) => e.status === "not_marked" || e.status === "flagged" || e.status === "rejected") ?? [], [roster.data]);

  if (session.loading && !session.data) return <Spinner />;
  if (session.error) return <ErrorState error={session.error} onRetry={() => void session.reload()} />;
  if (!session.data) return null;
  const s = session.data;
  const counts = roster.data?.counts ?? {};

  return (
    <>
      <PageHeader
        title={`${s.course_code ?? "Session"} attendance`}
        description={`${formatDateTime(s.starts_at)} – ${formatTime(s.ends_at)} · ${s.venue_name ?? "lecturer location"} · radius ${s.radius_m} m`}
        actions={
          <>
            <Badge value={s.status} />
            {s.status === "open" || s.status === "scheduled" ? (
              <>
                <Button variant="secondary" disabled={busy} onClick={() => void act(() => api.request(`/sessions/${sessionId}/close`, { method: "POST" }), () => "Session closed and finalized.")}>
                  Close session
                </Button>
                <Button variant="danger" disabled={busy} onClick={() => void act(() => api.request(`/sessions/${sessionId}/cancel`, { method: "POST" }), () => "Session cancelled.")}>
                  Cancel
                </Button>
              </>
            ) : null}
          </>
        }
      />
      {message ? (
        <div className="mb-4">
          <Alert tone={message.tone}>{message.text}</Alert>
        </div>
      ) : null}
      <div className="grid gap-4 lg:grid-cols-3">
        {s.status === "open" ? (
          <Card className="lg:col-span-1">
            <CardTitle>Scan to check in</CardTitle>
            <QRDisplay sessionId={s.id} onEnded={() => void reloadSession()} />
          </Card>
        ) : (
          <Card className="lg:col-span-1">
            <CardTitle>QR code</CardTitle>
            <p className="text-sm text-slate-600">
              {s.status === "closed" ? "This session is closed. Late offline scans may still arrive for a while." : s.status === "cancelled" ? "This session was cancelled." : "This session has not started yet."}
            </p>
          </Card>
        )}
        <div className="space-y-4 lg:col-span-2">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Enrolled" value={counts.enrolled ?? 0} />
            <Stat label="Present" value={(counts.verified ?? 0) + (counts.manual ?? 0)} />
            <Stat label="Pending review" value={counts.flagged ?? 0} />
            <Stat label="Not marked" value={counts.not_marked ?? 0} hint={open ? "Not absent until closed" : undefined} />
          </div>
          <Card>
            <CardTitle>Mark students manually</CardTitle>
            <p className="mb-3 text-sm text-slate-600">For students without a working phone. A reason is required and the action is recorded in the audit log.</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Reason" htmlFor="manual_reason">
                <Select id="manual_reason" value={reason} onChange={(e) => setReason(e.target.value as ManualReason)}>
                  {REASONS.map((r) => (
                    <option key={r} value={r}>
                      {titleCase(r)}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Note (optional)" htmlFor="manual_note">
                <Textarea id="manual_note" rows={1} value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} />
              </Field>
            </div>
            <Button
              className="mt-3"
              disabled={busy || selected.size === 0}
              onClick={() =>
                void act(
                  () => api.request<ManualMarkResult>(`/sessions/${sessionId}/attendance/manual`, { method: "POST", body: { identifiers: [...selected], reason, note: note || null } }),
                  (r) => `Marked ${r.marked.length} present${r.already_present.length ? `, ${r.already_present.length} already present` : ""}${r.not_enrolled.length ? `, ${r.not_enrolled.length} not enrolled` : ""}.`,
                ).then(() => setSelected(new Set()))
              }
            >
              Mark {selected.size || ""} selected present
            </Button>
          </Card>
        </div>
      </div>

      <Card className="mt-4">
        <CardTitle>Roster</CardTitle>
        {roster.error ? <ErrorState error={roster.error} onRetry={() => void roster.reload()} /> : null}
        <Table>
          <thead>
            <tr>
              <Th>
                <input
                  type="checkbox"
                  aria-label="Select all unmarked students"
                  checked={markable.length > 0 && markable.every((e) => selected.has(e.identifier))}
                  onChange={(e) => setSelected(e.target.checked ? new Set(markable.map((m) => m.identifier)) : new Set())}
                />
              </Th>
              <Th>Matric no.</Th>
              <Th>Name</Th>
              <Th>Status</Th>
              <Th>Detail</Th>
              <Th />
            </tr>
          </thead>
          <tbody>
            {roster.data?.entries.map((e) => (
              <tr key={e.student_id}>
                <Td>
                  {markable.includes(e) ? (
                    <input
                      type="checkbox"
                      aria-label={`Select ${e.full_name}`}
                      checked={selected.has(e.identifier)}
                      onChange={(ev) => {
                        const next = new Set(selected);
                        if (ev.target.checked) next.add(e.identifier);
                        else next.delete(e.identifier);
                        setSelected(next);
                      }}
                    />
                  ) : null}
                </Td>
                <Td className="font-mono text-xs">{e.identifier}</Td>
                <Td>{e.full_name}</Td>
                <Td>
                  <Badge value={e.status} />
                </Td>
                <Td className="text-xs text-slate-500">
                  {[e.flag_reason ? titleCase(e.flag_reason) : e.manual_reason ? titleCase(e.manual_reason) : "", e.distance_m !== null ? `${Math.round(e.distance_m)} m` : ""]
                    .filter(Boolean)
                    .join(" · ")}
                </Td>
                <Td>
                  {e.status === "flagged" && e.attendance_id ? (
                    <span className="flex gap-1">
                      <Button size="sm" variant="secondary" onClick={() => setReview({ entry: e, action: "approve" })}>
                        Approve
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setReview({ entry: e, action: "reject" })}>
                        Reject
                      </Button>
                    </span>
                  ) : null}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>

      {review ? (
        <div role="dialog" aria-modal="true" aria-label="Review flagged scan" className="fixed inset-0 z-10 flex items-center justify-center bg-black/40 p-4">
          <Card className="w-full max-w-md">
            <CardTitle>
              {review.action === "approve" ? "Approve" : "Reject"} scan for {review.entry.full_name}
            </CardTitle>
            <Field label="Reason (recorded in the audit log)" htmlFor="review_reason">
              <Textarea id="review_reason" value={reviewReason} onChange={(e) => setReviewReason(e.target.value)} />
            </Field>
            <div className="mt-3 flex justify-end gap-2">
              <Button variant="secondary" onClick={() => { setReview(null); setReviewReason(""); }}>
                Cancel
              </Button>
              <Button
                variant={review.action === "approve" ? "primary" : "danger"}
                disabled={busy || reviewReason.trim().length < 3}
                onClick={() => {
                  const r = review;
                  void act(
                    () => api.request(`/attendance/${r.entry.attendance_id}/review`, { method: "POST", body: { action: r.action, reason: reviewReason.trim() } }),
                    () => `Scan ${r.action === "approve" ? "approved" : "rejected"}.`,
                  ).then(() => { setReview(null); setReviewReason(""); });
                }}
              >
                Confirm
              </Button>
            </div>
          </Card>
        </div>
      ) : null}
    </>
  );
}
