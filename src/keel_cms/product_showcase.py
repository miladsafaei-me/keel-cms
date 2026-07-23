"""
Mid-article product showcase for posts.

The SELECTION ALGORITHM is generic and ships in keel-cms: it picks the post's
primary market, orders the funnel cards by the post's ``intent_frame`` (commercial
vs informational), and lets the topic cluster's ``conversion_landing`` override the
lead card. The market->surface map and the card catalog are host DATA:

* ``KEEL_CMS["market_hubs_hook"]`` -> ``{market_slug: {surface_key: url|None}}`` —
  the host's funnel surfaces. Empty (default) -> no showcase is built.
* ``KEEL_CMS["showcase_cards"]`` -> the card catalog + ordering the host declares
  (see the shape below). Empty (default) -> no showcase is built.

``showcase_cards`` shape::

    {
        "hub_defaults": {"signals": "/signals", "extensions": "/tools", ...},
        # each card: key -> {surface_key, icon, kind, title, desc, cta,
        #                    title_template?}. title_template may contain
        #                    "{label}" which is filled with the market name.
        "cards": {"signals": {...}, "telegram": {...}, ...},
        "order_informational": ["signals", "telegram", "extensions", "connector"],
        "order_commercial": ["extensions", "connector", "telegram", "signals"],
        "commercial_frames": ["best", "compare", "review", "vs"],
    }

With no configuration ``build_product_showcase`` returns ``{"market_label": "",
"cards": []}``.
"""

from __future__ import annotations

from .config import market_hubs


def _keel_cms(key, default=None):
    from django.conf import settings

    return getattr(settings, "KEEL_CMS", {}).get(key, default)


def _showcase_cfg() -> dict:
    return _keel_cms("showcase_cards", {}) or {}


def _intent_frame(post) -> str:
    """The post's planned intent_frame (from its ContentPlan), or '' if unplanned."""
    try:
        plan = getattr(post, "content_plan", None)
        return (plan.intent_frame or "").strip().lower() if plan else ""
    except Exception:
        return ""


def _conversion_landing(post):
    """The money page the post's topic cluster declares (``conversion_landing``).

    A cluster-level pointer set in the admin — when present it beats the
    market-derived guess. ``None`` for cluster-less posts / undeclared clusters.
    """
    try:
        cluster = post.topic_cluster
        return cluster.conversion_landing if cluster else None
    except Exception:
        return None


def _primary_market(post):
    """Pick the market that drives the deep links.

    Prefer the first market that has its own hub pages; otherwise the first market
    on the post; ``None`` when the post has no markets.
    """
    hubs_map = market_hubs()
    try:
        markets = list(post.markets.all())
    except Exception:
        return None
    if not markets:
        return None
    for market in markets:
        if market.slug in hubs_map:
            return market
    return markets[0]


def build_product_showcase(post) -> dict:
    """Return the showcase context: ``{"market_label": str, "cards": [...]}``.

    ``market_label`` is the human market name when the post maps to a known market
    (used to title the cards); empty when the post is cross-market / unmapped, which
    yields generic card titles. Returns empty cards when the host has not configured
    a card catalog + hub map.
    """
    cfg = _showcase_cfg()
    catalog = cfg.get("cards") or {}
    if not catalog:
        return {"market_label": "", "cards": []}

    hubs_map = market_hubs()
    hub_defaults = cfg.get("hub_defaults") or {}
    order_info = cfg.get("order_informational") or list(catalog.keys())
    order_comm = cfg.get("order_commercial") or list(catalog.keys())
    commercial_frames = set(cfg.get("commercial_frames") or ())

    market = _primary_market(post)
    hubs = hubs_map.get(market.slug) if market else None
    label = market.name if hubs else ""

    def _href(card_key: str) -> str:
        surface = catalog[card_key].get("surface_key", card_key)
        if hubs and hubs.get(surface):
            return hubs[surface]
        return hub_defaults.get(surface, "")

    def _title(card_key: str) -> str:
        card = catalog[card_key]
        tmpl = card.get("title_template")
        if tmpl and label:
            return tmpl.replace("{label}", label).replace("  ", " ").strip()
        return card.get("title", "")

    by_key = {}
    for key, card in catalog.items():
        by_key[key] = {
            "key": key,
            "href": _href(key),
            "icon": card.get("icon", ""),
            "kind": card.get("kind", ""),
            "title": _title(key),
            "desc": card.get("desc", ""),
            "cta": card.get("cta", ""),
        }

    order = order_comm if _intent_frame(post) in commercial_frames else order_info
    order = [k for k in order if k in by_key]
    cards = [{**by_key[k], "primary": i == 0} for i, k in enumerate(order)]

    landing = _conversion_landing(post)
    if landing is not None:
        lead = {
            "key": "conversion",
            "href": landing.url,
            "icon": cfg.get("conversion_icon", "fa-solid fa-bullseye"),
            "kind": cfg.get("conversion_kind", "Recommended"),
            "title": landing.title,
            "desc": cfg.get(
                "conversion_desc",
                "The tool readers of this guide most often start with — "
                "see it in action and decide in minutes.",
            ),
            "cta": cfg.get("conversion_cta", "See how it works"),
            "primary": True,
        }
        cards = [lead] + [{**c, "primary": False} for c in cards[:3]]
    return {"market_label": label, "cards": cards}
