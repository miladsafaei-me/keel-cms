# keel-cms design library

Reusable, project-neutral **design references** for composing a host project's
content pages. Unlike the runtime templates in `keel_cms/templates/`, nothing here
is rendered by Django or served at a URL — these files ship with the package purely
as a catalog a developer (or an LLM) reads when designing a project's blog surface.

Change a catalog **here**, bump the keel-cms version, and let projects pull the new
version — never fork it into a project (same editing rule as the rest of keel-cms).

## Catalogs

### `blog_index/` — Blog Index Template

A single standalone HTML catalog of **interchangeable blog-index sections**: 8 blocks,
37 layout variants, one shared design system (vanilla CSS + one small vanilla script).

- **`blog_index_template.html`** — the visual catalog. Open it in a browser (`file://…`)
  to see every variant rendered.
- **`manifest.json`** — the machine-readable index an LLM reads to choose sections.
  Every block lists its variants with `layout`, `bestFor`, and `requiresJs`.

**Blocks:** `hero`, `latest`, `trending`, `category`, `media`, `slider`, `live`, `learn`.

**How the HTML is addressable** (so a picker can locate anything):

| Level | Hook | Example |
| --- | --- | --- |
| Catalog root | `[data-keel-catalog="blog-index"]` | the `<main>` |
| Block group | `[data-keel-block-group="<block>"]`, `id="block-<block>"` | `#block-hero` |
| Variant | `[data-keel-block][data-keel-variant]`, `id="<block>__<slug>"` | `#hero__classic-split` |
| Needs the script | `[data-keel-requires-js="true"]` | all `slider` + `live` variants |

**Shared foundation** every variant reuses (copy it once per project):

- The `:root` design tokens — colors, topic hues, spacing scale, radius, shadow, fonts.
- The component CSS — `.card`, `.media` (strict 16:9), `.chip`, `.badge`, `.meta`,
  `.avatar`, and the `#i-*` inline SVG icon sprite.
- One vanilla `<script>` (no inline handlers) that drives the carousels, rotating
  sliders, auto-updating feeds, the live-blog countdown, ticking counters and the
  curriculum progress bar. It reads `data-*` hooks, pauses on hover, and honors
  `prefers-reduced-motion`; seed content still renders with JS disabled.

**Hard rules the variants preserve** (keep them when you adapt a variant):

- Every image is 16:9 (`aspect-ratio:16/9; object-fit:cover`).
- Never place text over an image — play/live indicators are icon controls; textual
  badges (duration, LIVE, view counts) sit outside the image.
- CSS variables only; semantic tags and named selectors.

## Using it in a project

Pick blocks → pick one variant each → copy their `<article>` subtrees → keep the
shared foundation → reskin the tokens → wire to real data. Concretely, give an LLM
working in the project this instruction:

> Design this project's blog index using the **Keel CMS Blog Index Template** design
> library (installed with keel-cms).
> 1. Read `keel_cms/design_library/blog_index/manifest.json` — 8 blocks
>    (hero, latest, trending, category, media, slider, live, learn), 37 variants,
>    each with `layout`, `bestFor`, `requiresJs`.
> 2. Choose which blocks this project's blog index needs (usually one `hero` + one
>    `latest`, plus any of trending/category/media/slider/live/learn), and exactly
>    **one variant per block** — use each variant's `bestFor`.
> 3. In `blog_index_template.html`, find each chosen variant by its
>    `data-keel-variant` (or `id="<block>__<slug>"`) and copy that `<article>` subtree.
> 4. Copy the shared foundation once: the `:root` tokens, the component CSS
>    (`.card/.media/.chip/.badge/.meta/.avatar`) and the `#i-*` icon sprite. Include
>    the bundled `<script>` **only if** any chosen variant has `requiresJs: true`
>    (all `slider` and `live` variants).
> 5. Swap the `:root` design tokens for this project's brand. Keep 16:9 media and
>    never put text over an image.
> 6. Wire the copied markup to real data (the keel-cms `Post` list / context) in the
>    project's own template — do **not** fork keel-cms.

The template's demo brand ("The Daily Chronicle") and the Unsplash placeholder images
are illustrative — replace them with the project's brand and media.
