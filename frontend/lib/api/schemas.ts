import { z } from "zod";

/** Mirrors backend/app/schemas — single source of truth for API types. */

export const userSchema = z.object({
  id: z.number(),
  email: z.string().email(),
  name: z.string(),
  created_at: z.string(),
});
export type User = z.infer<typeof userSchema>;

export const tokenSchema = z.object({
  access_token: z.string(),
  token_type: z.literal("bearer"),
  expires_in: z.number(),
  user: userSchema,
});
export type TokenPayload = z.infer<typeof tokenSchema>;

export const seoSchema = z.object({
  title: z.string(),
  description: z.string(),
  keywords: z.array(z.string()),
  og_title: z.string().nullable(),
  og_description: z.string().nullable(),
  canonical_url: z.string().nullable(),
  robots: z.string(),
});
export type Seo = z.infer<typeof seoSchema>;

export const articleListItemSchema = z.object({
  id: z.number(),
  title: z.string(),
  query: z.string(),
  status: z.string(),
  current_version: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type ArticleListItem = z.infer<typeof articleListItemSchema>;

export const articleListSchema = z.object({
  items: z.array(articleListItemSchema),
  next_cursor: z.string().nullable(),
});
export type ArticleList = z.infer<typeof articleListSchema>;

export const articleDetailSchema = z.object({
  id: z.number(),
  title: z.string(),
  query: z.string(),
  status: z.string(),
  current_version: z.number(),
  markdown: z.string(),
  html: z.string(),
  seo: seoSchema.nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type ArticleDetail = z.infer<typeof articleDetailSchema>;

export const versionItemSchema = z.object({
  version: z.number(),
  change_type: z.string(),
  word_count: z.number(),
  created_at: z.string(),
});
export type VersionItem = z.infer<typeof versionItemSchema>;

export const versionListSchema = z.object({
  items: z.array(versionItemSchema),
});
export type VersionList = z.infer<typeof versionListSchema>;

export const rewriteStylesSchema = z.object({
  styles: z.array(z.object({ key: z.string(), label: z.string() })),
});
export type RewriteStyles = z.infer<typeof rewriteStylesSchema>;

/** SEO display limits (mirror backend normalize_seo bounds). */
export const SEO_LIMITS = { title: 60, description: 160 } as const;
