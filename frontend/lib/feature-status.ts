/**
 * The one list the public pages use to say what is shipped and what is next.
 * Update it in the same PR that ships or plans a feature, so the website never
 * describes a shipped feature as "in development" (or the reverse).
 */
export type FeatureNote = { name: string; detail: string };

export const AVAILABLE: FeatureNote[] = [
  {
    name: "Article generation",
    detail: "Create a sectioned draft from a topic, then review it before publication.",
  },
  {
    name: "Web research",
    detail:
      "Search for relevant source excerpts with visible links and dates. Current-topic drafts require usable evidence, and a draft without sources is marked Unresearched. Review claims before publishing.",
  },
  {
    name: "Structured editing",
    detail:
      "Edit article content and SEO fields, with visible unsaved changes and keep/discard protection.",
  },
  {
    name: "Rewrites and history",
    detail: "Apply a rewrite style, save versions, and restore an earlier draft.",
  },
  {
    name: "Credited photos",
    detail:
      "Search Wikimedia Commons for a cover and section photos. Each keeps the creator's credit, licence and source link, with alt text you can edit.",
  },
  {
    name: "HTML and Markdown export",
    detail:
      "Download the saved article with its research status, source links and photo credits.",
  },
  {
    name: "Password and Google sign-in",
    detail:
      "Enter your workspace using a password or Google. Existing password accounts link Google explicitly from Account.",
  },
  {
    name: "Account security",
    detail:
      "Verify your email, reset a forgotten password by email, or add and change a password from Account.",
  },
  {
    name: "Daily limits and safe retries",
    detail:
      "Each account has a daily generation allowance. If a request is interrupted, you can check and recover it instead of spending another draft.",
  },
];

export const NEXT: FeatureNote[] = [
  {
    name: "Progress while it drafts",
    detail:
      "Generation will run in the background and show each stage, so a slow draft is never a blank wait.",
  },
  {
    name: "Account export and deletion",
    detail: "Download everything you have written, and delete your account yourself.",
  },
  {
    name: "Check a sentence against its source",
    detail:
      "Select a sentence to see the passage that supports it, with unsupported claims flagged.",
  },
];
