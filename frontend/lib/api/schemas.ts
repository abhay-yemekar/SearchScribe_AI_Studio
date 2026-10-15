import { z } from "zod";

/** Mirrors backend/app/schemas — single source of truth for API types. */

export const userSchema = z.object({
  id: z.number(),
  email: z.string().email(),
  name: z.string(),
  email_verified: z.boolean().default(false),
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
  robots: z.enum(["index, follow", "noindex, follow"]),
  review_status: z.enum(["generated", "needs_review", "edited", "unknown"]).optional(),
});
export type Seo = z.infer<typeof seoSchema>;

const photoImageUrl = z
  .string()
  .url()
  .refine((value) => {
    const url = new URL(value);
    return (
      url.protocol === "https:" &&
      ["upload.wikimedia.org", "thumb.wikimedia.org"].includes(url.host) &&
      url.pathname.startsWith("/wikipedia/commons/") &&
      !url.search &&
      !url.hash
    );
  });
export const photoAssetSchema = z.object({
  provider: z.literal("commons"),
  source_id: z.number().int().positive(),
  title: z.string(),
  creator: z.string(),
  source_url: z.string().url(),
  preview_url: photoImageUrl,
  original_url: photoImageUrl,
  license_name: z.string(),
  license_url: z.string().url(),
  width: z.number().positive(),
  height: z.number().positive(),
});
export const articlePhotoSchema = photoAssetSchema.extend({
  id: z.string(),
  alt: z.string(),
  section_id: z.string().nullable(),
});
export const photoSuggestionSchema = photoAssetSchema.extend({
  selection_token: z.string(),
});
export const photoSearchSchema = z.object({
  query: z.string(),
  photos: z.array(photoSuggestionSchema),
});
export type PhotoAsset = z.infer<typeof photoAssetSchema>;
export type ArticlePhoto = z.infer<typeof articlePhotoSchema>;
export type PhotoSuggestion = z.infer<typeof photoSuggestionSchema>;
export type PhotoChoice = {
  id?: string;
  selection_token?: string;
  alt: string;
  section_id: string | null;
};

export const articleSectionSchema = z.object({
  id: z.string().min(8),
  heading: z.string(),
  paragraphs: z.array(z.string()),
  bullets: z.array(z.string()),
});
export const articleContentSchema = z.object({
  title: z.string(),
  introduction: z.string(),
  sections: z.array(articleSectionSchema),
  conclusion: z.string(),
  photos: z.array(articlePhotoSchema).optional(),
  research: z
    .object({
      status: z.enum(["unresearched", "sources_retrieved"]),
      retrieved_at: z.string().nullable(),
      sources: z.array(
        z.object({
          id: z.string(),
          title: z.string(),
          url: z.string().url(),
          published_at: z.string().nullable().optional(),
        }),
      ),
    })
    .optional(),
});
export type ArticleContent = z.infer<typeof articleContentSchema>;

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
  content: articleContentSchema,
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
  complete_snapshot: z.boolean(),
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
