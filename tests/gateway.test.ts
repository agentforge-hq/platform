import assert from "node:assert/strict";
import { test, mock } from "node:test";
import { searchGateway } from "../src/lib/gateway";
import { searchRequestSchema } from "../src/lib/contracts";

function request(body: unknown) {
  return new Request("http://localhost/api/v1/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

test("query contract rejects unknown fields, bool limits, and Unicode byte overflow", () => {
  for (const body of [
    { query: "task", transcript: "private" },
    { query: "é".repeat(1025) },
    { query: "task", limit: true },
    { query: "task", harness: "invented" },
  ])
    assert.equal(searchRequestSchema.safeParse(body).success, false);
});
test("public gateway rejects malformed and oversized input before forwarding", async () => {
  assert.equal(
    (await searchGateway(request({ query: "task", transcript: "secret" })))
      .status,
    422,
  );
  assert.equal(
    (
      await searchGateway(
        new Request("http://localhost", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "x".repeat(9000),
        }),
      )
    ).status,
    413,
  );
  assert.equal(
    (
      await searchGateway(
        new Request("http://localhost", { method: "POST", body: "task" }),
      )
    ).status,
    415,
  );
});
test("gateway forwards the same query and server credential without exposing that credential", async () => {
  process.env.PIXELTABLE_SERVICE_URL = "https://backend.example/app";
  process.env.PIXELTABLE_SERVICE_KEY = "server-only-test-key";
  const fetchMock = mock.method(
    globalThis,
    "fetch",
    async (_input: string | URL | Request, init?: RequestInit) => {
      const headers = new Headers(init?.headers);
      assert.equal(headers.get("X-api-key"), "server-only-test-key");
      assert.deepEqual(JSON.parse(String(init?.body)), {
        query: "review permissions",
        harness: "codex",
        limit: 3,
      });
      return Response.json({
        rows: [],
        meta: {
          status: "no_match",
          retrieval_mode: "hybrid",
          catalog_revision: "fixture",
          ranking_version: "hybrid-v1",
          request_id: "test",
        },
      });
    },
  );
  try {
    const response = await searchGateway(
      request({ query: "review permissions", harness: "codex", limit: 3 }),
    );
    assert.equal(response.status, 200);
    const text = await response.text();
    assert.equal(text.includes("server-only-test-key"), false);
    assert.equal(JSON.parse(text).meta.status, "no_match");
  } finally {
    fetchMock.mock.restore();
    delete process.env.PIXELTABLE_SERVICE_URL;
    delete process.env.PIXELTABLE_SERVICE_KEY;
  }
});
test("a missing backend is an error rather than an empty successful catalog", async () => {
  assert.equal(
    (await searchGateway(request({ query: "review permissions" }))).status,
    503,
  );
});
test("gateway does not leak an upstream error body", async () => {
  process.env.PIXELTABLE_SERVICE_URL = "https://backend.example/app";
  process.env.PIXELTABLE_SERVICE_KEY = "test";
  const fetchMock = mock.method(
    globalThis,
    "fetch",
    async () =>
      new Response("private traceback and credentials", { status: 500 }),
  );
  try {
    const response = await searchGateway(
      request({ query: "review permissions" }),
    );
    assert.equal(response.status, 503);
    assert.equal((await response.text()).includes("private traceback"), false);
  } finally {
    fetchMock.mock.restore();
    delete process.env.PIXELTABLE_SERVICE_URL;
    delete process.env.PIXELTABLE_SERVICE_KEY;
  }
});
