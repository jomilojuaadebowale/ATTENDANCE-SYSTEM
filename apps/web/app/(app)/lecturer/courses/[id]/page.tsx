"use client";

import { Download } from "lucide-react";
import { use, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Alert, EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { Stat } from "@/components/ui/stat";
import { Table, Td, Th } from "@/components/ui/table";
import { useFetch } from "@/hooks/use-fetch";
import { useAuth } from "@/lib/auth";
import { percent } from "@/lib/utils";
import type { CourseReport } from "@/types/api";

export default function CourseReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { api } = useAuth();
  const { data, error, loading, reload } = useFetch<CourseReport>(`/courses/${id}/report`);
  const [exportError, setExportError] = useState<string | null>(null);

  async function exportCsv() {
    setExportError(null);
    try {
      const { blob, filename } = await api.download(`/courses/${id}/report.csv`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setExportError("Could not export the report.");
    }
  }

  return (
    <>
      <PageHeader
        title={data ? `${data.course_code} attendance report` : "Attendance report"}
        description="Counts closed sessions only. Open and cancelled sessions are not included."
        actions={
          <Button variant="secondary" onClick={() => void exportCsv()} disabled={!data}>
            <Download className="h-4 w-4" aria-hidden /> Export CSV
          </Button>
        }
      />
      {exportError ? <Alert tone="error">{exportError}</Alert> : null}
      {loading ? <Spinner /> : null}
      {error ? <ErrorState error={error} onRetry={() => void reload()} /> : null}
      {data ? (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Sessions counted" value={data.sessions_counted} />
            <Stat label="Still open/scheduled" value={data.sessions_open_or_scheduled} />
            <Stat label="Students" value={data.rows.length} />
            <Stat label="Eligibility threshold" value={`${data.threshold_percent}%`} />
          </div>
          <Card>
            {data.rows.length === 0 ? <EmptyState title="No students enrolled" /> : null}
            {data.rows.length > 0 ? (
              <Table>
                <thead>
                  <tr>
                    <Th>Matric no.</Th>
                    <Th>Name</Th>
                    <Th>Present</Th>
                    <Th>Pending</Th>
                    <Th>Percentage</Th>
                    <Th>Eligible</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((r) => (
                    <tr key={r.student_id}>
                      <Td className="font-mono text-xs">{r.identifier}</Td>
                      <Td>{r.full_name}</Td>
                      <Td>
                        {r.present} / {r.sessions_counted}
                      </Td>
                      <Td>{r.pending_review}</Td>
                      <Td>{percent(r.percentage)}</Td>
                      <Td>{r.eligible === null ? "—" : <Badge value={r.eligible ? "verified" : "flagged"} label={r.eligible ? "Yes" : "No"} />}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : null}
          </Card>
        </>
      ) : null}
    </>
  );
}
