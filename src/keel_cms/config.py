"""Host configuration surface for keel-cms.

A consuming project configures keel-cms through a ``KEEL_CMS`` settings dict; every
key is optional and the defaults make the package work standalone (every hook
degrades to a safe no-op, so ``import keel_cms`` succeeds with no configuration):

    KEEL_CMS = {
        # Brand string used in schema.org SITE_NAME, page <title> composition, and
        # the glossary meta-title template. Empty by default (kept out of code so
        # keel-cms stays domain-neutral).
        "site_name": "Acme",

        # Meta <title> suffix appended to glossary-term pages, e.g.
        # "What is Slippage? | Acme Trading Glossary". Blank -> no suffix.
        "glossary_title_suffix": "| Acme Trading Glossary",

        # Dotted path to a callable returning the editorial-desk DATA the host owns
        # (the framework — resolution + schema rendering — ships in the package;
        # the desk copy does not). Signature: () -> list[dict]. See README for the
        # dict shape. Default: no desks (the desk framework no-ops gracefully).
        "desks_hook": "myapp.editorial.desks",

        # Dotted path to a callable returning the single Editorial Board reviewer
        # DATA the host owns. Signature: () -> dict. Default: no board (schema
        # reviewedBy is simply omitted).
        "board_hook": "myapp.editorial.board",

        # Dotted path to a callable returning the host's entity registry that the
        # body auto-linker wraps at render time (broker/exchange name variants ->
        # affiliate URL -> family/market). Signature: () -> list[dict]. See README
        # for the entry shape. Default: empty -> the linker is a no-op pass-through.
        "entity_registry_hook": "myapp.monetization.entity_registry",

        # Dotted path to a callable returning the host's funnel-surface map for the
        # mid-article product showcase (market slug -> {surface: url}). Signature:
        # () -> dict. Default: empty -> no showcase is built.
        "market_hubs_hook": "myapp.funnel.market_hubs",

        # Dotted path to a callable that builds the post-detail aside payload for a
        # given post (host-owned broker/exchange/VIP data). Signature:
        # (post) -> dict. Default: empty -> no aside data.
        "aside_data_hook": "myapp.funnel.aside_data",

        # Dotted path to a callable returning the schema.org Organization node for
        # the site publisher. Signature: (request) -> dict. Default: a minimal
        # Organization node derived from ``site_name`` + the request host.
        "organization_node_hook": "myapp.schema.organization_node",

        # Fixed display order for glossary categories (a list of category labels).
        # Default: [] -> categories fall back to alphabetical order.
        "glossary_category_order": ["Signal Mechanics", "Risk & Performance Metrics"],

        # Human labels for internal landing URLs stored on a term's
        # ``related_surfaces``: {url: label}. Default: {} -> the raw URL is shown
        # as its own label.
        "glossary_surface_labels": {"/pricing": "Pricing"},
    }

Two related settings live at the top level of ``settings`` rather than inside the
``KEEL_CMS`` dict, because Django resolves them at model-import time:

    # Swappable target of ``TopicCluster.conversion_landing``. Point it at the
    # host's money-page / landing model. Default: ``"keel_seo.Landing"`` (the
    # sibling package's registry). A host with its own Landing model overrides it.
    KEEL_CMS_LANDING_MODEL = "core.Landing"

    # db_table for the swappable Landing target is owned by that model's package,
    # not here.

    # Set True ONLY when adopting a host's pre-existing blog_*/news_* tables: the
    # initial migration then records model state without emitting CREATE TABLE.
    # Default False -> a fresh project's initial migration creates the tables.
    KEEL_CMS_ADOPT_EXISTING = True
"""
from django.conf import settings
from django.utils.module_loading import import_string

_DEFAULTS = {
    "site_name": "",
    "glossary_title_suffix": "",
    "desks_hook": None,
    "board_hook": None,
    "entity_registry_hook": None,
    "market_hubs_hook": None,
    "aside_data_hook": None,
    "organization_node_hook": None,
    "glossary_category_order": [],
    "glossary_surface_labels": {},
    # Admin OS staff panel. ``admin_os_enabled`` is advisory only (the host opts in
    # by including ``keel_cms.admin_os.urls``, or the batteries-included
    # ``keel_cms.admin_os.site_urls``; nothing auto-mounts). ``admin_logout_url`` is
    # the target of the panel navbar "Sign out" link; it defaults to the Django admin
    # logout under the ``site_urls`` remount prefix, so a keel-cms host that does not
    # run keel-web's auth/client apps still has a working logout.
    "admin_os_enabled": True,
    "admin_logout_url": "/staff/django/logout/",
}

# Default swappable target for TopicCluster.conversion_landing. Resolved at
# model-import time from the top-level setting so a host can point the FK at its
# own Landing/money-page model without editing package code.
DEFAULT_LANDING_MODEL = "keel_seo.Landing"


def landing_model_ref() -> str:
    """Return the swappable Landing model reference (``"app_label.ModelName"``)."""
    return getattr(settings, "KEEL_CMS_LANDING_MODEL", DEFAULT_LANDING_MODEL)


def adopt_existing() -> bool:
    """Whether the initial migration adopts pre-existing tables (state-only) rather
    than creating them. Default False: a fresh project creates the tables."""
    return bool(getattr(settings, "KEEL_CMS_ADOPT_EXISTING", False))


def cms_setting(key):
    return getattr(settings, "KEEL_CMS", {}).get(key, _DEFAULTS[key])


def _resolve_hook(key):
    """Import the dotted-path callable for ``key`` (or ``None`` if unset/broken)."""
    dotted = cms_setting(key)
    if not dotted:
        return None
    try:
        return import_string(dotted)
    except Exception:
        return None


def site_name() -> str:
    """The host brand string (empty by default)."""
    return cms_setting("site_name") or ""


def glossary_title_suffix() -> str:
    return cms_setting("glossary_title_suffix") or ""


def desks_data() -> list:
    """Resolve the ``desks_hook`` to the host's editorial-desk data list.

    The framework (resolution + schema rendering) ships in the package; the desk
    copy is host-owned. Any failure falls back to an empty list, i.e. no desks
    rather than fabricated ones.
    """
    hook = _resolve_hook("desks_hook")
    if hook is None:
        return []
    try:
        return list(hook() or [])
    except Exception:
        return []


def board_data() -> dict:
    """Resolve the ``board_hook`` to the host's Editorial Board reviewer data."""
    hook = _resolve_hook("board_hook")
    if hook is None:
        return {}
    try:
        return dict(hook() or {})
    except Exception:
        return {}


def entity_registry() -> list:
    """Resolve the ``entity_registry_hook`` to the host's linkable-entity registry.

    Each entry is a dict with keys ``variants`` (tuple/list of name spellings),
    ``name`` (canonical), ``url`` (affiliate/IB link), ``family`` and ``market``.
    Default (no hook): an empty registry, so the body auto-linker becomes a no-op
    pass-through.
    """
    hook = _resolve_hook("entity_registry_hook")
    if hook is None:
        return []
    try:
        return [e for e in (hook() or []) if e.get("url")]
    except Exception:
        return []


def market_hubs() -> dict:
    """Resolve the ``market_hubs_hook`` to the host's funnel-surface map.

    ``{market_slug: {"signals": url, "telegram": url, "connector": url|None, ...}}``.
    Default: an empty map, so the mid-article product showcase builds nothing.
    """
    hook = _resolve_hook("market_hubs_hook")
    if hook is None:
        return {}
    try:
        return dict(hook() or {})
    except Exception:
        return {}


def aside_data(post) -> dict:
    """Resolve the ``aside_data_hook`` to the post-detail aside payload.

    Host-owned data (broker box, exchange box, VIP links, market-matched banner).
    Default: an empty dict, so the aside renders nothing.
    """
    hook = _resolve_hook("aside_data_hook")
    if hook is None:
        return {}
    try:
        return dict(hook(post) or {})
    except Exception:
        return {}


def glossary_category_order() -> list:
    order = cms_setting("glossary_category_order")
    return list(order) if order else []


def glossary_surface_labels() -> dict:
    labels = cms_setting("glossary_surface_labels")
    return dict(labels) if labels else {}


def admin_os_enabled() -> bool:
    """Advisory flag; the host still opts in by including the admin_os URLconf."""
    return bool(cms_setting("admin_os_enabled"))


def admin_logout_url() -> str:
    return cms_setting("admin_logout_url") or "/accounts/logout/"
