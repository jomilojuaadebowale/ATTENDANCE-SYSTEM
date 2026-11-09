"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Spinner } from "@/components/ui/feedback";
import { useAuth } from "@/lib/auth";
import { HOME } from "@/lib/roles";

export default function Index() {
  const { status, me } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (status === "signed_in" && me) router.replace(HOME[me.role]);
    else if (status === "signed_out" || status === "not_provisioned") router.replace("/login");
  }, [status, me, router]);
  return <Spinner />;
}
