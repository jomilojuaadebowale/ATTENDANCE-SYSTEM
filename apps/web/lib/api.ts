import { config } from "@/lib/config";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** True when the request never reached the server (offline, DNS, CORS...). */
  get isNetwork(): boolean {
    return this.status === 0;
  }
}

export type TokenGetter = () => Promise<string | null>;

type Query = Record<string, string | number | boolean | null | undefined>;

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  form?: FormData;
  query?: Query;
}

function withQuery(path: string, query?: Query): string {
  if (!query) return path;
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `${path}?${s}` : path;
}

export function createApi(getToken: TokenGetter, baseUrl: string = config.apiUrl) {
  async function raw(path: string, opts: RequestOptions = {}): Promise<Response> {
    const headers: Record<string, string> = {};
    const token = await getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    let body: BodyInit | undefined;
    if (opts.form) body = opts.form;
    else if (opts.body !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(opts.body);
    }
    let res: Response;
    try {
      res = await fetch(baseUrl + withQuery(path, opts.query), { method: opts.method ?? "GET", headers, body });
    } catch {
      throw new ApiError(0, "network_error", "Cannot reach the server. Check your connection.");
    }
    if (!res.ok) {
      let code = "http_error";
      let message = `Request failed (${res.status})`;
      let details: unknown;
      try {
        const data = (await res.json()) as { error?: { code?: string; message?: string; details?: unknown } };
        if (data.error) {
          code = data.error.code ?? code;
          message = data.error.message ?? message;
          details = data.error.details;
        }
      } catch {
        /* non-JSON error body */
      }
      throw new ApiError(res.status, code, message, details);
    }
    return res;
  }

  async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
    const res = await raw(path, opts);
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  }

  async function download(path: string, query?: Query): Promise<{ blob: Blob; filename: string }> {
    const res = await raw(path, { query });
    const disposition = res.headers.get("content-disposition") ?? "";
    const match = /filename="([^"]+)"/.exec(disposition);
    return { blob: await res.blob(), filename: match?.[1] ?? "export.csv" };
  }

  return { request, download };
}

export type Api = ReturnType<typeof createApi>;
