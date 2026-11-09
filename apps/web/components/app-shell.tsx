"use client";

import { LogOut } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { OfflineBanner } from "@/features/offline-banner";
import { useAuth } from "@/lib/auth";
import { NAV } from "@/lib/roles";
import { cn, titleCase } from "@/lib/utils";

export function AppShell({ children }: { children: ReactNode }) {
  const { me, signOut } = useAuth();
  const pathname = usePathname();
  if (!me) return null;
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-6">
            <span className="font-semibold text-brand-700">Attendance</span>
            <nav aria-label="Main" className="flex flex-wrap gap-1">
              {NAV[me.role].map((item) => {
                const active = item.href === pathname || (item.href.length > 8 && pathname.startsWith(item.href));
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={cn("rounded-md px-3 py-1.5 text-sm", active ? "bg-brand-50 font-medium text-brand-700" : "text-slate-600 hover:bg-slate-100")}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="hidden text-right sm:block">
              <span className="block font-medium leading-tight">{me.full_name}</span>
              <span className="text-xs text-slate-500">{titleCase(me.role)}</span>
            </span>
            <Button variant="ghost" size="sm" onClick={() => void signOut()} aria-label="Sign out">
              <LogOut className="h-4 w-4" aria-hidden /> Sign out
            </Button>
          </div>
        </div>
      </header>
      <OfflineBanner />
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}
