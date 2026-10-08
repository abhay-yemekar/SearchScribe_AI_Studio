# GitHub presentation

Use **SearchScribe AI** as the displayed product name. Keep the existing repository
name `SearchScribe_AI_Studio` for now: its URLs already appear in documentation,
deployment integrations, and contributor history. A repository rename should be
a separate reviewed change with integration checks, not a side effect of a visual
redesign.

## Suggested About settings

Description, website, and the following 12 topics were applied and verified on
GitHub using the personal `abhay-yemekar` account on 8 October 2026. Social preview
is prepared below; its GitHub upload is a separate step.

- **Description:** Open-source AI writing studio: generate structured drafts, edit
  SEO, rewrite in six styles, restore versions, and export HTML. Built with Next.js
  and FastAPI.
- **Website:** `https://searchscribe-ai.vercel.app/`
- **Topics:** `ai-writing`, `open-source`, `nextjs`, `react`, `typescript`, `fastapi`,
  `python`, `gemini`, `seo`, `content-editor`, `postgresql`, `self-hosted`
- **Social preview:** `frontend/public/brand/open-graph.png` (1200 × 630).

The README starts with the real brand image, the live website, the contribution
path, an MIT link, and the actual main-branch CI badge. It describes the working
article workflow and separates remaining beta work from shipped features. Avoid
usage counts, testimonials, quality scores, and release badges that have not been
established.

## Captured product media

The following local-app captures exist and are linked in the README:

- `screenshots/redesign-home-hero.png`: the implemented homepage at 3840 × 2160.
  The scene uses labeled illustrative article copy.
- `screenshots/redesign-workspace.png`: the populated editor at 2880 × 2000,
  using a synthetic **Demo Writer** account and the deterministic mock provider.
  No private account or live-generation claim appears in its caption.
- `screenshots/writing-journey.gif`: six real captures of the homepage's prewritten
  walkthrough, 727 × 546, approximately 80 KB and nine seconds. It demonstrates
  the explanatory scene, not AI generation speed. Both static screenshots are
  linked as alternatives to the animation.

The static images were visually reviewed. These are local implementation captures,
not evidence that the redesign is already deployed. Old dark-dashboard images
remain historical assets and are not used to illustrate the redesigned product.

Future media should identify the provider and data source, omit emails and private
articles, and avoid fabricated completions. Replace local captures with deployed
ones only after verifying the production release.

## Release accuracy

- Google sign-in is deployed; real identity login and password-authenticated
  linking acceptance remain pending until explicitly verified.
- Password recovery, email verification, research citations, photo selection,
  Markdown download, daily quotas, and provider fallback remain unfinished.
- The live frontend/API/database foundation does not prove backup restore or
  rollback. Keep those as separate release gates.
- Self-hosting is MIT-licensed code plus the operator's own infrastructure and API
  accounts. Hosted providers' free allowances are not bundled with the license.
- Publish a beta tag and GitHub Release only after the documented release gates
  pass. Repository About settings and a polished README do not establish release
  readiness.
