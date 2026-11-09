"use client";

import { useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { Table, Td, Th } from "@/components/ui/table";
import { useFetch } from "@/hooks/use-fetch";
import { formatDateTime } from "@/lib/utils";
import type { AuditEvent, Page } from "@/types/api";

export default function AuditPage() {
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useFetch<Page<AuditEvent>>("/admin/audit", { page, page_size: 25 });
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  return (
    <>
      <PageHeader title="Audit log" description="Append-only record of sensitive actions: corrections, device resets, account changes." />
      <Card>
        {loading ? <Spinner /> : null}
        {error ? <ErrorState error={error} onRetry={() => void reload()} /> : null}
        {data && data.items.length === 0 ? <EmptyState title="No events yet" /> : null}
        {data && data.items.length > 0 ? (
          <>
            <Table>
              <thead>
                <tr>
                  <Th>When</Th>
                  <Th>Actor</Th>
                  <Th>Action</Th>
                  <Th>Target</Th>
                  <Th>Reason</Th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((e) => (
                  <tr key={e.id}>
                    <Td className="whitespace-nowrap">{formatDateTime(e.created_at)}</Td>
                    <Td>{e.actor_id ?? "system"}</Td>
                    <Td className="font-mono text-xs">{e.action}</Td>
                    <Td className="text-xs">
                      {e.target_type} #{e.target_id}
                    </Td>
                    <Td className="text-xs text-slate-600">{e.reason ?? ""}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <div className="mt-3 flex items-center justify-between text-sm">
              <span className="text-slate-500">
                Page {data.page} of {pages} · {data.total} events
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
