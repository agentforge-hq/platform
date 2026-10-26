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
    limit: z.number().int().min(1).max(20).default(5),
  })
  .strict();
export const skillSchema = z.object({
  skill_id: z.string(),
  name: z.string(),
  summary: z.string(),
  category: z.string(),
  capabilities: z.array(z.string()),
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
});
export type Skill = z.infer<typeof skillSchema>;
export type Catalog = z.infer<typeof catalogResponseSchema>;
export type SearchResponse = z.infer<typeof searchResponseSchema>;
export type Harness = z.infer<typeof harnessSchema>;
