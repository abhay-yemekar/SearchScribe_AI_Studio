# SearchScribe redesign audit — 8 October 2026

The shipped product has public home/process/features/example/privacy routes, login, protected dashboard and account. FastAPI contracts remain unchanged. Tracked Next.js 16.3.3 documentation was read before fonts/metadata changes.

## Findings

- The feather mark and teal/serif styling lacked a recognizable input-to-writing identity.
- Marketing used a repeated card grid with little product demonstration or visual hierarchy.
- Dashboard and Account had no direct public-website path; the public header was not session aware.
- Google was deployed in PR10, but homepage/features/docs still described it as unavailable.
- The empty workspace had a large blank panel without guidance. Motion lacked a consistent reduced-motion treatment.
- Existing unit and Playwright tests cover editing/version/export/mobile navigation; real Google consent/linking remains a separate production verification gate.

## Independent visual research

Inspected actual rendered pages and scroll states of Odyssée Clinic, TWKS and Riotters Aevion. Also inspected iA Writer and Readwise Reader. Borrow layout/motion principles, never assets or compositions: confident typography, deliberate spacing, visible product surfaces, editorial control and portability.

## Implemented direction

Original paper/ink/citron identity; custom bracket-and-caret mark; self-hosted Manrope, DM Serif Display and IBM Plex Mono via next/font. The home page demonstrates one coherent article workflow with explicit sample labels. Native scroll/sticky choreography, keyboard-operable rewrite examples, transparent roadmap, open-source ownership, FAQ and session-preserving navigation replace generic decoration. No video, WebGL, animation dependency or unrelated stock imagery. SVG graphics remain sharp on 4K displays; large raster downloads are unnecessary here.

## Setup distinction

Vercel BACKEND_URL and Render production DATABASE_URL/SECRET_KEY/GEMINI_API_KEY/CORS_ORIGINS/GOOGLE_CLIENT_ID were configured and deployed in the preceding release. Google client production+localhost3100 origins and home/privacy branding are saved. No Google client secret or NEXT_PUBLIC_GOOGLE_CLIENT_ID is needed.

Real Google login/session/linking/public availability checks remain unconfirmed. Brevo sender/API key/delivery and reset/email-verification implementation remain pending. Planned email variables are not read by the application yet. Research/photos/fallback/quotas/Markdown and restore/rollback rehearsals remain release gates, not missing credentials for shipped features.
