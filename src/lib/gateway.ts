import { createHash, randomUUID } from "node:crypto";
import { z } from "zod";
import {
  catalogQuerySchema,
  catalogResponseSchema,
  searchRequestSchema,
  searchResponseSchema,
} from "./contracts";

const callers = new Map<string, { count: number; reset: number }>();
const MAX_BODY = 8192;

export function apiError(
  status: number,
  code: string,
  message: string,
  requestId = randomUUID(),
): Response {
  return Response.json(
    { error: { code, message }, request_id: requestId },
    {
      status,
      headers: { "Cache-Control": "no-store", "X-Request-ID": requestId },
    },
  );
}

export async function readBody(
  request: Pick<Request, "body">,
  byteLimit = MAX_BODY,
): Promise<string | null> {
  if (!request.body) return "";
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  while (true) {
    const chunk = await reader.read();
    if (chunk.done) break;
    length += chunk.value.byteLength;
    if (length > byteLimit) {
      await reader.cancel();
      return null;
    }
    chunks.push(chunk.value);
  }
  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
}

function withinLimit(request: Request): boolean {
  const now = Date.now();
  if (callers.size > 5000)
    for (const [key, value] of callers)
      if (value.reset <= now) callers.delete(key);
  const address =
    request.headers.get("x-vercel-forwarded-for") ??
    request.headers.get("x-forwarded-for") ??
    "local";
  const key = createHash("sha256").update(address).digest("hex");
  const previous = callers.get(key);
  const state =
    previous && previous.reset > now
      ? previous
      : { count: 0, reset: now + 60_000 };
  state.count += 1;
  callers.set(key, state);
  return state.count <= 20;
}

async function forward<T>(
  path: "/v1/search" | "/v1/catalog",
  schema: z.ZodType<T>,
  body?: unknown,
  query?: URLSearchParams,
): Promise<Response> {
  const base = process.env.PIXELTABLE_SERVICE_URL;
  const key = process.env.PIXELTABLE_SERVICE_KEY;
  if (!base || !key)
    return apiError(
      503,
      "catalog_unavailable",
      "The catalog is not connected yet. Please try again shortly.",
    );
  try {
    const response = await fetch(
      `${base.replace(/\/$/, "")}${path}${query ? `?${query}` : ""}`,
      {
        method: body === undefined ? "GET" : "POST",
        headers: {
          "X-api-key": key,
          ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: AbortSignal.timeout(7_500),
        cache: "no-store",
        redirect: "error",
      },
    );
    if (!response.ok)
      return apiError(
        response.status === 429 ? 429 : 503,
        "catalog_unavailable",
        "The catalog is temporarily unavailable. Please try again.",
      );
    const raw = await readBody(response, 4_194_304);
    if (raw === null)
      return apiError(
        502,
        "invalid_response",
        "The search service returned an invalid response.",
      );
    const parsed = schema.safeParse(JSON.parse(raw));
    if (!parsed.success)
      return apiError(
        502,
        "invalid_response",
        "The search service returned an invalid response.",
      );
    return Response.json(parsed.data, {
      headers: {
        "Cache-Control":
          path === "/v1/catalog"
            ? "public, s-maxage=60, stale-while-revalidate=120"
            : "no-store",
      },
    });
  } catch (error: unknown) {
    const timeout =
      error instanceof Error &&
      (error.name === "TimeoutError" || error.name === "AbortError");
    return apiError(
      timeout ? 504 : 503,
      timeout ? "search_timeout" : "catalog_unavailable",
      timeout
        ? "Search took too long. Please try again."
        : "The catalog is temporarily unavailable. Please try again.",
    );
  }
}

export async function searchGateway(request: Request): Promise<Response> {
  if (
    request.headers.get("content-type")?.split(";")[0].trim() !==
    "application/json"
  )
    return apiError(415, "content_type", "Send application/json.");
  let input: unknown;
  try {
    const raw = await readBody(request);
    if (raw === null)
      return apiError(413, "body_limit", "Keep the request under 8 KiB.");
    input = JSON.parse(raw);
  } catch {
    return apiError(
      422,
      "invalid_request",
      "Send a valid JSON search request.",
    );
  }
  const parsed = searchRequestSchema.safeParse(input);
  if (!parsed.success)
    return apiError(
      422,
      "invalid_request",
      parsed.error.issues[0]?.message ??
        "Describe a task using the supported search fields.",
    );
  if (!withinLimit(request)) {
    const response = apiError(
      429,
      "rate_limit",
      "You have made several searches. Please wait a minute and try again.",
    );
    response.headers.set("Retry-After", "60");
    return response;
  }
  return forward("/v1/search", searchResponseSchema, parsed.data);
}
export async function catalogGateway(request?: Request): Promise<Response> {
  const parameters = new URL(request?.url ?? "http://localhost/api/v1/catalog")
    .searchParams;
  if ([...parameters.keys()].some((key) => parameters.getAll(key).length > 1))
    return apiError(422, "invalid_request", "Use each catalog filter once.");
  const parsed = catalogQuerySchema.safeParse(Object.fromEntries(parameters));
  if (!parsed.success)
    return apiError(
      422,
      "invalid_request",
      "Use supported catalog filters and page bounds.",
    );
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(parsed.data))
    query.set(key, String(value));
  return forward("/v1/catalog", catalogResponseSchema, undefined, query);
}
