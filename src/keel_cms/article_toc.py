"""
Server-side extraction of ``<h2>`` headings for the article table of contents.

Parses stored HTML with BeautifulSoup, assigns unique ``id`` attributes on each
``h2`` (for in-page anchors), then runs the same nh3 sanitizer used elsewhere.
Serves both blog and news article render paths (news uses only the TOC builder;
the intro/showcase splits are blog-side).
"""

from __future__ import annotations

from bs4 import BeautifulSoup
from django.utils.text import slugify

from .html_sanitize import sanitize_blog_html


def split_html_before_first_h2(html: str) -> tuple[str, str]:
    """Split prepared body HTML into ``(intro, rest)`` at the first ``<h2>``.

    ``intro`` is the top-level nodes before the first second-level heading (the
    one or two lead paragraphs); ``rest`` is the first ``<h2>`` onward. Used by
    the single-column editorial layout, which surfaces the intro above Key
    Takeaways + the table of contents and renders the remaining sections after.

    The split is done on *top-level* nodes only, so the two halves stay
    well-formed HTML. When no top-level ``<h2>`` exists, the whole body is
    returned as ``rest`` (``intro`` empty) rather than cutting through a
    nested element.
    """
    if not html or not html.strip():
        return "", ""

    soup = BeautifulSoup(html, "html.parser")
    intro_parts: list[str] = []
    rest_parts: list[str] = []
    seen_h2 = False
    for node in soup.contents:
        name = getattr(node, "name", None)
        if not seen_h2 and name == "h2":
            seen_h2 = True
        (rest_parts if seen_h2 else intro_parts).append(str(node))

    if not seen_h2:
        return "", html
    return "".join(intro_parts), "".join(rest_parts)


def split_html_for_showcase(html: str) -> tuple[str, str]:
    """Split prepared body HTML into ``(before, after)`` for the mid-article
    product showcase, so the showcase can be rendered between the two halves.

    The split is placed before the **third** top-level ``<h2>`` - far enough in
    that the reader is engaged but well before the article ends. Posts with only
    two ``<h2>`` split before the second (last) section instead; posts with
    fewer than two ``<h2>`` are too short/unstructured, so the whole body is
    returned as ``before`` (``after`` empty) and no showcase is injected.

    Operates on top-level nodes only, keeping both halves well-formed HTML.
    """
    if not html or not html.strip():
        return html or "", ""

    soup = BeautifulSoup(html, "html.parser")
    nodes = list(soup.contents)
    h2_indexes = [i for i, node in enumerate(nodes) if getattr(node, "name", None) == "h2"]
    if len(h2_indexes) >= 3:
        split_at = h2_indexes[2]
    elif len(h2_indexes) == 2:
        split_at = h2_indexes[1]
    else:
        return html, ""

    before = "".join(str(node) for node in nodes[:split_at])
    after = "".join(str(node) for node in nodes[split_at:])
    return before, after


def prepare_article_html_with_h2_toc(
    html: str, *, trusted: bool = False,
) -> tuple[list[dict[str, str]], str]:
    """
    Return ``(toc_entries, sanitized_html)`` where each entry is
    ``{"label": "…", "fragment": "slug-without-hash"}``.

    ``trusted=True`` skips the nh3 sanitize pass. Use only for content
    produced by a trusted content pipeline (``post.is_pipeline_generated=True``),
    so its visual blocks (Mermaid, Chart.js canvases, custom HTML) survive.
    """
    html = html or ""
    stripped = html.strip()
    if not stripped:
        return [], ""

    if "<" not in stripped or ">" not in stripped:
        return [], (stripped if trusted else sanitize_blog_html(stripped))

    soup = BeautifulSoup(stripped, "html.parser")
    used_ids: set[str] = set()
    entries: list[dict[str, str]] = []

    for h2 in soup.find_all("h2"):
        label = h2.get_text(strip=True)
        if not label:
            continue
        existing = (h2.get("id") or "").strip()
        if existing and existing not in used_ids:
            used_ids.add(existing)
            entries.append({"label": label, "fragment": existing})
            continue
        base = slugify(label) or "section"
        candidate = base
        suffix = 2
        while candidate in used_ids:
            candidate = f"{base}-{suffix}"
            suffix += 1
        used_ids.add(candidate)
        h2["id"] = candidate
        entries.append({"label": label, "fragment": candidate})

    rendered = str(soup)
    return entries, (rendered if trusted else sanitize_blog_html(rendered))
