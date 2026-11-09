import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApi } from "@/lib/api";

vi.mock("next/link", () => ({ default: ({ href, children, ...p }: { href: string; children: React.ReactNode }) => <a href={href} {...p}>{children}</a> }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/" }));

const routes = new Map<string, () => Response>();
const calls: { url: string; method: string; body?: string }[] = [];
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

vi.mock("@/lib/auth", async () => {
  const { createApi } = await import("@/lib/api");
  const api = createApi(async () => "dev:test@example.edu", "http://api.test");
  return { useAuth: () => ({ api, me: { id: 1, role: "student", full_name: "Test", identifier: "X", email: null }, status: "signed_in", error: null, signIn: vi.fn(), signOut: vi.fn() }) };
});

beforeEach(() => {
  routes.clear();
  calls.length = 0;
  vi.stubGlobal("fetch", async (url: string, init: RequestInit = {}) => {
    const path = url.replace("http://api.test", "").split("?")[0] ?? "";
    calls.push({ url, method: init.method ?? "GET", body: init.body as string | undefined });
    const handler = routes.get(`${init.method ?? "GET"} ${path}`);
    return handler ? handler() : json({ error: { code: "not_found", message: `no route ${path}` } }, 404);
  });
});
afterEach(() => vi.unstubAllGlobals());

import StudentHome from "@/app/(app)/student/page";
import HistoryPage from "@/app/(app)/student/history/page";
import AdminHome from "@/app/(app)/admin/page";
import { CourseAdmin } from "@/features/course-admin";

describe("pages render REAL data from the API (nothing hardcoded)", () => {
  it("student dashboard shows percentages from the summary endpoint", async () => {
    routes.set("GET /me/attendance-summary", () =>
      json([
        { course_id: 1, course_code: "CSC 308", course_title: "Numerical Computation", sessions_counted: 4, present: 3, pending_review: 1, percentage: 75, eligible: true },
        { course_id: 2, course_code: "MTH 302", course_title: "Differential Equations", sessions_counted: 4, present: 1, pending_review: 0, percentage: 25, eligible: false },
      ]),
    );
    render(<StudentHome />);
    expect(await screen.findByText("CSC 308")).toBeInTheDocument();
    expect(screen.getByText("75.0%")).toBeInTheDocument();
    expect(screen.getByText("25.0%")).toBeInTheDocument();
    expect(screen.getByText(/1 pending review/)).toBeInTheDocument();
    expect(screen.getByText(/below the 75% requirement/)).toBeInTheDocument();
    expect(screen.getAllByRole("progressbar")).toHaveLength(2);
    expect(screen.getByText("50.0%")).toBeInTheDocument(); // overall = 4/8, computed from the data
  });

  it("student dashboard empty and error states", async () => {
    routes.set("GET /me/attendance-summary", () => json([]));
    const { unmount } = render(<StudentHome />);
    expect(await screen.findByText(/not enrolled in any course/i)).toBeInTheDocument();
    unmount();
    routes.set("GET /me/attendance-summary", () => json({ error: { code: "boom", message: "Database is down" } }, 500));
    render(<StudentHome />);
    expect(await screen.findByText("Database is down")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("history lists records, how they were made, and paginates", async () => {
    routes.set("GET /attendance/me", () =>
      json({ items: [{ id: 1, session_id: "s", course_code: "CSC 308", course_title: "x", session_starts_at: "2026-10-29T09:00:00Z", status: "manual", flag_reason: null, marked_manually: true, received_at: "2026-10-29T09:05:00Z" }], total: 31, page: 1, page_size: 15 }),
    );
    render(<HistoryPage />);
    expect(await screen.findByText("Marked by lecturer")).toBeInTheDocument();
    expect(screen.getByText(/Page 1 of 3 · 31 records/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(calls.some((c) => c.url.includes("page=2"))).toBe(true));
  });

  it("admin overview shows database counts", async () => {
    routes.set("GET /admin/overview", () => json({ users_by_role: { student: 40, lecturer: 3, super_admin: 1 }, courses: 12, venues: 5, sessions_by_status: { open: 2, closed: 9 }, attendance_by_status: { verified: 300, manual: 14 }, audit_events_last_7_days: 27 }));
    render(<AdminHome />);
    expect(await screen.findByText("44")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("27")).toBeInTheDocument();
    expect(screen.getByText("Super Admin")).toBeInTheDocument();
    expect(screen.getByText("300")).toBeInTheDocument();
  });
});

describe("admin actions call the API", () => {
  it("enrols pasted matric numbers and reports the server's answer", async () => {
    routes.set("GET /courses", () => json({ items: [{ id: 5, code: "CSC 308", title: "Numerical Computation", department: null }], total: 1, page: 1, page_size: 100 }));
    routes.set("GET /courses/5/enrollments", () => json([]));
    routes.set("GET /courses/5/assignments", () => json([]));
    routes.set("POST /courses/5/enrollments", () => json({ enrolled: 2, already_enrolled: 1, unknown_identifiers: ["NOPE/1"], not_students: [] }));
    render(<CourseAdmin />);
    await userEvent.click(await screen.findByRole("button", { name: /CSC 308/ }));
    const box = await screen.findByLabelText(/matric numbers to enrol/i);
    await userEvent.type(box, "CSC/2022/001, CSC/2022/002 NOPE/1");
    await userEvent.click(screen.getByRole("button", { name: /enrol students/i }));
    expect(await screen.findByText(/Enrolled 2, already enrolled 1, unknown: NOPE\/1/)).toBeInTheDocument();
    const post = calls.find((c) => c.method === "POST" && c.url.endsWith("/courses/5/enrollments"));
    expect(JSON.parse(post?.body ?? "{}")).toEqual({ identifiers: ["CSC/2022/001", "CSC/2022/002", "NOPE/1"] });
  });

  it("shows the server's error when an action is refused", async () => {
    routes.set("GET /courses", () => json({ items: [], total: 0, page: 1, page_size: 100 }));
    routes.set("POST /courses", () => json({ error: { code: "course_code_taken", message: "A course with that code already exists" } }, 409));
    render(<CourseAdmin />);
    const form = await screen.findByRole("form", { name: /add course/i });
    await userEvent.type(within(form).getByLabelText(/course code/i), "CSC 308");
    await userEvent.type(within(form).getByLabelText(/^title/i), "Duplicate");
    await userEvent.click(within(form).getByRole("button", { name: /add course/i }));
    expect(await screen.findByText("A course with that code already exists")).toBeInTheDocument();
  });
});

describe("sanity", () => {
  it("createApi is the real client", () => expect(typeof createApi).toBe("function"));
});
