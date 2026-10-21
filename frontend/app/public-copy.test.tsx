import { renderToString } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HomePage from "./page";
import ExamplePage from "./example/page";
import FeaturesPage from "./features/page";
import HowItWorksPage from "./how-it-works/page";
import PrivacyPage from "./privacy/page";
import { AVAILABLE, NEXT } from "@/lib/feature-status";

vi.mock("@/features/auth/useSession", () => ({ useSession: () => ({ user: null }) }));

function text(page: () => React.ReactNode): string {
  return renderToString(page())
    .replace(/<[^>]+>/g, " ")
    .replace(/&#x27;|&#39;/g, "'")
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ");
}

const pages = {
  home: HomePage,
  features: FeaturesPage,
  "how-it-works": HowItWorksPage,
  example: ExamplePage,
  privacy: PrivacyPage,
};

describe("public pages describe what is shipped", () => {
  beforeEach(() => {
    vi.stubGlobal("matchMedia", () => ({ matches: false }));
  });

  it.each(Object.entries(pages))("%s has no stale shipped-status claims", (_, page) => {
    const copy = text(page);
    for (const stale of [
      /photo suggestions are (still )?in development/i,
      /password-reset emails are still in development/i,
      /neither step is shipped/i,
      /traceable research and credited photo selection are in development/i,
      /research citations and photo suggestions are still in development/i,
      /brevo/i,
    ]) {
      expect(copy).not.toMatch(stale);
    }
  });

  it("lists photos, research and safe retries as available, from one source", () => {
    const names = AVAILABLE.map((feature) => feature.name);
    expect(names).toEqual(
      expect.arrayContaining([
        "Web research",
        "Credited photos",
        "Daily limits and safe retries",
      ]),
    );
    const features = text(FeaturesPage);
    for (const feature of [...AVAILABLE, ...NEXT])
      expect(features).toContain(feature.name);
    const home = text(HomePage);
    expect(home).toMatch(/Photos you can credit.*Available/);
    for (const feature of NEXT) expect(home).toContain(feature.name);
  });

  it("names the services that actually handle email and photos", () => {
    const privacy = text(PrivacyPage);
    expect(privacy).toContain("Resend sends verification");
    expect(privacy).toContain("Wikimedia Commons");
  });
});
