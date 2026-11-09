"use client";

import Link from "next/link";
import { useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { Select } from "@/components/ui/form";
import { Table, Td, Th } from "@/components/ui/table";
import { useFetch } from "@/hooks/use-fetch";
import { formatDateTime } from "@/lib/utils";
import type { ClassSession, MyCourse, Page } from "@/types/api";

export default function LecturerHome() {
  const courses = useFetch<MyCourse[]>("/me/courses");
  const [courseId, setCourseId] = useState("");
  const sessions = useFetch<Page<ClassSession>>("/sessions", { course_id: courseId || undefined, page_size: 20 });

  return (
    <>
      <PageHeader
        title="My courses and sessions"
        actions={
          <Link href="/lecturer/sessions/new">
            <Button>New attendance session</Button>
          </Link>
        }
      />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardTitle>Courses this term</CardTitle>
          {courses.loading ? <Spinner /> : null}
          {courses.error ? <ErrorState error={courses.error} onRetry={() => void courses.reload()} /> : null}
          {courses.data && courses.data.length === 0 ? <EmptyState title="No courses assigned">Ask an administrator to assign your courses.</EmptyState> : null}
          <ul className="divide-y divide-slate-100">
            {courses.data?.map((c) => (
              <li key={c.id} className="flex items-center justify-between gap-2 py-2">
                <div>
                  <p className="font-medium">{c.code}</p>
                  <p className="text-xs text-slate-500">{c.title}</p>
                </div>
                <Link className="text-sm text-brand-600 hover:underline" href={`/lecturer/courses/${c.id}`}>
                  Report
                </Link>
              </li>
            ))}
          </ul>
        </Card>
        <Card className="lg:col-span-2">
          <CardTitle
            action={
              <Select aria-label="Filter by course" value={courseId} onChange={(e) => setCourseId(e.target.value)} className="w-40">
                <option value="">All courses</option>
                {courses.data?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.code}
                  </option>
                ))}
              </Select>
            }
          >
            Sessions
          </CardTitle>
          {sessions.loading ? <Spinner /> : null}
          {sessions.error ? <ErrorState error={sessions.error} onRetry={() => void sessions.reload()} /> : null}
          {sessions.data && sessions.data.items.length === 0 ? <EmptyState title="No sessions yet">Create one to start taking attendance.</EmptyState> : null}
          {sessions.data && sessions.data.items.length > 0 ? (
            <Table>
              <thead>
                <tr>
                  <Th>Course</Th>
                  <Th>Starts</Th>
                  <Th>Venue</Th>
                  <Th>Present</Th>
                  <Th>Status</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {sessions.data.items.map((s) => (
                  <tr key={s.id}>
                    <Td className="font-medium">{s.course_code}</Td>
                    <Td>{formatDateTime(s.starts_at)}</Td>
                    <Td>{s.venue_name ?? "My location"}</Td>
                    <Td>{s.attendance_count ?? 0}</Td>
                    <Td>
                      <Badge value={s.status} />
                    </Td>
                    <Td>
                      <Link className="text-brand-600 hover:underline" href={`/lecturer/sessions/${s.id}`}>
                        Open
                      </Link>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : null}
        </Card>
      </div>
    </>
  );
}
