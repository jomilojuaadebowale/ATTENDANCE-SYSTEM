import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, createApi } from "@/lib/api";

const BASE = "http://api.test/v1";
afterEach(() => vi.unstubAllGlobals());

function stubFetch(impl: (url: string, init: RequestInit) => Response | Promise<Response>) {
  const fn = vi.fn(async (url: string, init: RequestInit) => impl(url, init));
  vi.stubGlobal("fetch", fn);
  return fn;
}
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

describe("api client", () => {
  it("sends the bearer token and JSON body", async () => {
    const f = stubFetch(() => json({ ok: true }));
    const api = createApi(async () => "tok123", BASE);
    await api.request("/x", { method: "POST", body: { a: 1 } });
    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`${BASE}/x`);
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer tok123");
    expect(init.body).toBe('{"a":1}');
  });

  it("builds query strings and skips empty values", async () => {
    const f = stubFetch(() => json([]));
    await createApi(async () => null, BASE).request("/list", { query: { page: 2, q: "", role: undefined, name: "a b" } });
    expect((f.mock.calls[0] as unknown as [string])[0]).toBe(`${BASE}/list?page=2&name=a+b`);
  });

  it("omits Authorization when signed out", async () => {
    const f = stubFetch(() => json({}));
    await createApi(async () => null, BASE).request("/x");
    expect(((f.mock.calls[0] as [string, RequestInit])[1].headers as Record<string, string>).Authorization).toBeUndefined();
  });

  it("maps the error envelope to ApiError", async () => {
    stubFetch(() => json({ error: { code: "not_enrolled", message: "You are not enrolled", details: [1] } }, 403));
    const err = await createApi(async () => "t", BASE).request("/x").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 403, code: "not_enrolled", message: "You are not enrolled", isNetwork: false });
  });

  it("handles non-JSON error bodies", async () => {
    stubFetch(() => new Response("<html>Bad gateway</html>", { status: 502 }));
    const err = (await createApi(async () => "t", BASE).request("/x").catch((e: unknown) => e)) as ApiError;
    expect(err.status).toBe(502);
    expect(err.code).toBe("http_error");
  });

  it("reports network failures as status 0", async () => {
    stubFetch(() => {
      throw new TypeError("Failed to fetch");
    });
    const err = (await createApi(async () => "t", BASE).request("/x").catch((e: unknown) => e)) as ApiError;
    expect(err.isNetwork).toBe(true);
    expect(err.code).toBe("network_error");
  });

  it("returns undefined for 204 and the filename for downloads", async () => {
    stubFetch((url) => (url.endsWith("/del") ? new Response(null, { status: 204 }) : new Response("a,b", { headers: { "content-disposition": 'attachment; filename="r.csv"' } })));
    const api = createApi(async () => "t", BASE);
    expect(await api.request("/del", { method: "DELETE" })).toBeUndefined();
    const { filename, blob } = await api.download("/report.csv");
    expect(filename).toBe("r.csv");
    expect(await blob.text()).toBe("a,b");
  });
});
