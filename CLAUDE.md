# keel-cms — package guide

Part of the **Keel** platform (see keel-kit `PLATFORM.md`). This is a Bucket-2
reusable Django app: the blog / news / glossary content engine. English only; no
banner comments; CSS variables only in any styling; multi-line comments use
block-delimited syntax.

## Boundaries — what is here vs what stays in the host

- **Here (the engine, Bucket 2):** the shared content models (with literal
  `blog_*` / `news_*` `db_table` names), the Markdown/HTML render pipeline
  (`markdown_convert`, `html_sanitize`, `article_toc`), the schema.org builders
  (`blog_schema`, `news_schema`), RSS `feeds`, the sidebar helpers + cache +
  invalidation `signals`, the editorial-desks **framework** (resolution + schema
  rendering), the body auto-linker / product-showcase / aside **mechanisms**, the
  glossary render service, the `glossary_visuals` templatetag (keel-ui), the
  3-tab body editor (partial + JS + CSS + `content_convert` view), and the
  **content sitemaps** (`sitemaps.py`: blog-post / news / desk / topic / tag
  buckets, composed by the host with keel-seo's `LandingSitemap`).
- **Stays in the host (Bucket 0 / content):** the actual glossary term corpus
  (`trading_glossary.json`), the glossary category rows, the `DESKS` / `BOARD`
  copy, the entity/affiliate registry (broker/exchange links), the funnel-surface
  map and showcase card copy, the aside broker/exchange/VIP data, and the market
  vocabulary rows. Also **not** here: the glossary *authoring* management commands
  (`author_glossary_terms`, `persist_glossary_terms`, `judge_glossary_viz`) — those
  belong to the sibling package **keel-content**, together with the component
  library that `keel_ui` fronts.

## Editing rule (drift prevention)

When a consuming project has this installed, its copy of these files is **not**
editable in that project — change them **here**, bump the version, and let the
project pull the new version. Project-specific behavior belongs in `KEEL_CMS`
config hooks, never in a fork of this code.

## Design library + the shipped Blog Index foundation

`keel_cms/design_library/blog_index/` is the **Blog Index Template**: a standalone
HTML catalog of 37 interchangeable section variants (8 blocks) plus a `manifest.json`
an LLM reads to compose a host's blog index. It is a **reference** — not a Django
template, not served — and a host copies *only the per-variant markup* out of it.

The **styling/behavior is not copied** — it is shipped as a linked foundation, so a
host fixes theming/RTL/motion/a11y bugs simply by **pinning a newer keel-cms
version** (they never fork the CSS):

- `static/keel_cms/css/blog-index.css` — tokens + every component/block layout,
  **scoped under `[data-keel-catalog="blog-index"]`** so it never collides with a
  host's own `.card`/`.title`/`.meta`. Light + dark (auto via `prefers-color-scheme`,
  forceable with `data-theme`), RTL-ready (logical properties only), one
  `prefers-reduced-motion` blanket.
- `static/keel_cms/js/blog-index.js` — the slider/live behavior (load only for
  `data-keel-requires-js` variants).
- `templates/keel_cms/blog_index/_icons.html` — the `#i-*` SVG sprite, `{% include %}`
  once. **Source of truth**; the catalog inlines an identical copy for reference.

A host wires it: link the CSS, put `data-keel-catalog="blog-index"` on the blog-index
root, include the icons partial, then copy variant markup. **Category colour is
token-driven** — one `.chip` rule + `.accent-1..8` helpers set `--cat` (an 8-slot
neutral palette, remapped per project); no topic names live in the CSS. Theme by
overriding tokens on the root (or set `--brand` once — `--accent` inherits it).

Drift rule (unchanged): edit the catalog HTML **here** and bump the version; keep the
HTML + `manifest.json` in sync with `scripts/build_blog_index_manifest.py` (repo-only,
not shipped) — hand-edit the HTML (`data-keel-*` hooks) and the script's editorial
table, then rerun it; it rebuilds `manifest.json` and fails if they disagree. The
catalog's inline `<style>`/sprite must stay consistent with the shipped foundation —
the catalog `<link>`s the real `blog-index.css` (single source of truth for the
component styling) and only inlines demo chrome (masthead/footer/variation labels).
Selection hooks: `data-keel-catalog` on `<main>`, `data-keel-block-group` on each
`<section>`, `data-keel-block` + `data-keel-variant` (+ `data-keel-requires-js`) on
each variant `<article>`.

## Override hooks (config-contract)

See the table + examples in [`README.md`](README.md). Every hook lives in
`keel_cms/config.py` (dotted-path resolution via `import_string`) and degrades to a
safe no-op default, so the package imports and runs standalone with zero config.

Two coupling seams intentionally left as documented TODO for the host:

- **`editor_persist_hook`** (`editor_views.py`) — the "save body while editing"
  persist path is a no-op until the host supplies a callable that writes the body
  onto its Post/NewsPost and kicks a re-render task (the source project used a
  Celery `refresh_*_rendered` task). Conversion works without it.
- **`editor_permission_hook`** — defaults to `user.is_staff`; override to match the
  host's content-editor permission.

## Content sitemaps (`sitemaps.py`)

`keel_cms.sitemaps` ships the content buckets for a host's `sitemap.xml` — blog
posts, news articles, and desk/topic/tag archives — regenerated on every request
(each read hits current DB state; no cron). A host wires it in three steps:

1. Register the `keel_cms` URL namespace at the host's real serving paths
   (`keel_cms.contrib.urls` is the reference; a host that serves blog/news at
   other paths registers its own `app_name = "keel_cms"` aliases). The sitemap
   reverses `keel_cms:post_detail` / `keel_cms:news_post_detail` /
   `keel_cms:team_desk` / `keel_cms:topic_list` / `keel_cms:tag_detail`.
2. Compose `SITEMAPS = {"landings": LandingSitemap, **content_sitemaps()}` and
   hand it to Django's `sitemap` view. `all_sitemaps()` does the same composition
   when keel-seo is installed.
3. Add `django.contrib.sitemaps` to `INSTALLED_APPS` (it ships the `sitemap.xml`
   template) and ensure the Sites-framework `Site.domain` is the real domain (the
   sitemap builds absolute URLs from it).

A bucket whose `keel_cms:*` name is not registered is emitted **empty** rather
than raising, so a host with no topic/desk/tag pages simply omits those buckets
with no per-project sitemap code. The archive thin-content threshold is
`KEEL_CMS["archive_min_contents"]` (default 4).

## The `cp-` class contract (with keel-ui)

`markdown_convert` and the editor JS recognize the `cp-*` component-library class
prefix (figure/chart wrappers, embed figures, component chips). This is a
deliberate contract with **keel-ui** — do not rename it. `html_sanitize` does *not*
allowlist `cp-*`: pipeline-generated bodies (`is_pipeline_generated=True`) skip the
sanitizer entirely, which is where `cp-*` blocks survive. Non-pipeline user edits
are sanitized and lose raw `cp-*` markup by design.

## Adoption note (host migration — reuse existing tables)

The models keep the source project's literal `db_table` names (`blog_post`,
`blog_tag`, `blog_content_plan`, `news_post`, `news_comment`, …). A host that
already has these tables (i.e. is migrating off in-repo `blog`/`news` apps) can
adopt keel-cms with a **state-only** migration rather than a data copy:

1. Point `KEEL_CMS_LANDING_MODEL` at the host's existing money-page/landing model
   (default `keel_seo.Landing`).
2. Fake-apply `keel_cms 0001_initial` (`migrate keel_cms 0001 --fake`) once the old
   `blog`/`news` app migrations are squashed/retired, since the tables already
   exist. Sequence this behind the host's canary deploy and verify a known glossary
   page + a blog detail page still render before cutover.
3. If a table name must differ, override the model's `db_table` in a host
   migration (`AlterModelTable`) — but prefer keeping the literals so no rename runs.

`TopicCluster.conversion_landing` targets the swappable `KEEL_CMS_LANDING_MODEL`;
the initial migration computes its dependency from that setting. If the target app
exposes no migration graph, adjust the computed `swappable_dependency` in
`0001_initial.py`.

## Third-party dependencies

`Django>=4.2`, `markdown2`, `nh3`, `beautifulsoup4`, `keel-ui` (glossary visuals).
Optional `markdownify` (`keel-cms[editor]`) for the HTML→Markdown editor direction;
absent, that direction falls back to plain text.
