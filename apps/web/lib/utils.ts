import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { config } from "@/lib/config";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** The API stores UTC; people read local time. */
export function formatDateTime(iso: string | null | undefined, timeZone: string = config.timezone): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone }).format(new Date(iso));
}

export function formatTime(iso: string | null | undefined, timeZone: string = config.timezone): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("en-GB", { timeStyle: "medium", timeZone }).format(new Date(iso));
}

export function percent(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${value.toFixed(1)}%`;
}

export function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
