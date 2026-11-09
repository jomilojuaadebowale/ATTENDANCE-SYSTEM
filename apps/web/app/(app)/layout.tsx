"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { AppShell } from "@/components/app-shell";
import { Alert, Spinner } from "@/components/ui/feedback";
import { useAuth } from "@/lib/auth";
import { HOME, roleForPath } from "@/lib/roles";

/** Route protection for UX only. Every API call is authorized again on the server. */
export default function AppLayout({ children }: { children: ReactNode }) {
  const { status, me } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const needed = roleForPath(pathname);

  useEffect(() => {
    if (status === "signed_out" || status === "not_provisioned") router.replace("/login");
    else if (status === "signed_in" && me && needed && needed !== me.role) router.replace(HOME[me.role]);
  }, [status, me, needed, router]);

  if (status === "loading") return <Spinner label="Checking your session" />;
  if (status !== "signed_in" || !me) return <Spinner label="Redirecting to sign in" />;
  if (needed && needed !== me.role)
    return (
      <div className="p-6">
        <Alert tone="error" title="Not allowed">
          This area is not available for your account.
        </Alert>
      </div>
    );
  return <AppShell>{children}</AppShell>;
}
