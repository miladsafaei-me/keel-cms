# TODO

This file is the single source of truth for pending, follow-up, and deferred work on this project. See CLAUDE.md for the tracking rule.

Guidelines:
- Add a task here as soon as it's identified — with priority, prerequisites/dependencies, and enough context to pick it up cold.
- Group by priority: P0 (urgent / blocking / production risk), P1 (next up), P2 (backlog / nice-to-have).
- Note real dependencies explicitly ("Blocked by: ...", "Requires: ...").
- Delete a task from this file the moment it's done. This file only ever holds what's left.

## P1 — Next up
- [ ] `KeywordClusterJob` (`src/keel_cms/models.py`, migration `0007_keywordclusterjob.py`, landed v0.11.0) is a bare data model with no engine behind it yet: no `admin.py` registration (`src/keel_cms/contrib/admin.py` registers Author/Category/Tag/Market/TopicCluster/Post/NewsPost/ContentPlan but not this), no management command or service that actually drains the queue (claims a `queued` row, runs clustering, writes a resolved spec, emits `ContentPlan` rows with `source_type=keyword_clustering`), and no mention in README.md or CLAUDE.md. The model's own docstring describes the intended lifecycle (research source deposits a job → autopilot drains this queue before content production → clustering emits a spec → ContentPlan rows land). Next step is implementing that drain step (likely a management command mirroring the ContentPlan autopilot pattern) plus admin registration and a README/CLAUDE.md section documenting the model, same as the other content-plan additions.

## P2 — Backlog
- [ ] Three consumers have no sitemap infra wired to this package's `sitemaps.py` content-sitemap engine (shipped v0.5.0): binaryoptiontrading, broker-best, prop-firm-review. Standing this up per host (contrib.sitemaps in INSTALLED_APPS, a `keel_cms_urls.py` alias module, robots.txt) is host-side work, not a keel-cms code change, and is gated by the URL-creation-confirmation rule (sitemap entries are new indexable URL surface) — deferred, not to be started unprompted. See CLAUDE.md "Content sitemaps" section for the 3-step host wiring this package already supports.
- [ ] The v0.10.0 blog-index foundation (`static/keel_cms/css/blog-index.css` + `js/blog-index.js` + `templates/keel_cms/blog_index/_icons.html`) is this package's shipped deliverable, but two of its own consumers still run pre-v0.10.0 forked copies instead of linking it: signalbots (`core/templates/core/magazine.html` + `core/static/css|js/pages/blog-index.*` + `tools/gen_critical_css.js`) and revenika (`academy-index.css`, `blog/post_list.html`). Bumping their keel-cms pin alone does nothing until each switches to linking the shipped CSS/JS and deletes its fork — host-side follow-up work, one per project.
