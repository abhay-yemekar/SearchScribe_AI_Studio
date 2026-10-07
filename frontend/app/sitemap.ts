import type { MetadataRoute } from "next";

const site = "https://searchscribe-ai.vercel.app";

export default function sitemap(): MetadataRoute.Sitemap {
  return ["", "/how-it-works", "/features", "/example", "/privacy"].map((path) => ({
    url: `${site}${path}`,
    lastModified: new Date(),
    changeFrequency: "monthly",
    priority: path === "" ? 1 : 0.6,
  }));
}
