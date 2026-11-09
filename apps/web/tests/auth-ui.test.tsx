import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Me } from "@/types/api";

const replace = vi.fn();
let pathname = "/student";
let auth: { status: string; me: Me | null; error: string | null; signIn: ReturnType<typeof vi.fn>; signOut: ReturnType<typeof vi.fn>; api: unknown };

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, push: vi.fn() }), usePathname: () => pathname }));
vi.mock("next/link", () => ({ default: ({ href, children, ...p }: { href: string; children: React.ReactNode }) => <a href={href} {...p}>{children}</a> }));
vi.mock("@/lib/auth", () => ({ useAuth: () => auth }));
vi.mock("@/features/offline-banner", () => ({ OfflineBanner: () => null }));

import AppLayout from "@/app/(app)/layout";
import { LoginForm } from "@/features/login-form";
import { HOME, NAV, roleForPath } from "@/lib/roles";

const me = (role: Me["role"]): Me => ({ id: 1, identifier: "X1", email: "x@example.edu", full_name: "Test Person", department: null, level: null, role, is_active: true, linked: true, created_at: "2026-01-01T00:00:00Z", active_device: null });

beforeEach(() => {
  replace.mockClear();
  auth = { status: "signed_out", me: null, error: null, signIn: vi.fn().mockResolvedValue(undefined), signOut: vi.fn(), api: {} };
});

describe("role routing helpers", () => {
  it("maps URL prefixes to roles", () => {
    expect(roleForPath("/student/scan")).toBe("student");
    expect(roleForPath("/lecturer/sessions/1")).toBe("lecturer");
    expect(roleForPath("/admin/users")).toBe("super_admin");
    expect(roleForPath("/login")).toBeNull();
  });
  it("each role has a home and navigation", () => {
    for (const role of ["student", "lecturer", "super_admin"] as const) {
      expect(HOME[role]).toBeTruthy();
      expect(NAV[role].length).toBeGreaterThan(0);
    }
  });
});

describe("<AppLayout /> route protection", () => {
  it("sends signed-out visitors to the login page", async () => {
    pathname = "/student";
    render(<AppLayout>secret</AppLayout>);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
  });

  it("sends unprovisioned accounts to the login page", async () => {
    auth.status = "not_provisioned";
    render(<AppLayout>secret</AppLayout>);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
  });

  it("redirects a student away from admin pages and does not render them", async () => {
    auth.status = "signed_in";
    auth.me = me("student");
    pathname = "/admin/users";
    render(<AppLayout>admin-only</AppLayout>);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/student"));
    expect(screen.queryByText("admin-only")).not.toBeInTheDocument();
    expect(screen.getByText(/not available for your account/i)).toBeInTheDocument();
  });

  it("redirects a lecturer away from student pages", async () => {
    auth.status = "signed_in";
    auth.me = me("lecturer");
    pathname = "/student/scan";
    render(<AppLayout>scanner</AppLayout>);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/lecturer"));
  });

  it("shows role-specific navigation and content to the right user", () => {
    auth.status = "signed_in";
    auth.me = me("super_admin");
    pathname = "/admin";
    render(<AppLayout>overview</AppLayout>);
    expect(screen.getByText("overview")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Audit log" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Scan QR" })).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("lets the user sign out", async () => {
    auth.status = "signed_in";
    auth.me = me("student");
    pathname = "/student";
    render(<AppLayout>x</AppLayout>);
    await userEvent.click(screen.getByRole("button", { name: /sign out/i }));
    expect(auth.signOut).toHaveBeenCalled();
  });
});

describe("<LoginForm />", () => {
  it("validates the email before signing in", async () => {
    render(<LoginForm />);
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText(/enter your email/i)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/university email/i), "not-an-email");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText(/valid email address/i)).toBeInTheDocument();
    expect(auth.signIn).not.toHaveBeenCalled();
  });

  it("signs in with the entered email (dev mode has no password)", async () => {
    render(<LoginForm />);
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
    expect(screen.getByText(/development sign-in/i)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/university email/i), "student1@example.edu");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => expect(auth.signIn).toHaveBeenCalledWith("student1@example.edu", ""));
  });

  it("shows an error when sign-in fails", async () => {
    auth.signIn.mockRejectedValueOnce(new Error("bad"));
    render(<LoginForm />);
    await userEvent.type(screen.getByLabelText(/university email/i), "a@example.edu");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText(/sign-in failed/i)).toBeInTheDocument();
  });

  it("explains accounts the administrator has not set up", () => {
    auth.status = "not_provisioned";
    auth.error = "Your account has not been set up. Contact your department administrator.";
    render(<LoginForm />);
    expect(screen.getByText(/has not been set up/i)).toBeInTheDocument();
  });

  it("sends signed-in users to their home page", async () => {
    auth.status = "signed_in";
    auth.me = me("lecturer");
    render(<LoginForm />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/lecturer"));
  });
});
