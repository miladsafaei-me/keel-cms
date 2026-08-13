#!/usr/bin/env python3
"""Build + drift-check the Blog Index Template manifest from the catalog HTML.

`design_library/blog_index/blog_index_template.html` is the authored source of layout
and the `data-keel-*` selection hooks. This script holds the editorial metadata
(purpose / layout / bestFor prose) keyed by the same block+variant slugs, asserts it
matches the hooks actually present in the HTML (fails loudly on drift), and writes
`manifest.json`. Run after adding, renaming, or removing a variant:

    python scripts/build_blog_index_manifest.py

Repo-only tooling: it lives under scripts/ (outside src/), so it is not shipped in the
wheel — only the two reference outputs (the HTML + the manifest) ship with the package.
"""
from __future__ import annotations

import json
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "src/keel_cms/design_library/blog_index"
HTML = CATALOG / "blog_index_template.html"
OUT = CATALOG / "manifest.json"

CATALOG_VERSION = "1.0"

# Editorial metadata — prose keyed by the block + variant slugs that the HTML carries
# as data-keel-block / data-keel-variant. `js` must match the HTML's data-keel-requires-js.
BLOCKS = [
  {"block": "hero", "title": "Hero / Featured News",
   "purpose": "Above-the-fold lead: one prominent story plus a set of supporting items.",
   "whenToUse": "The top of the blog index. Pick exactly one hero variant.",
   "variants": [
     {"slug": "classic-split", "name": "Classic Split", "js": False,
      "layout": "60/40 split — a large lead feature on the left, six stacked list items on the right.",
      "bestFor": "A single dominant lead beside a scannable secondary list."},
     {"slug": "top-hero-grid", "name": "Top Hero Grid", "js": False,
      "layout": "A full-width horizontal lead above a four-column strip of supporting cards.",
      "bestFor": "One lead plus an even row of equally-weighted follow-ups."},
     {"slug": "center-asymmetric", "name": "Center Hero Asymmetric", "js": False,
      "layout": "A central feature flanked by two cards on the left and two on the right.",
      "bestFor": "A balanced, magazine-style front with a strong centerpiece."},
     {"slug": "magazine-mosaic", "name": "Magazine Mosaic", "js": False,
      "layout": "A 2-row lead tile with five smaller cards staggered around it.",
      "bestFor": "A dense editorial mosaic when several strong stories compete."},
     {"slug": "lead-quad-sidebar", "name": "Lead + Quad & Sidebar", "js": False,
      "layout": "A lead over a 2x2 sub-grid, plus one tall highlight card on the right edge.",
      "bestFor": "A lead, a compact cluster, and one evergreen highlight together."},
   ]},
  {"block": "latest", "title": "Latest News Grid",
   "purpose": "The main chronological article feed.",
   "whenToUse": "The core list of recent posts on the index.",
   "variants": [
     {"slug": "three-column-cards", "name": "3-Column Standard Cards", "js": False,
      "layout": "A uniform three-column grid of vertical cards (image, tag, title, excerpt, byline footer).",
      "bestFor": "The default, predictable chronological feed."},
     {"slug": "horizontal-rows", "name": "Horizontal Card Rows", "js": False,
      "layout": "A two-column layout of image-left / text-right cards.",
      "bestFor": "A scannable feed that shows more text per card."},
     {"slug": "masonry-mixed", "name": "Masonry / Varied Cards", "js": False,
      "layout": "A multi-column masonry grid; card heights vary by excerpt length.",
      "bestFor": "A lively, non-uniform feed that breaks grid monotony."},
     {"slug": "density-grid", "name": "Density-Focused Grid", "js": False,
      "layout": "A compact four-column grid with small thumbnails and dense metadata.",
      "bestFor": "High-volume output where many items must fit above the fold."},
     {"slug": "bento-box", "name": "Bento Box News Grid", "js": False,
      "layout": "A 2x2 lead tile beside a block of four small cards, then a uniform row.",
      "bestFor": "A feed with built-in hierarchy — one hero item per band."},
   ]},
  {"block": "trending", "title": "Trending / Most Read",
   "purpose": "Typography-driven ranking of most-read or momentum stories.",
   "whenToUse": "A 'most read' / 'trending' module or sidebar.",
   "variants": [
     {"slug": "numbered-rank", "name": "Numbered Rank List", "js": False,
      "layout": "A vertical list with large 01-05 rank numerals, tiny thumbnails and view/comment stats.",
      "bestFor": "A most-read module or sidebar."},
     {"slug": "accordion-expanding", "name": "Accordion / Expanding List", "js": False,
      "layout": "A native <details> list; the open item reveals a full image, excerpt and byline.",
      "bestFor": "A compact list that expands on demand — no JavaScript."},
     {"slug": "tabbed-timeframe", "name": "Tabbed Trending", "js": False,
      "layout": "CSS-only tabs (Hourly / Daily / Weekly) over a two-column ranked list with thumbnails.",
      "bestFor": "Switching trending windows without navigation — no JavaScript."},
     {"slug": "timeline", "name": "Timeline Trending", "js": False,
      "layout": "A chronological rail with connectors, timestamps and 16:9 thumbnails.",
      "bestFor": "A time-ordered 'what happened' rundown."},
     {"slug": "horizontal-scroll", "name": "Horizontal Scrolling Cards", "js": False,
      "layout": "A snap-scrolling strip of compact ranked cards with momentum stats.",
      "bestFor": "A swipeable trending row, mobile-first."},
   ]},
  {"block": "category", "title": "Category Spotlight",
   "purpose": "Topic/section spotlight: an anchor story per topic plus related headlines.",
   "whenToUse": "Surfacing a specific section (Tech, Business, Politics, ...).",
   "variants": [
     {"slug": "big-plus-list", "name": "1 Big + 4 Item List Split", "js": False,
      "layout": "One large lead article beside a four-item thumbnail headline list.",
      "bestFor": "Spotlighting a section with one anchor plus quick links."},
     {"slug": "multi-column", "name": "Multi-Category Columns", "js": False,
      "layout": "Three parallel topic columns, each a full lead card over three thumbnail headlines.",
      "bestFor": "Showing several sections side by side."},
     {"slug": "feature-plus-grid", "name": "Feature Story + Sub-topic Grid", "js": False,
      "layout": "A wide horizontal feature over a three-column sub-topic grid.",
      "bestFor": "A section front: one feature plus its sub-topics."},
     {"slug": "editorial-block", "name": "Editorial Highlight Block", "js": False,
      "layout": "A tinted container: one major analysis piece beside five single-column briefing cards.",
      "bestFor": "An opinion/analysis highlight with related briefs."},
     {"slug": "dual-feature", "name": "Side-by-Side Dual Feature", "js": False,
      "layout": "Two equal-weight stories side by side, each with two nested sub-headlines.",
      "bestFor": "Pitting two co-lead stories with their follow-ups."},
   ]},
  {"block": "media", "title": "Media / Video / Multimedia",
   "purpose": "Video / podcast / multimedia shelves.",
   "whenToUse": "When the blog has watch or listen content.",
   "variants": [
     {"slug": "main-player", "name": "Main Video Player Layout", "js": False,
      "layout": "One large 16:9 player (icon play control) beside a four-item playlist.",
      "bestFor": "A featured video with an up-next queue."},
     {"slug": "video-strip", "name": "Video Carousel / Strip", "js": False,
      "layout": "A four-column row of video cards with duration chips and view counts.",
      "bestFor": "A row of related clips."},
     {"slug": "dark-strip", "name": "Dark Mode Media Strip", "js": False,
      "layout": "A dark-themed container holding a five-item video grid with channel tags.",
      "bestFor": "A visually distinct video shelf that contrasts the page."},
     {"slug": "video-podcast-hybrid", "name": "Video + Audio / Podcast Hybrid", "js": False,
      "layout": "A split: three video cards on one side, three podcast cards (with waveforms) on the other.",
      "bestFor": "Mixing watch and listen in one module."},
     {"slug": "live-plus-replays", "name": "Grid Showcase with Live Stream", "js": False,
      "layout": "One LIVE card (status badge + viewer count) plus four categorized replay cards.",
      "bestFor": "A live stream with recent replays."},
   ]},
  {"block": "slider", "title": "Sliders / Carousels",
   "purpose": "Interactive, swipeable modules (require the bundled script).",
   "whenToUse": "When paging or rotation lets you fit more stories in less space.",
   "variants": [
     {"slug": "card-carousel", "name": "Card Carousel", "js": True,
      "layout": "Four vertical cards in a row; header prev/next slide the next set into view.",
      "bestFor": "An 'in depth' shelf the reader pages through."},
     {"slug": "featured-rotator", "name": "Featured Rotator + Side List", "js": True,
      "layout": "A big featured story auto-rotates (dots + arrows) beside a fixed side list.",
      "bestFor": "A rotating hero with an accompanying headline list."},
     {"slug": "story-slider", "name": "Full-Width Story Slider", "js": True,
      "layout": "One wide split slide (image + text) rotates through the day's lead stories.",
      "bestFor": "A cinematic single-story rotator."},
     {"slug": "thumbnail-gallery", "name": "Thumbnail-Nav Gallery", "js": True,
      "layout": "One large slide switched by a strip of thumbnail buttons below.",
      "bestFor": "A curated set the reader browses by thumbnail."},
   ]},
  {"block": "live", "title": "Live / Real-Time",
   "purpose": "Real-time, continuously-updating modules (require the bundled script).",
   "whenToUse": "For live events, breaking coverage, or a 'happening now' feel.",
   "variants": [
     {"slug": "auto-updating-feed", "name": "Auto-Updating Feed Column", "js": True,
      "layout": "Every few seconds a new item flashes in at the top and the oldest fades out.",
      "bestFor": "A wire / breaking feed that must feel live."},
     {"slug": "breaking-ticker", "name": "Breaking Ticker + Latest", "js": True,
      "layout": "A continuously scrolling breaking-news marquee over a self-refreshing list.",
      "bestFor": "A breaking-news bar plus a latest list."},
     {"slug": "live-blog", "name": "Live Blog (Minute-by-Minute)", "js": True,
      "layout": "A timestamped live blog with a visible countdown that posts a new update at zero.",
      "bestFor": "Minute-by-minute event coverage."},
     {"slug": "live-dashboard", "name": "Live Now Dashboard", "js": True,
      "layout": "'Happening now' live streams with ticking viewer counters and a moving market strip.",
      "bestFor": "A live status board or 'now' page."},
   ]},
  {"block": "learn", "title": "Explainer / Learn",
   "purpose": "Educational / explainer formats.",
   "whenToUse": "When the goal is to teach — explainers, how-it-works, glossary, a series.",
   "variants": [
     {"slug": "explainer-cards", "name": "Explainer Cards", "js": False,
      "layout": "'Understand it in a minute' cards: learn badge, difficulty level, key-takeaway checklist, learn-time.",
      "bestFor": "Explaining the concept behind a story."},
     {"slug": "step-by-step", "name": "Step-by-Step How It Works", "js": False,
      "layout": "A numbered four-step path, each step with an image and a short instruction.",
      "bestFor": "Walking through a process or mechanism."},
     {"slug": "glossary", "name": "Glossary / Key Terms", "js": False,
      "layout": "A jargon-buster grid; click a term to expand its definition (CSS-only <details>).",
      "bestFor": "Defining key terms inline — no JavaScript."},
     {"slug": "learning-series", "name": "Learning Series / Curriculum", "js": False,
      "layout": "A featured course beside a numbered syllabus with a progress bar and per-lesson times.",
      "bestFor": "A multi-part educational series or academy module."},
   ]},
]


class Hooks(HTMLParser):
    """Collect the (block, variant) -> requiresJs hooks actually present in the HTML."""

    def __init__(self):
        super().__init__()
        self.variants = {}   # (block, variant) -> requiresJs
        self.groups = set()  # block

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if "data-keel-block-group" in d:
            self.groups.add(d["data-keel-block-group"])
        if "data-keel-variant" in d and "data-keel-block" in d:
            self.variants[(d["data-keel-block"], d["data-keel-variant"])] = (
                d.get("data-keel-requires-js") == "true"
            )


def fail(msg):
    print(f"drift: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    hooks = Hooks()
    hooks.feed(HTML.read_text(encoding="utf-8"))

    table_pairs = {(b["block"], v["slug"]): v["js"] for b in BLOCKS for v in b["variants"]}
    table_blocks = {b["block"] for b in BLOCKS}

    if hooks.groups != table_blocks:
        fail(f"block groups differ. html={sorted(hooks.groups)} table={sorted(table_blocks)}")
    if set(hooks.variants) != set(table_pairs):
        only_html = sorted(set(hooks.variants) - set(table_pairs))
        only_table = sorted(set(table_pairs) - set(hooks.variants))
        fail(f"variant sets differ. html-only={only_html} table-only={only_table}")
    for key, js in table_pairs.items():
        if hooks.variants[key] != js:
            fail(f"requiresJs mismatch for {key}: html={hooks.variants[key]} table={js}")

    manifest = {
        "template": "blog-index",
        "title": "Blog Index Template",
        "source": "keel-cms design library",
        "catalogVersion": CATALOG_VERSION,
        "file": "blog_index_template.html",
        "selectors": {
            "catalogRoot": '[data-keel-catalog="blog-index"]',
            "blockGroup": '[data-keel-block-group="<block>"]  (also id="block-<block>")',
            "variant": '[data-keel-block="<block>"][data-keel-variant="<slug>"]  (also id="<block>__<slug>")',
            "needsScript": '[data-keel-requires-js="true"]',
        },
        "howToUse": [
            "Decide which blocks the project blog index needs (usually one hero + one latest, plus any of trending/category/media/slider/live/learn).",
            "For each chosen block pick exactly ONE variant using bestFor / layout below.",
            "Copy each chosen variant's <article data-keel-variant> subtree into the project template.",
            "Keep the shared foundation: the :root design tokens, the component CSS (.card/.media/.chip/.badge/.meta/.avatar), and the #i-* SVG icon sprite.",
            "Include the bundled <script> only if any chosen variant has requiresJs=true (all slider and live variants).",
            "Swap the :root tokens (colors, fonts, radius, spacing) for the project brand. Keep 16:9 media and never put text over an image.",
        ],
        "sharedFoundation": {
            "designTokens": ":root CSS custom properties — colors, topic hues, spacing scale, radius, shadow, fonts. Swap per project.",
            "components": ["card", "media (strict 16:9)", "chip (topic tag)", "badge (breaking/live/premium/update)", "meta (avatar/author/time/read-time/comments)", "avatar (CSS initials)", "icon sprite (#i-*)"],
            "script": "One vanilla <script> (no inline handlers) powers carousels, rotating sliders, auto-updating feeds, the live-blog countdown, ticking counters and the curriculum progress bar. It reads data-* hooks, pauses on hover, and honors prefers-reduced-motion. Seed content renders with JS disabled.",
            "rules": ["Every image is 16:9 (aspect-ratio:16/9; object-fit:cover).", "No text over images — play/live indicators are icon controls; textual badges sit outside the image.", "CSS variables only; no hardcoded colors/spacing.", "Semantic tags + named selectors."],
        },
        "blocks": [
            {
                "block": b["block"],
                "title": b["title"],
                "purpose": b["purpose"],
                "whenToUse": b["whenToUse"],
                "sectionId": f'block-{b["block"]}',
                "variants": [
                    {
                        "id": f'{b["block"]}__{v["slug"]}',
                        "block": b["block"],
                        "variant": v["slug"],
                        "name": v["name"],
                        "layout": v["layout"],
                        "bestFor": v["bestFor"],
                        "requiresJs": v["js"],
                    }
                    for v in b["variants"]
                ],
            }
            for b in BLOCKS
        ],
    }

    OUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    n = sum(len(b["variants"]) for b in BLOCKS)
    print(f"OK: {len(BLOCKS)} blocks, {n} variants in sync with the HTML hooks -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
