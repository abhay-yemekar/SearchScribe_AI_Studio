# SearchScribe visual system

## Identity

SearchScribe AI: an open-source writing studio. The bracketed S and caret express a thought entering an editorial workspace. See brand.md for concepts and assets.

- Paper #f6f4ed, surface #fffef9, ink #17252b, muted #626b6c, rule #d6d8cf.
- Citron #e0f06b is a small editorial highlight: cursor, selected voice and final action. Do not use it for low-contrast text on paper.
- Dark marketing theme uses ink canvas #17252b, surface #21333a, text #f6f4ed, muted #bac5c1, rule #415259. It is explicitly switchable, not a blanket color inversion. Studio stays light and calm in this release.
- Manrope for navigation/headlines/UI, DM Serif Display italic for human emphasis and article examples, IBM Plex Mono for numbers/labels. next/font self-hosts build-fetched fonts; no runtime Google Fonts request.

## Layout

1440px maximum content width with 48px desktop / 20–24px narrow gutters. Fluid display type, prominent hierarchy, thin rules, numbered sections and generous spacing. Marketing uses asymmetry and illustrative document layers; forms preserve conventional readable controls. No gratuitous card repetition.

## Motion

Single cubic-bezier(.22,1,.36,1) easing. Interactions ~250ms, entry ~700ms. Passive scroll with requestAnimationFrame advances one of six topic→structure→draft→SEO→versions→HTML states; controls also work without scrolling. Sticky scene only on wide viewports, with a stacked explanatory sequence on narrow or reduced-motion settings. Native IntersectionObserver reveals leave content visible without JavaScript. All custom animation/transition stops with prefers-reduced-motion. Editor never gets scroll hijacking, smooth-scroll libraries or hero code.

## Honest product content

Google and password login are deployed; real identity linking still needs production verification. The demo/voice text is prewritten, makes no AI calls, and does not claim research. Research/photos/recovery/quotas/fallback/Markdown remain explicitly in development. No fake testimonials, user totals, quality scores, live metrics or invented citations. MIT license and HTML ownership claims come from the repository.

## Acceptance

Check actual 390px viewport for no horizontal overflow and functional menu. Keyboard: visible focus, Escape closes menu, arrow/Home/End voice tabs, mobile article focus trap. Test Website↔Open workspace session continuity, existing generation/edit/SEO/version/HTML paths and logout protection. Inspect light/dark surfaces plus reduced-motion static flow. Record actual results separately; a Lighthouse90 target is not a claimed measured score.
