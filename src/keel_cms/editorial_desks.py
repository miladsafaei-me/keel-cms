"""Editorial Desks framework - per-market authorship teams (resolution + mapping).

This is the SPLIT boundary. The FRAMEWORK ships in keel-cms:

- ``desk_slug_for_market(market_names)`` resolves a post's primary market to its
  Desk slug (falling back to a configurable cross-market desk);
- ``market_to_desk()`` / ``desk_by_slug()`` build the lookup maps from the host's
  desk DATA;
- ``blog_schema.organization_for_desk`` / ``editorial_team_node`` render the Desk
  and Board as schema.org nodes.

The DATA - the ``DESKS`` list (per-market desk copy) and the ``BOARD`` dict (the
Editorial Board reviewer copy) - is host-owned and supplied through
``KEEL_CMS["desks_hook"]`` / ``KEEL_CMS["board_hook"]``. With no hooks configured,
every function degrades to a safe default (no desks, cross-market fallback slug),
so the framework never fabricates project-specific content.

Expected desk dict shape (host-supplied, see README for a full example)::

    {"slug": "forex-desk", "name": "Acme Forex Desk", "market": "forex",
     "role": "Forex Research", "icon": "fa-solid fa-chart-line", "accent": "forex",
     "paragraphs": ["...", "...", "..."]}

Expected board dict shape::

    {"slug": "editorial-board", "name": "Acme Editorial Board",
     "schema_name": "Acme Editorial & Fact-Checking Team",
     "role": "Editorial & Fact-Checking", "icon": "fa-solid fa-circle-check",
     "accent": "board", "review_anchor": "/editorial-policy#review-process",
     "paragraphs": ["...", "..."]}
"""

from __future__ import annotations

import re

from .config import board_data, cms_setting, desks_data

# Slug used when a post's market matches no configured desk. The host may add its
# own cross-market desk with this slug via the desks hook; otherwise resolution
# just returns this string.
CROSS_MARKET_DESK_SLUG = "cross-market-desk"


def desks() -> list[dict]:
    """The host's editorial-desk data (empty when no ``desks_hook`` is configured)."""
    return desks_data()


def board() -> dict:
    """The host's Editorial Board reviewer data (empty when no ``board_hook`` is set)."""
    return board_data()


def market_to_desk() -> dict[str, str]:
    """Map each desk's canonical market slug to its desk slug, from host desk data.

    An optional ``KEEL_CMS["desk_market_aliases"]`` dict ({extra_market_slug:
    desk_slug}) lets a host route a market with no dedicated desk to an existing
    one. Absent -> just the direct desk-market mapping.
    """
    mapping = {d["market"]: d["slug"] for d in desks() if d.get("market") and d.get("slug")}
    aliases = getattr_config("desk_market_aliases") or {}
    for extra_market, desk_slug in aliases.items():
        mapping.setdefault(extra_market, desk_slug)
    return mapping


def getattr_config(key):
    """Read an optional ``KEEL_CMS`` key that is not part of the core defaults set."""
    from django.conf import settings

    return getattr(settings, "KEEL_CMS", {}).get(key)


def desk_by_slug() -> dict[str, dict]:
    return {d["slug"]: d for d in desks() if d.get("slug")}


def _norm(value: str) -> str:
    """Normalize a market NAME or slug to its canonical slug (Django-free)."""
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", (value or "").lower())).strip("-")


def desk_slug_for_market(market_names) -> str:
    """Desk slug for the primary market; falls back to the cross-market desk slug."""
    mapping = market_to_desk()
    for value in market_names or []:
        slug = mapping.get(_norm(value))
        if slug:
            return slug
    return CROSS_MARKET_DESK_SLUG


def board_review_anchor() -> str:
    """The review-process URL anchor the Board's schema node points at.

    From the board data ``review_anchor`` key, or a configurable default.
    """
    b = board()
    return b.get("review_anchor") or (cms_setting("site_name") and "/editorial-policy#review-process") or "/"


def board_schema_name() -> str:
    """The name used in the schema.org ``reviewedBy`` node (Board), or ``site_name``."""
    b = board()
    return b.get("schema_name") or b.get("name") or cms_setting("site_name") or ""
