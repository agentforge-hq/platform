import { z } from "zod";

export const harnessSchema = z.enum([
  "codex",
  "claude-code",
  "cursor",
  "gemini",
  "opencode",
  "devin",
  "portable",
]);
export const searchConstraintsSchema = z
  .object({
    available_tools: z
      .array(z.string().regex(/^[A-Za-z0-9][A-Za-z0-9._+\-]{0,63}$/))
      .max(32)
      .nullable()
      .optional(),
    allow_setup: z.boolean().default(true),
    allow_credentials: z.boolean().default(true),
  })
  .strict();
export const catalogQuerySchema = z
  .object({
    offset: z.coerce.number().int().min(0).max(100000).default(0),
    limit: z.coerce.number().int().min(1).max(50).default(50),
    category: z
      .enum([
        "Design",
        "Engineering",
        "Writing",
        "Research",
        "Operations",
        "General",
      ])
      .optional(),
    harness: harnessSchema.optional(),
  })
  .strict();
export const evidenceSchema = z.object({
  field: z.string(),
  quote: z.string(),
  location: z.string(),
  source_url: z.url(),
  status: z.enum(["declared", "inferred"]),
});
export const capabilityProfileSchema = z.object({
  extractor_version: z.string(),
  source_revision: z.string(),
  outputs: z.array(z.string()),
  use_when: z.array(z.string()),
  avoid_when: z.array(z.string()),
  tools: z.array(z.string()),
  credentials: z.array(z.string()),
  evidence: z.array(evidenceSchema),
});
export const searchRequestSchema = z
  .object({
    query: z
      .string()
      .trim()
      .min(1, "Describe what you want to do.")
      .max(2048)
      .refine(
        (q) => new TextEncoder().encode(q).length <= 2048,
        "Keep your request under 2,048 bytes.",
      ),
    harness: harnessSchema.nullable().optional(),
    constraints: searchConstraintsSchema.nullable().optional(),
    limit: z.number().int().min(1).max(20).default(5),
  })
  .strict();
export const skillSchema = z.object({
  skill_id: z.string(),
  name: z.string(),
  summary: z.string(),
  category: z.string(),
  capabilities: z.array(z.string()),
  profile: capabilityProfileSchema.optional(),
  harness_support: z
    .array(
      z.object({
        harness: harnessSchema,
        status: z.enum([
          "declared",
          "inferred",
          "tested",
          "incompatible",
          "unknown",
        ]),
        detail: z.string(),
        evidence_url: z.url(),
        checked_at: z.string().nullable(),
        harness_version: z.string().nullable(),
      }),
    )
    .optional(),
  fit: z
    .object({
      reason: z.string(),
      evidence: z.array(evidenceSchema),
      missing_tools: z.array(z.string()),
      notes: z.array(z.string()),
    })
    .nullable()
    .optional(),
  author_metadata: z.record(z.string(), z.json()).optional(),
  example_prompts: z.array(z.string()),
  requirements: z.array(z.string()),
  exclusions: z.array(z.string()),
  compatibility: z.object({ harness: z.string(), status: z.string() }),
  license: z.object({ identifier: z.string().nullable(), status: z.string() }),
  source: z.object({
    url: z.url(),
    repository: z.string(),
    revision: z.string(),
    skill_path: z.string(),
    manifest_sha256: z.string(),
    checked_at: z.string(),
    files: z
      .array(z.object({ path: z.string(), git_blob_sha1: z.string() }))
      .optional(),
    discovered_via: z.array(z.string()).optional(),
  }),
  adoption_status: z.enum(["review_required", "metadata_only", "unavailable"]),
});
export const searchResponseSchema = z.object({
  rows: z.array(skillSchema),
  meta: z.object({
    status: z.enum(["matches", "no_match"]),
    retrieval_mode: z.enum(["hybrid", "lexical_only"]),
    catalog_revision: z.string(),
    ranking_version: z.string(),
    request_id: z.string(),
  }),
});
export const catalogResponseSchema = z.object({
  rows: z.array(skillSchema),
  skill_count: z.number().int(),
  source_count: z.number().int(),
  categories: z.array(z.string()),
  updated_at: z.string().nullable(),
  filtered_count: z.number().int().nullable().optional(),
  offset: z.number().int().default(0),
  limit: z.number().int().default(50),
  next_offset: z.number().int().nullable().default(null),
});
export type Skill = z.infer<typeof skillSchema>;
export type Catalog = z.infer<typeof catalogResponseSchema>;
export type SearchResponse = z.infer<typeof searchResponseSchema>;
export type Harness = z.infer<typeof harnessSchema>;
