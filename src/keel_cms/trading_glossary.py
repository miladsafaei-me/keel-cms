"""Glossary render service — context builders over ``keel_cms.Tag`` (is_term=True).

The public surface is read-only. Two pages are served from here: the glossary
listing and the single-term page. The category display ORDER and the internal-URL
LABELS are host content, resolved from ``KEEL_CMS``:

* ``glossary_category_order`` — a list of category labels; categories not listed
  fall back to alphabetical order after the configured ones. Empty (default) ->
  purely alphabetical.
* ``glossary_surface_labels`` — ``{internal_url: human_label}`` for the URLs stored
  on a term's ``related_surfaces``. Empty (default) -> the raw URL is its own label.

Host URL pattern ``keel_cms:trading_glossary_term`` is reversed defensively.
"""
from __future__ import annotations

from django.urls import NoReverseMatch, reverse
from django.utils.text import slugify

from .config import glossary_category_order, glossary_surface_labels

ALPHABET = [chr(c) for c in range(ord("A"), ord("Z") + 1)]


def _term_url(slug: str) -> str:
    try:
        return reverse("keel_cms:trading_glossary_term", kwargs={"slug": slug})
    except NoReverseMatch:
        return ""


def _sort_letter(name: str) -> str:
    ch = (name or "").strip()[:1].upper()
    return ch if "A" <= ch <= "Z" else "#"


def _term_row(tag) -> dict[str, object]:
    cat = (tag.parent_category or "").strip()
    aka = tag.aka if isinstance(tag.aka, list) else []
    search_bits = [tag.name, tag.abbreviation, *aka]
    return {
        "glossary_term": tag,
        "term_url": _term_url(tag.slug),
        "letter": _sort_letter(tag.name),
        "category_key": slugify(cat) if cat else "",
        "category_label": cat,
        "search_text": " ".join(b for b in search_bits if b).lower(),
    }


def trading_glossary_index_context() -> dict[str, object]:
    """Listing context: terms grouped A-Z, plus category + alphabet filter data."""
    from .models import Tag

    terms = list(Tag.objects.filter(is_term=True).order_by("name"))
    rows = [_term_row(t) for t in terms]

    by_letter: dict[str, list] = {}
    for r in rows:
        by_letter.setdefault(r["letter"], []).append(r)

    letters = sorted(l for l in by_letter if l != "#")
    glossary_by_letter = [(l, by_letter[l]) for l in letters]
    if "#" in by_letter:
        glossary_by_letter.append(("#", by_letter["#"]))

    order = glossary_category_order()
    present = {r["category_label"] for r in rows if r["category_label"]}
    category_filters = [(slugify(c), c) for c in order if c in present]
    for c in sorted(present):
        if c not in order:
            category_filters.append((slugify(c), c))

    active = {r["letter"] for r in rows}
    return {
        "glossary_by_letter": glossary_by_letter,
        "glossary_category_filters": category_filters,
        "glossary_alphabet": ALPHABET,
        "glossary_letters_active": sorted(active - {"#"}),
        "glossary_has_hash_bucket": "#" in active,
        "glossary_term_count": len(terms),
    }


def related_surface_links(tag) -> list[dict[str, str]]:
    """Resolve Tag.related_surfaces (URLs) into {url, label} link dicts."""
    urls = tag.related_surfaces if isinstance(tag.related_surfaces, list) else []
    labels = glossary_surface_labels()
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for u in urls:
        u = (u or "").strip()
        if not u or u in seen:
            continue
        seen.add(u)
        links.append({"url": u, "label": labels.get(u, u)})
    return links


def trading_glossary_term_context(tag) -> dict[str, object]:
    """Single-term context: heading, related terms, related surfaces, breadcrumb data."""
    from .models import Post

    related_terms = list(tag.related_terms.all().order_by("name"))
    # Up to 3 published guides tagged with this term, newest first.
    related_posts = list(
        tag.posts.filter(
            status=Post.Status.PUBLISHED,
            published_at__isnull=False,
            is_deleted=False,
        )
        .select_related("author", "category")
        .order_by("-published_at")[:3]
    )
    impact = tag.trade_impact if isinstance(tag.trade_impact, list) else []
    impact_level = impact[0] if len(impact) >= 1 else ""
    impact_text = impact[1] if len(impact) >= 2 else ""
    faq = tag.faq if isinstance(tag.faq, list) else []
    term_faqs = [
        {"q": (f.get("question") or "").strip(), "a": (f.get("answer") or "").strip()}
        for f in faq
        if isinstance(f, dict) and f.get("question") and f.get("answer")
    ]
    return {
        "term": tag,
        "term_heading": tag.get_public_heading(),
        "term_category": (tag.parent_category or "").strip(),
        "term_related_terms": related_terms,
        "term_related_posts": related_posts,
        "term_related_surfaces": related_surface_links(tag),
        "term_impact_level": impact_level,
        "term_impact_text": impact_text,
        "term_faqs": term_faqs,
    }
