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
  glossary render service, the `glossary_visuals` templatetag (keel-ui), and the
  3-tab body editor (partial + JS + CSS + `content_convert` view).
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
