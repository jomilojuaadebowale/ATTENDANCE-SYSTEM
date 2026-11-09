"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export interface FetchState<T> {
  data: T | null;
  error: ApiError | null;
  /** True while a request for the CURRENT path/query is in flight (previous data stays available). */
  loading: boolean;
  /** Ask for a fresh copy. Previous data stays visible until the new response arrives. */
  reload: () => Promise<void>;
}

interface Settled<T> {
  key: string;
  data: T | null;
  error: ApiError | null;
}

/** Load one API resource with loading and error state, plus a manual reload. */
export function useFetch<T>(path: string | null, query?: Record<string, string | number | undefined>): FetchState<T> {
  const { api } = useAuth();
  const [settled, setSettled] = useState<Settled<T> | null>(null);
  const [version, setVersion] = useState(0);
  const queryKey = JSON.stringify(query ?? {});
  const requestKey = `${path}|${queryKey}|${version}`;

  useEffect(() => {
    if (path === null) return;
    let cancelled = false;
    api
      .request<T>(path, { query: JSON.parse(queryKey) as Record<string, string | number> })
      .then((data) => {
        if (!cancelled) setSettled({ key: requestKey, data, error: null });
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const error = e instanceof ApiError ? e : new ApiError(0, "network_error", "Something went wrong.");
        setSettled((prev) => ({ key: requestKey, data: prev?.data ?? null, error }));
      });
    return () => {
      cancelled = true;
    };
  }, [api, path, queryKey, requestKey]);

  const reload = useCallback(async () => setVersion((v) => v + 1), []);
  return {
    data: settled?.data ?? null,
    error: settled?.error ?? null,
    loading: path !== null && settled?.key !== requestKey,
    reload,
  };
}
