import type { Role } from "@/types/api";

export const HOME: Record<Role, string> = {
  student: "/student",
  lecturer: "/lecturer",
  super_admin: "/admin",
};

/** Which URL prefix belongs to which role. The API enforces this too; this only improves UX. */
export function roleForPath(pathname: string): Role | null {
  if (pathname.startsWith("/student")) return "student";
  if (pathname.startsWith("/lecturer")) return "lecturer";
  if (pathname.startsWith("/admin")) return "super_admin";
  return null;
}

export const NAV: Record<Role, { href: string; label: string }[]> = {
  student: [
    { href: "/student", label: "My courses" },
    { href: "/student/scan", label: "Scan QR" },
    { href: "/student/history", label: "History" },
  ],
  lecturer: [
    { href: "/lecturer", label: "Sessions" },
    { href: "/lecturer/sessions/new", label: "New session" },
  ],
  super_admin: [
    { href: "/admin", label: "Overview" },
    { href: "/admin/users", label: "Users" },
    { href: "/admin/courses", label: "Courses" },
    { href: "/admin/venues", label: "Venues" },
    { href: "/admin/audit", label: "Audit log" },
  ],
};
