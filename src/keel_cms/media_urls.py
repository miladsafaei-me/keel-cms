"""Resolve a post's stored featured-image URL to a request-absolute URL for OG/JSON-LD.

Generic, request-based resolver: relative (``/media/...``) values become absolute
against the current request host; already-absolute external URLs pass through
unchanged. Social cards cannot render SVG, so an ``.svg`` value returns ``None``
(the caller then falls back to a brand default card) unless the host swaps in
richer logic elsewhere.
"""

from __future__ import annotations


def featured_image_absolute_url(request, stored: str | None) -> str | None:
    """Return an absolute image URL for Open Graph / JSON-LD, or ``None``.

    Kept deliberately minimal: the SignalBots-specific loopback-host rewriting and
    SVG->WebP sibling lookup are host concerns, so a host that needs them provides
    its own resolver and passes the result in.
    """
    value = (stored or "").strip()
    if not value:
        return None
    if value.lower().endswith(".svg"):
        return None
    if value.startswith("/"):
        return request.build_absolute_uri(value) if request else value
    return value
