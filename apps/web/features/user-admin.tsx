"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Alert, EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/form";
import { Table, Td, Th } from "@/components/ui/table";
import { useFetch } from "@/hooks/use-fetch";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { titleCase } from "@/lib/utils";
import type { ImportResult, Page, Role, User } from "@/types/api";

const schema = z.object({
  identifier: z.string().min(2, "Enter a matric number or staff ID"),
  email: z.string().email("Enter a valid email"),
  full_name: z.string().min(2, "Enter the full name"),
  role: z.enum(["student", "lecturer", "super_admin"]),
  department: z.string(),
  level: z.string().refine((v) => v === "" || (Number(v) >= 100 && Number(v) <= 900), "e.g. 300"),
});
type Values = z.infer<typeof schema>;

export function UserAdmin() {
  const { api, me } = useAuth();
  const [q, setQ] = useState("");
  const [role, setRole] = useState<"" | Role>("");
  const [page, setPage] = useState(1);
  const users = useFetch<Page<User>>("/users", { q: q || undefined, role: role || undefined, page, page_size: 15 });
  const [msg, setMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { identifier: "", email: "", full_name: "", role: "student", department: "", level: "" } });

  async function createUser(v: Values) {
    setMsg(null);
    try {
      await api.request("/users", { method: "POST", body: { ...v, department: v.department || null, level: v.level ? Number(v.level) : null } });
      reset();
      setMsg({ tone: "success", text: `Created ${v.identifier}. They can now sign in with ${v.email}.` });
      await users.reload();
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof ApiError ? e.message : "Could not create the user." });
    }
  }

  async function importCsv(file: File | undefined) {
    if (!file) return;
    setMsg(null);
    setImportResult(null);
    const form = new FormData();
    form.set("file", file);
    try {
      setImportResult(await api.request<ImportResult>("/users/import", { method: "POST", form }));
      await users.reload();
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof ApiError ? e.message : "Import failed." });
    }
  }

  async function patch(u: User, body: Partial<Pick<User, "is_active">>) {
    setMsg(null);
    try {
      await api.request(`/users/${u.id}`, { method: "PATCH", body });
      await users.reload();
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof ApiError ? e.message : "Update failed." });
    }
  }

  async function resetDevice(u: User) {
    setMsg(null);
    try {
      await api.request(`/users/${u.id}/reset-device`, { method: "POST" });
      setMsg({ tone: "success", text: `${u.full_name} can bind a new phone.` });
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof ApiError ? e.message : "Reset failed." });
    }
  }

  const pages = users.data ? Math.max(1, Math.ceil(users.data.total / users.data.page_size)) : 1;
  return (
    <div className="space-y-4">
      {msg ? <Alert tone={msg.tone}>{msg.text}</Alert> : null}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardTitle>Add a user</CardTitle>
          <form onSubmit={handleSubmit(createUser)} className="space-y-3" noValidate aria-label="Add user">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Matric no. / staff ID" htmlFor="u_identifier" error={errors.identifier?.message}>
                <Input id="u_identifier" {...register("identifier")} />
              </Field>
              <Field label="Role" htmlFor="u_role">
                <Select id="u_role" {...register("role")}>
                  <option value="student">Student</option>
                  <option value="lecturer">Lecturer</option>
                  <option value="super_admin">Super admin</option>
                </Select>
              </Field>
            </div>
            <Field label="Full name" htmlFor="u_name" error={errors.full_name?.message}>
              <Input id="u_name" {...register("full_name")} />
            </Field>
            <Field label="Email (used to sign in)" htmlFor="u_email" error={errors.email?.message}>
              <Input id="u_email" type="email" {...register("email")} />
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Department" htmlFor="u_dept">
                <Input id="u_dept" {...register("department")} />
              </Field>
              <Field label="Level" htmlFor="u_level" error={errors.level?.message}>
                <Input id="u_level" inputMode="numeric" {...register("level")} />
              </Field>
            </div>
            <Button type="submit" disabled={isSubmitting}>
              Create user
            </Button>
          </form>
        </Card>
        <Card>
          <CardTitle>Bulk import (CSV)</CardTitle>
          <p className="mb-3 text-sm text-slate-600">
            Columns: <code>identifier,email,full_name,role,department,level</code>. Existing users are skipped.
          </p>
          <Input type="file" accept=".csv,text/csv" aria-label="CSV file" onChange={(e) => void importCsv(e.target.files?.[0])} />
          {importResult ? (
            <div className="mt-3 space-y-2 text-sm">
              <Alert tone={importResult.errors.length ? "warning" : "success"} title="Import finished">
                {importResult.created} created · {importResult.skipped_existing} skipped · {importResult.errors.length} errors
              </Alert>
              {importResult.errors.slice(0, 10).map((e) => (
                <p key={e.row} className="text-red-700">
                  Row {e.row}: {e.message}
                </p>
              ))}
            </div>
          ) : null}
        </Card>
      </div>
      <Card>
        <CardTitle
          action={
            <div className="flex gap-2">
              <Input placeholder="Search name, ID, email" aria-label="Search users" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} className="w-56" />
              <Select aria-label="Filter by role" value={role} onChange={(e) => { setRole(e.target.value as "" | Role); setPage(1); }} className="w-36">
                <option value="">All roles</option>
                <option value="student">Students</option>
                <option value="lecturer">Lecturers</option>
                <option value="super_admin">Admins</option>
              </Select>
            </div>
          }
        >
          Users
        </CardTitle>
        {users.loading && !users.data ? <Spinner /> : null}
        {users.error ? <ErrorState error={users.error} onRetry={() => void users.reload()} /> : null}
        {users.data && users.data.items.length === 0 ? <EmptyState title="No users match" /> : null}
        {users.data && users.data.items.length > 0 ? (
          <>
            <Table>
              <thead>
                <tr>
                  <Th>ID</Th>
                  <Th>Name</Th>
                  <Th>Role</Th>
                  <Th>Signed in before</Th>
                  <Th>Status</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {users.data.items.map((u) => (
                  <tr key={u.id}>
                    <Td className="font-mono text-xs">{u.identifier}</Td>
                    <Td>
                      {u.full_name}
                      <span className="block text-xs text-slate-500">{u.email}</span>
                    </Td>
                    <Td>{titleCase(u.role)}</Td>
                    <Td>{u.linked ? "Yes" : "Not yet"}</Td>
                    <Td>
                      <Badge value={u.is_active ? "open" : "cancelled"} label={u.is_active ? "Active" : "Disabled"} />
                    </Td>
                    <Td>
                      <span className="flex gap-1">
                        <Button size="sm" variant="secondary" disabled={u.id === me?.id} onClick={() => void patch(u, { is_active: !u.is_active })}>
                          {u.is_active ? "Disable" : "Enable"}
                        </Button>
                        {u.role === "student" ? (
                          <Button size="sm" variant="ghost" onClick={() => void resetDevice(u)}>
                            Reset phone
                          </Button>
                        ) : null}
                      </span>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <div className="mt-3 flex items-center justify-between text-sm">
              <span className="text-slate-500">
                Page {users.data.page} of {pages} · {users.data.total} users
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
    </div>
  );
}
