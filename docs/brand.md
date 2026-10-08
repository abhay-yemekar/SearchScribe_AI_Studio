# SearchScribe AI identity

The product name is **SearchScribe AI**. `searchscribe-ai` is the URL/repository slug,
not the displayed wordmark. The identity describes a writing tool with editorial
control: it should look useful, precise, and recognizable without a technology mascot.

## Symbol explorations

The three original options live in `frontend/public/brand/options/`:

1. **Editorial bracket**: a geometric S enclosed by two brackets, with a separate
   writing caret. It joins the input field with the resulting structured draft.
2. **Draft fold**: an S on a folded page. Clear at large sizes, but less distinctive
   and less legible at favicon scale.
3. **Query cursor**: an input chevron, S, and baseline. More terminal-like than the
   intended writing studio.

**Option 01 is the final.** The brackets create a recognizable silhouette at small
sizes; the S retains the name's initial; the caret suggests work in progress. No
feather, generic search lens, copied reference-site asset, or external image is used.

## Color and lettering

- Ink `#17252b` is the primary mark and type color.
- Paper `#f6f4ed` is the warm ground.
- Acid `#e0f06b` is a precise accent for a caret, label, or app icon. It is not a
  background for low-contrast white text.
- The wordmark is bold, tightly spaced sans lettering; `AI` is a subordinate label.
  SVG wordmark assets contain outlines so they need no installed font at runtime.

Use the ink mark on light surfaces and the paper mark with an acid caret on dark
surfaces. Keep at least one S stroke of clear space around the mark. The browser
icon has a fixed acid backing to remain identifiable on both light and dark tabs.

## Integration

`frontend/components/brand/BrandLogo.tsx` exports a server-compatible component with
`compact?: boolean` and `className?: string`. Place it inside a home link. Its SVG
is decorative; the visible wordmark or compact screen-reader text supplies the
accessible product name. Add “home” to the surrounding link if helpful.

The classes `brand-logo`, `brand-symbol`, `brand-wordmark`, `brand-ai`, and
`brand-caret` are the styling hooks. Any first-load caret reveal must be finite,
avoid layout shifts, and stop under `prefers-reduced-motion: reduce`. The caret is
visible in the static SVG exports and never essential to reading the product name.

## Delivered assets

- Transparent mark and outlined wordmark SVGs, with light/dark variants.
- Acid-backed app icon SVG, 16/32 px favicon PNGs, and a 180 px touch icon PNG.
- `frontend/app/icon.svg` for automatic Next.js favicon metadata.
- `frontend/app/opengraph-image.tsx`, a self-contained 1200 × 630 social image using
  Next.js `ImageResponse`. It has no font/image fetch, fabricated metrics, or API
  dependency.

Source geometry is intentionally simple. Use the SVG assets for publication;
do not upscale a small favicon to create a wordmark.
