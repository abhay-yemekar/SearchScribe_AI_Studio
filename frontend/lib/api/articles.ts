"use client";

import { apiFetch } from "./client";
import {
  articleDetailSchema,
  articleListSchema,
  rewriteStylesSchema,
  versionListSchema,
  type ArticleDetail,
  type ArticleList,
  type RewriteStyles,
  type VersionList,
} from "./schemas";

export async function generateArticle(query: string): Promise<ArticleDetail> {
  const payload = await apiFetch<unknown>("/api/v1/articles", {
    method: "POST",
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

export async function deleteArticle(id: number): Promise<void> {
  await apiFetch<void>(`/api/v1/articles/${id}`, { method: "DELETE" });
}

export async function duplicateArticle(id: number): Promise<ArticleDetail> {
  const payload = await apiFetch<unknown>(`/api/v1/articles/${id}/duplicate`, {
    method: "POST",
  });
  return articleDetailSchema.parse(payload);
}

export async function rewriteArticle(id: number, style: string): Promise<ArticleDetail> {
  const payload = await apiFetch<unknown>(`/api/v1/articles/${id}/rewrite`, {
    method: "POST",
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
