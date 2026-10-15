"use client";

import { apiFetch } from "./client";
import {
  articleDetailSchema,
  articleListSchema,
  rewriteStylesSchema,
  versionListSchema,
  type ArticleDetail,
  type ArticleContent,
  type ArticleList,
  type RewriteStyles,
  type VersionList,
  type Seo,
  photoSearchSchema,
  type PhotoChoice,
} from "./schemas";

export async function generateArticle(
  query: string,
  requestKey: string = crypto.randomUUID(),
): Promise<ArticleDetail> {
  const payload = await apiFetch<unknown>("/api/v1/articles", {
    method: "POST",
    headers: { "Idempotency-Key": requestKey },
    body: JSON.stringify({ query }),
  });
  return articleDetailSchema.parse(payload);
}

export async function listArticles(
  limit: number,
  cursor?: string | null,
): Promise<ArticleList> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor) params.set("cursor", cursor);
  const payload = await apiFetch<unknown>(`/api/v1/articles?${params}`);
  return articleListSchema.parse(payload);
}

export async function getArticle(id: number): Promise<ArticleDetail> {
  const payload = await apiFetch<unknown>(`/api/v1/articles/${id}`);
  return articleDetailSchema.parse(payload);
}

export async function renameArticle(id: number, title: string): Promise<ArticleDetail> {
  const payload = await apiFetch<unknown>(`/api/v1/articles/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
  return articleDetailSchema.parse(payload);
}

export async function saveArticle(
  id: number,
  baseVersion: number,
  content: ArticleContent,
  seo: Seo,
): Promise<ArticleDetail> {
  const payload = await apiFetch<unknown>(`/api/v1/articles/${id}/content`, {
    method: "PUT",
    body: JSON.stringify({ base_version: baseVersion, content, seo }),
  });
  return articleDetailSchema.parse(payload);
}

export async function deleteArticle(id: number): Promise<void> {
  await apiFetch<void>(`/api/v1/articles/${id}`, { method: "DELETE" });
}

export async function duplicateArticle(id: number): Promise<ArticleDetail> {
  const payload = await apiFetch<unknown>(`/api/v1/articles/${id}/duplicate`, {
    method: "POST",
  });
  return articleDetailSchema.parse(payload);
}

export async function rewriteArticle(
  id: number,
  style: string,
  requestKey: string = crypto.randomUUID(),
): Promise<ArticleDetail> {
  const payload = await apiFetch<unknown>(`/api/v1/articles/${id}/rewrite`, {
    method: "POST",
    headers: { "Idempotency-Key": requestKey },
    body: JSON.stringify({ style }),
  });
  return articleDetailSchema.parse(payload);
}

export async function listVersions(id: number): Promise<VersionList> {
  const payload = await apiFetch<unknown>(`/api/v1/articles/${id}/versions`);
  return versionListSchema.parse(payload);
}

export async function restoreVersion(
  id: number,
  version: number,
): Promise<ArticleDetail> {
  const payload = await apiFetch<unknown>(
    `/api/v1/articles/${id}/versions/${version}/restore`,
    { method: "POST" },
  );
  return articleDetailSchema.parse(payload);
}

export async function fetchRewriteStyles(): Promise<RewriteStyles> {
  const payload = await apiFetch<unknown>("/api/v1/articles/rewrite-styles");
  return rewriteStylesSchema.parse(payload);
}

export async function searchArticlePhotos(id: number, query: string) {
  const params = new URLSearchParams({ query });
  return photoSearchSchema.parse(
    await apiFetch<unknown>(`/api/v1/articles/${id}/photos?${params}`),
  );
}

export async function saveArticlePhotos(
  id: number,
  baseVersion: number,
  photos: PhotoChoice[],
) {
  return articleDetailSchema.parse(
    await apiFetch<unknown>(`/api/v1/articles/${id}/photos`, {
      method: "PUT",
      body: JSON.stringify({ base_version: baseVersion, photos }),
    }),
  );
}
