# keel-cms

Reusable blog / news / glossary CMS engine for Keel projects — the shared content
taxonomy models, the 3-tab body editor, the Markdown/HTML render pipeline, the
schema.org builders, and the render-time auto-linker / product-showcase / aside
slots. Extracted from SignalBots and neutralized: every project-specific piece
(brand string, editorial desks, entity/affiliate registry, funnel surfaces,
glossary categories) is a config hook, not hardcoded.

Read [`PLATFORM.md`](https://github.com/miladsafaei-me/keel-kit) (in keel-kit) for
the platform model, and this repo's [`CLAUDE.md`](CLAUDE.md) for the contract.

## What it provides

- **Models** (`keel_cms.models`) — the shared content engine: `Post`, `NewsPost`,
  `Category`, `Tag` (doubles as the glossary-term model), `Market`, `AudienceRole`,
  `AudienceLevel`, `TopicCluster`, `ContentPlan` (the unified editorial queue),
  `Comment` / `NewsComment`, `Author`, `UserIntent` / `Keyword`.
- **Render pipeline** — `markdown_convert` (Markdown↔HTML, 3-tab round-trip + the
  trusted pipeline path), `html_sanitize` (nh3 allowlist), `article_toc` (h2 TOC +
  intro/showcase splits), `blog_schema` / `news_schema` (schema.org JSON-LD),
  `feeds` (RSS — `BlogRssFeed`, served at `keel_cms:blog_rss_feed`, and the
  `{% blog_feed_link %}` templatetag that renders the `<link rel="alternate">`
  discovery tag for it in a host's `<head>`).
- **3-tab body editor** — `templates/keel_cms/_content_editor.html` +
  `static/keel_cms/{js,css}/content-editor.*` + `editor_views.content_convert`.
- **Render-time slots** (all neutralized to hooks) — `body_linking` (auto-link
  entity names / license phrases), `product_showcase` (mid-article funnel cards),
  `post_aside_data` (quiet reference aside).
- **Glossary** — `trading_glossary` (listing + single-term context over
  `Tag(is_term=True)`) and the `glossary_visuals` templatetag (renders a term's
  `visuals` specs through the **keel-ui** component library).
- **Sidebar** — `sidebar_data` / `sidebar_cache` / `news_sidebar_*` + `signals`
  (cache invalidation + ContentPlan publish-state sync).

- **Design library** (`keel_cms/design_library/`) — project-neutral design
  catalogs (references, **not** runtime templates and not served). Ships the **Blog
  Index Template**: a standalone HTML catalog of 37 interchangeable blog-index
  section variants across 8 blocks (hero, latest, trending, category, media, slider,
  live, learn) + a `manifest.json` an LLM reads to compose a project's blog index
  without forking. See
  [`design_library/README.md`](src/keel_cms/design_library/README.md).

## Consume it (host wiring)

1. `pip install keel-cms` (or an editable install during development). Optional
   `keel-cms[editor]` pulls `markdownify` for the HTML→Markdown editor direction.
2. Add `keel_cms` to `INSTALLED_APPS`. (The models FK a Landing model — see
   `KEEL_CMS_LANDING_MODEL` below; the default is `keel_seo.Landing`, so add
   `keel_seo` too, or point the setting at your own model.)
3. Run `migrate` (or, to adopt existing `blog_*` / `news_*` tables, see the
   adoption note in `CLAUDE.md`).
4. Wire the 3-tab editor endpoint into your URLconf as `keel_cms:content_convert`
   → `keel_cms.editor_views.content_convert`, and include the editor partial in
   your add/edit forms.
5. Name the public URL patterns the schema/glossary builders reverse (they are all
   reversed defensively, so unwired ones just yield empty URLs): `keel_cms:home`,
   `keel_cms:post_list`, `keel_cms:post_detail`, `keel_cms:topic_list`,
   `keel_cms:tag_detail`, `keel_cms:trading_glossary_term`, `keel_cms:team_desk`,
   `keel_cms:news_post_list`, `keel_cms:news_post_detail`, `keel_cms:news_topic_list`,
   `keel_cms:news_author_list`, `keel_cms:blog_rss_feed`.
6. Configure via `KEEL_CMS` (all optional — see `keel_cms/config.py`).
7. Optional — feed discovery: once `keel_cms:blog_rss_feed` reverses (either by
   including `keel_cms.contrib.urls` directly, or by aliasing that name at your own
   feed route the way you alias the other `keel_cms:*` names), drop
   `{% load keel_cms_tags %}{% blog_feed_link %}` into your base template's
   `<head>` to advertise it. It renders nothing if the name isn't wired, so it's
   always safe to add ahead of the URL wiring.

## Blog Index foundation (design library)

`keel_cms/design_library/blog_index/` is a **reference catalog** of 37 blog-index
section variants across 8 blocks (hero / latest / trending / category / media /
slider / live / learn), plus a `manifest.json` for machine composition. You copy
**only the per-variant markup** into your own template — the styling and behavior are
**shipped and linked**, so a `keel-cms` version bump delivers every foundation fix
(theming, RTL, motion, accessibility) with no re-copy.

Wire it once:

```django
{% load static %}
{# in <head> — render-blocking, so first paint is styled #}
<link rel="stylesheet" href="{% static 'keel_cms/css/blog-index.css' %}">

{# once inside <body>, before the blog-index markup #}
{% include "keel_cms/blog_index/_icons.html" %}

{# the blog-index root carries the scope hook; everything is scoped to it #}
<main data-keel-catalog="blog-index"> … copied variant markup … </main>

{# only if you used a slider/live variant (data-keel-requires-js) #}
<script src="{% static 'keel_cms/js/blog-index.js' %}" defer></script>
```

- **Scoped**: all foundation CSS lives under `[data-keel-catalog="blog-index"]`, so it
  never collides with your own `.card` / `.title` / `.meta`.
- **Theming**: override the tokens on the root, or just set `--brand` once (`--accent`
  inherits it). Dark theme is automatic via `prefers-color-scheme`; force it with
  `data-theme="dark"` (opt a subtree back to light with `data-theme="light"`).
- **Category colour is token-driven**: one `.chip` rule + `.accent-1..8` helpers set
  `--cat` (a neutral 8-slot palette). Remap the slots to your verticals — no topic
  names are baked into the CSS. Example: `--cat-1: var(--broker-forex);`.
- **RTL**: set `dir="rtl"` — the foundation uses logical properties throughout, so it
  mirrors with no extra CSS.
- **Images**: every variant image is 16:9 with `width`/`height` (CLS-safe); the hero
  lead models `srcset`/`sizes` + `fetchpriority` — wire your real responsive sources
  the same way.

## Config-contract / override hooks (the rawification points)

Everything project-specific is a `KEEL_CMS` key; every one degrades to a safe
no-op so `import keel_cms` works standalone.

| Hook | Default | Host provides |
|---|---|---|
| `site_name` | `""` | brand string for schema + titles |
| `glossary_title_suffix` | `""` | e.g. `"\| Acme Trading Glossary"` |
| `desks_hook` | none → no desks | `() -> list[dict]` editorial-desk data |
| `board_hook` | none → no reviewer | `() -> dict` Editorial Board data |
| `entity_registry_hook` | none → linker no-op | `() -> list[dict]` name→url→family map |
| `market_hubs_hook` | none → no showcase | `() -> dict` market slug → funnel surfaces |
| `aside_data_hook` | none → empty aside | `(post) -> dict` aside payload |
| `organization_node_hook` | minimal default | `(request) -> dict` publisher Organization |
| `glossary_category_order` | `[]` → alphabetical | list of category labels |
| `glossary_surface_labels` | `{}` → url is its own label | `{url: label}` |
| `KEEL_CMS_LANDING_MODEL` *(top-level setting)* | `"keel_seo.Landing"` | swappable money-page model for `TopicCluster.conversion_landing` |

Extra keys read directly (not in the defaults set): `desk_market_aliases`,
`market_family_map`, `license_phrase_pattern`, `license_modal`, `affiliate_anchor`,
`showcase_cards`, `editor_permission_hook`, `editor_persist_hook`.

### Example: editorial desks + board data (`desks_hook` / `board_hook`)

```python
def desks():
    return [
        {"slug": "forex-desk", "name": "Acme Forex Desk", "market": "forex",
         "role": "Forex Research", "icon": "fa-solid fa-chart-line", "accent": "forex",
         "paragraphs": ["...", "...", "..."]},
    ]

def board():
    return {
        "slug": "editorial-board", "name": "Acme Editorial Board",
        "schema_name": "Acme Editorial & Fact-Checking Team",
        "role": "Editorial & Fact-Checking", "icon": "fa-solid fa-circle-check",
        "accent": "board", "review_anchor": "/editorial-policy#review-process",
        "paragraphs": ["...", "..."],
    }
```

### Example: entity registry (`entity_registry_hook`)

```python
def entity_registry():
    return [
        {"variants": ("Pocket Option", "PocketOption"), "name": "Pocket Option",
         "url": "https://partner.example/pocket-option", "family": "binary", "market": "binary"},
        {"variants": ("Binance",), "name": "Binance",
         "url": "https://partner.example/binance", "family": "crypto", "market": "crypto"},
    ]
```

Pair it with `KEEL_CMS["market_family_map"] = {"binary-options": "binary", "crypto": "crypto"}`
so market integrity gates which family links on each post. Anchor conventions
default to `rel="sponsored nofollow noopener" target="_blank"`; override via
`KEEL_CMS["affiliate_anchor"]`.

### Example: mid-article product showcase (`market_hubs_hook` + `showcase_cards`)

```python
def market_hubs():
    return {"forex": {"signals": "/signals/forex", "telegram": "/telegram/forex", "connector": None}}

KEEL_CMS = {
    "market_hubs_hook": "myapp.funnel.market_hubs",
    "showcase_cards": {
        "hub_defaults": {"signals": "/signals", "telegram": "/telegram", "extensions": "/tools", "connector": "/connectors"},
        "cards": {
            "signals": {"surface_key": "signals", "icon": "fa-solid fa-bolt", "kind": "Live Signals",
                        "title_template": "Live {label} Signals", "title": "Live Signals",
                        "desc": "...", "cta": "Explore live signals"},
            # ...
        },
        "order_informational": ["signals", "telegram", "extensions", "connector"],
        "order_commercial": ["extensions", "connector", "telegram", "signals"],
        "commercial_frames": ["best", "compare", "review", "vs"],
    },
}
```

## Glossary data

`data/trading_glossary.example.json` ships a single placeholder term — the real
term corpus is host content (Bucket 0), not part of the package. Load your own
terms as `Tag(is_term=True)` rows.

## Status

v0.1.2 — extracted, neutralized, and consumed by SignalBots (its first host): the
existing `blog_*` / `news_*` tables are adopted via the state-only `0001`, and the
render pipeline, the 3-tab body editor, and the `ContentPlan` queue are all live.
