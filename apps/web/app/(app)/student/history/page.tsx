"use client";

import { useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { Table, Td, Th } from "@/components/ui/table";
import { PendingScans } from "@/features/pending-scans";
import { useFetch } from "@/hooks/use-fetch";
import { formatDateTime, titleCase } from "@/lib/utils";
import type { MyAttendance, Page } from "@/types/api";

export default function HistoryPage() {
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useFetch<Page<MyAttendance>>("/attendance/me", { page, page_size: 15 });
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  return (
    <>
      <PageHeader title="Attendance history" description="Every record the server has stored for you." />
      <PendingScans />
      <Card>
        {loading ? <Spinner /> : null}
        {error ? <ErrorState error={error} onRetry={() => void reload()} /> : null}
        {data && data.items.length === 0 ? <EmptyState title="No attendance recorded yet" /> : null}
        {data && data.items.length > 0 ? (
          <>
            <Table>
              <thead>
                <tr>
                  <Th>Course</Th>
                  <Th>Lecture</Th>
                  <Th>Status</Th>
                  <Th>How</Th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((r) => (
                  <tr key={r.id}>
                    <Td className="font-medium">{r.course_code}</Td>
                    <Td>{formatDateTime(r.session_starts_at)}</Td>
                    <Td>
                      <Badge value={r.status} />
                      {r.flag_reason ? <span className="ml-2 text-xs text-slate-500">{titleCase(r.flag_reason)}</span> : null}
                    </Td>
                    <Td>{r.marked_manually ? "Marked by lecturer" : "Scanned"}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <div className="mt-3 flex items-center justify-between text-sm">
              <span className="text-slate-500">
                Page {data.page} of {pages} · {data.total} records
              </span>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                  Previous
                </Button>
                <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>
                  Next
                </Button>
              </div>
            </div>
          </>
        ) : null}
      </Card>
    </>
  );
}
