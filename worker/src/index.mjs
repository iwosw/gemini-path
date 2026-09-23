// API-key-only Gemini API relay. No Google login, cookies or arbitrary hosts.
const UPSTREAM = "https://generativelanguage.googleapis.com";
const API_PATH = /^\/(?:v1|v1beta|upload\/v1|upload\/v1beta)(?:\/|$)/;
const METHODS = new Set(["GET", "POST", "DELETE"]);

export default {
  async fetch(request, env) {
    const incoming = new URL(request.url);
    if (incoming.pathname === "/health" && request.method === "GET") {
      return new Response("GeminiPath API relay is running", { status: 200 });
    }
    if (!METHODS.has(request.method) || !API_PATH.test(incoming.pathname)) {
      return new Response("Not found", { status: 404 });
    }

    const permitted = env.ALLOWED_API_KEY_SHA256?.trim().toLowerCase();
    if (!permitted || !/^[a-f0-9]{64}$/.test(permitted)) {
      return new Response("Configure ALLOWED_API_KEY_SHA256 first", { status: 503 });
    }
    const key = request.headers.get("x-goog-api-key") || incoming.searchParams.get("key");
    if (!key) return new Response("API key required", { status: 401 });
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(key));
    const hex = Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
    if (hex !== permitted) return new Response("API key not allowed", { status: 403 });

    // Keep the key in the Google API header; never forward browser credentials.
    incoming.searchParams.delete("key");
    const upstream = new URL(incoming.pathname + incoming.search, UPSTREAM);
    const headers = new Headers(request.headers);
    for (const name of ["host", "cookie", "authorization", "cf-connecting-ip",
                        "cf-ipcountry", "x-forwarded-for", "x-real-ip"]) {
      headers.delete(name);
    }
    headers.set("x-goog-api-key", key);

    try {
      const result = await fetch(upstream, {
        method: request.method,
        headers,
        body: request.method === "GET" ? undefined : request.body,
        redirect: "manual",
        duplex: "half",
      });
      // Do not let the client silently follow a redirect outside the relay.
      if (result.status >= 300 && result.status < 400) {
        await result.body?.cancel();
        return new Response("Upstream redirected; refusing direct fallback", { status: 502 });
      }
      const responseHeaders = new Headers(result.headers);
      responseHeaders.delete("set-cookie");
      return new Response(result.body, { status: result.status, headers: responseHeaders });
    } catch {
      return new Response("Google API upstream unavailable", { status: 502 });
    }
  },
};
