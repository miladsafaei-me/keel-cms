"""Data for the post-detail right-hand aside (quiet reference boxes).

The aside is intentionally low-key — no CTA-style buttons — so the reader's focus
stays on the article column. Its payload (market-aware Related Products, broker /
exchange boxes, VIP-channel links, a market-matched affiliate banner, Popular
Insights) is entirely host-owned business data: keel-cms ships only the SLOT, not
the SignalBots broker/exchange/VIP content.

The host supplies the whole payload through ``KEEL_CMS["aside_data_hook"]`` — a
dotted-path callable ``(post) -> dict``. The template consuming this decides which
keys it renders; with no hook configured the aside renders nothing.
"""

from __future__ import annotations

from .config import aside_data
from .product_showcase import _primary_market  # shared market-resolution helper


def build_aside(post) -> dict:
    """Return the host-provided aside payload for ``post`` (empty dict by default).

    Delegates entirely to ``KEEL_CMS["aside_data_hook"]``; the shape is whatever the
    host template expects (e.g. ``{"related_products": {...}, "broker_box": {...},
    "banner": {...}, ...}``). Keeping the data out of the package is what keeps
    keel-cms domain-neutral.
    """
    return aside_data(post)


def build_related_products(post) -> dict:
    """Convenience accessor for the aside's Related Products block, if the host
    payload includes a ``related_products`` key. Empty dict otherwise."""
    return build_aside(post).get("related_products", {}) or {}


def build_aside_banner(post):
    """Convenience accessor for the aside's market-matched banner, if the host
    payload includes a ``banner`` key. ``None`` otherwise."""
    return build_aside(post).get("banner")
