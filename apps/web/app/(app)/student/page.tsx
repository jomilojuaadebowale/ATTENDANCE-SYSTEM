"use client";

import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { ProgressBar, Stat } from "@/components/ui/stat";
import { useFetch } from "@/hooks/use-fetch";
import { percent } from "@/lib/utils";
import type { MyCourseSummary } from "@/types/api";

export default function StudentHome() {
  const summary = useFetch<MyCourseSummary[]>("/me/attendance-summary");
  const overall = (() => {
    const rows = summary.data ?? [];
    const counted = rows.reduce((n, r) => n + r.sessions_counted, 0);
    const present = rows.reduce((n, r) => n + r.present, 0);
    return counted ? (present / counted) * 100 : null;
  })();

  return (
    <>
      <PageHeader
        title="My attendance"
        description="Percentages count only finished (closed) sessions. Flagged scans count after your lecturer approves them."
        actions={
          <Link href="/student/scan">
            <Button>Scan QR</Button>
          </Link>
        }
      />
      {summary.loading ? <Spinner /> : null}
      {summary.error ? <ErrorState error={summary.error} onRetry={() => void summary.reload()} /> : null}
      {summary.data && summary.data.length === 0 ? (
        <EmptyState title="You are not enrolled in any course this term">Contact your department if this is wrong.</EmptyState>
      ) : null}
      {summary.data && summary.data.length > 0 ? (
        <>
          <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Stat label="Courses" value={summary.data.length} />
            <Stat label="Sessions attended" value={summary.data.reduce((n, r) => n + r.present, 0)} />
            <Stat label="Overall" value={percent(overall)} hint="Across closed sessions" />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {summary.data.map((c) => (
              <Card key={c.course_id}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h2 className="font-semibold">{c.course_code}</h2>
                    <p className="text-sm text-slate-600">{c.course_title}</p>
                  </div>
                  <p className="text-xl font-semibold">{percent(c.percentage)}</p>
                </div>
                <div className="mt-3">
                  <ProgressBar value={c.percentage} threshold={75} />
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  {c.present} of {c.sessions_counted} sessions
                  {c.pending_review ? ` · ${c.pending_review} pending review` : ""}
                  {c.eligible === false ? " · below the 75% requirement" : ""}
                </p>
              </Card>
            ))}
          </div>
        </>
      ) : null}
    </>
  );
}
