"use client";

import { PageHeader } from "@/components/page-header";
import { Card, CardTitle } from "@/components/ui/card";
import { ErrorState, Spinner } from "@/components/ui/feedback";
import { Stat } from "@/components/ui/stat";
import { useFetch } from "@/hooks/use-fetch";
import { titleCase } from "@/lib/utils";
import type { AdminOverview } from "@/types/api";

function Breakdown({ title, data }: { title: string; data: Record<string, number> }) {
  const entries = Object.entries(data);
  return (
    <Card>
      <CardTitle>{title}</CardTitle>
      {entries.length === 0 ? <p className="text-sm text-slate-500">Nothing yet.</p> : null}
      <ul className="space-y-1 text-sm">
        {entries.map(([k, v]) => (
          <li key={k} className="flex justify-between">
            <span>{titleCase(k)}</span>
            <span className="font-medium">{v}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export default function AdminHome() {
  const { data, error, loading, reload } = useFetch<AdminOverview>("/admin/overview");
  return (
    <>
      <PageHeader title="System overview" description="Live counts from the database." />
      {loading ? <Spinner /> : null}
      {error ? <ErrorState error={error} onRetry={() => void reload()} /> : null}
      {data ? (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Users" value={Object.values(data.users_by_role).reduce((a, b) => a + b, 0)} />
            <Stat label="Courses" value={data.courses} />
            <Stat label="Venues" value={data.venues} />
            <Stat label="Audit events (7 days)" value={data.audit_events_last_7_days} />
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            <Breakdown title="Users by role" data={data.users_by_role} />
            <Breakdown title="Sessions by status" data={data.sessions_by_status} />
            <Breakdown title="Attendance records by status" data={data.attendance_by_status} />
          </div>
        </>
      ) : null}
    </>
  );
}
