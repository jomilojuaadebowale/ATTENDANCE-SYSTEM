"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Alert, EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { Field, Input, Textarea } from "@/components/ui/form";
import { Table, Td, Th } from "@/components/ui/table";
import { useFetch } from "@/hooks/use-fetch";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Assignment, Course, EnrollResult, Enrollment, Page } from "@/types/api";

export function CourseAdmin() {
  const { api } = useAuth();
  const courses = useFetch<Page<Course>>("/courses", { page_size: 100 });
  const [selected, setSelected] = useState<number | null>(null);
  const enrollments = useFetch<Enrollment[]>(selected ? `/courses/${selected}/enrollments` : null);
  const assignments = useFetch<Assignment[]>(selected ? `/courses/${selected}/assignments` : null);
  const [msg, setMsg] = useState<{ tone: "success" | "error" | "warning"; text: string } | null>(null);
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [matrics, setMatrics] = useState("");
  const [lecturer, setLecturer] = useState("");

  async function run(fn: () => Promise<string>, after?: () => Promise<void>) {
    setMsg(null);
    try {
      setMsg({ tone: "success", text: await fn() });
      await after?.();
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof ApiError ? e.message : "Something went wrong." });
    }
  }

  return (
    <div className="space-y-4">
      {msg ? <Alert tone={msg.tone}>{msg.text}</Alert> : null}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardTitle>Courses</CardTitle>
          <form
            className="mb-4 space-y-2"
            aria-label="Add course"
            onSubmit={(e) => {
              e.preventDefault();
              void run(
                async () => {
                  await api.request("/courses", { method: "POST", body: { code, title } });
                  setCode("");
                  setTitle("");
                  return "Course created.";
                },
                async () => void (await courses.reload()),
              );
            }}
          >
            <Field label="Course code" htmlFor="c_code">
              <Input id="c_code" value={code} onChange={(e) => setCode(e.target.value)} placeholder="CSC 308" required minLength={2} />
            </Field>
            <Field label="Title" htmlFor="c_title">
              <Input id="c_title" value={title} onChange={(e) => setTitle(e.target.value)} required minLength={2} />
            </Field>
            <Button type="submit" disabled={!code || !title}>
              Add course
            </Button>
          </form>
          {courses.loading && !courses.data ? <Spinner /> : null}
          {courses.error ? <ErrorState error={courses.error} onRetry={() => void courses.reload()} /> : null}
          {courses.data?.items.length === 0 ? <EmptyState title="No courses yet" /> : null}
          <ul className="divide-y divide-slate-100">
            {courses.data?.items.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => setSelected(c.id)}
                  aria-pressed={selected === c.id}
                  className={`w-full px-2 py-2 text-left text-sm hover:bg-slate-50 ${selected === c.id ? "bg-brand-50 font-medium" : ""}`}
                >
                  {c.code} <span className="text-slate-500">— {c.title}</span>
                </button>
              </li>
            ))}
          </ul>
        </Card>
        <div className="space-y-4 lg:col-span-2">
          {!selected ? (
            <Card>
              <EmptyState title="Select a course">Choose a course to manage its lecturers and enrolled students.</EmptyState>
            </Card>
          ) : (
            <>
              <Card>
                <CardTitle>Lecturers</CardTitle>
                <form
                  className="mb-3 flex gap-2"
                  aria-label="Assign lecturer"
                  onSubmit={(e) => {
                    e.preventDefault();
                    void run(
                      async () => {
                        await api.request(`/courses/${selected}/assignments`, { method: "POST", body: { lecturer_identifier: lecturer } });
                        setLecturer("");
                        return "Lecturer assigned for the current term.";
                      },
                      async () => void (await assignments.reload()),
                    );
                  }}
                >
                  <Input aria-label="Lecturer staff ID" value={lecturer} onChange={(e) => setLecturer(e.target.value)} placeholder="Staff ID, e.g. STF001" />
                  <Button type="submit" disabled={!lecturer}>
                    Assign
                  </Button>
                </form>
                {assignments.data?.length === 0 ? <p className="text-sm text-slate-500">No lecturer assigned yet.</p> : null}
                <ul className="divide-y divide-slate-100 text-sm">
                  {assignments.data?.map((a) => (
                    <li key={a.id} className="flex items-center justify-between py-2">
                      <span>
                        {a.lecturer_name} <span className="text-slate-500">({a.lecturer_identifier}) · {a.academic_year} S{a.semester}</span>
                      </span>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => void run(async () => { await api.request(`/courses/${selected}/assignments/${a.id}`, { method: "DELETE" }); return "Assignment removed."; }, async () => void (await assignments.reload()))}
                      >
                        Remove
                      </Button>
                    </li>
                  ))}
                </ul>
              </Card>
              <Card>
                <CardTitle>Enrolled students ({enrollments.data?.length ?? 0})</CardTitle>
                <form
                  className="mb-3 space-y-2"
                  aria-label="Enrol students"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const identifiers = matrics.split(/[\s,;]+/).filter(Boolean);
                    void run(
                      async () => {
                        const r = await api.request<EnrollResult>(`/courses/${selected}/enrollments`, { method: "POST", body: { identifiers } });
                        setMatrics("");
                        return `Enrolled ${r.enrolled}, already enrolled ${r.already_enrolled}${r.unknown_identifiers.length ? `, unknown: ${r.unknown_identifiers.join(", ")}` : ""}${r.not_students.length ? `, not students: ${r.not_students.join(", ")}` : ""}.`;
                      },
                      async () => void (await enrollments.reload()),
                    );
                  }}
                >
                  <Textarea aria-label="Matric numbers to enrol" value={matrics} onChange={(e) => setMatrics(e.target.value)} placeholder="Paste matric numbers, separated by spaces, commas or new lines" />
                  <Button type="submit" disabled={!matrics.trim()}>
                    Enrol students
                  </Button>
                </form>
                {enrollments.loading ? <Spinner /> : null}
                {enrollments.data && enrollments.data.length > 0 ? (
                  <div className="max-h-72 overflow-y-auto">
                    <Table>
                      <thead>
                        <tr>
                          <Th>Matric no.</Th>
                          <Th>Name</Th>
                          <Th />
                        </tr>
                      </thead>
                      <tbody>
                        {enrollments.data.map((en) => (
                          <tr key={en.student_id}>
                            <Td className="font-mono text-xs">{en.identifier}</Td>
                            <Td>{en.full_name}</Td>
                            <Td>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => void run(async () => { await api.request(`/courses/${selected}/enrollments/${en.student_id}`, { method: "DELETE" }); return "Enrolment removed."; }, async () => void (await enrollments.reload()))}
                              >
                                Remove
                              </Button>
                            </Td>
                          </tr>
                        ))}
                      </tbody>
                    </Table>
                  </div>
                ) : null}
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
