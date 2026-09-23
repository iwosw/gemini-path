import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";
import worker from "./src/index.mjs";

const key = "test-key-only";
const env = { ALLOWED_API_KEY_SHA256: createHash("sha256").update(key).digest("hex") };
const endpoint = "https://relay.example.workers.dev/v1beta/models/gemini-2.5-flash:generateContent";

test("accepts one API key and forwards only a pinned Google API endpoint", async (t) => {
  let called = 0;
  t.mock.method(globalThis, "fetch", async (url, options) => {
    called++;
    assert.equal(url.hostname, "generativelanguage.googleapis.com");
    assert.equal(url.pathname, "/v1beta/models/gemini-2.5-flash:generateContent");
    assert.equal(url.searchParams.has("key"), false);
    assert.equal(options.headers.get("x-goog-api-key"), key);
    assert.equal(options.headers.has("cookie"), false);
    assert.equal(options.headers.has("authorization"), false);
    return new Response('{"ok":true}', { status: 200, headers: { "content-type": "application/json" } });
  });
  const response = await worker.fetch(new Request(endpoint, {
    method: "POST", headers: { "x-goog-api-key": key, cookie: "no", authorization: "Bearer no" },
    body: '{"contents":[]}',
  }), env);
  assert.equal(response.status, 200);
  assert.equal(await response.text(), '{"ok":true}');
  assert.equal(called, 1);
});

test("rejects unknown key and arbitrary paths without calling upstream", async (t) => {
  const upstream = t.mock.method(globalThis, "fetch", async () => { throw Error("must not forward"); });
  const denied = await worker.fetch(new Request(endpoint, { headers: { "x-goog-api-key": "wrong" } }), env);
  assert.equal(denied.status, 403);
  const badPath = await worker.fetch(new Request("https://relay.example.workers.dev/https://other.example/", {
    headers: { "x-goog-api-key": key },
  }), env);
  assert.equal(badPath.status, 404);
  assert.equal(upstream.mock.callCount(), 0);
});

test("does not follow Google redirects outside the relay", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response(null, {
    status: 302, headers: { location: "https://another.example/" },
  }));
  const result = await worker.fetch(new Request(endpoint, { headers: { "x-goog-api-key": key } }), env);
  assert.equal(result.status, 502);
  assert.equal(result.headers.has("location"), false);
});
