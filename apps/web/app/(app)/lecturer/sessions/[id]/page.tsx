"use client";

import { use } from "react";
import { SessionConsole } from "@/features/session-console";

export default function SessionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <SessionConsole sessionId={id} />;
}
