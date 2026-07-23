"""Auto-link entity (broker/exchange) names and product-license mentions in post bodies.

Render-time layer (invoked from the post-detail render, so the result is cached
per post revision): the stored post HTML never contains an affiliate URL — entity
NAMES are wrapped with their canonical link, and (optionally) product-license
phrases with a contact-modal trigger, when the page is prepared. Why render time
and not authoring time:

* Affiliate URLs live in ONE place (the host's entity registry); when a link
  changes, every article picks it up on the next render — nothing stored in post
  bodies goes stale.
* Retroactive: every existing post gains the links with no content migration.
* The authoring pipeline stays business-blind.

Market integrity is enforced structurally: an entity is linked only when its
family (e.g. binary / forex / crypto) matches the post's markets, so an off-market
name never gains an affiliate link even if it slips into prose.

This is the SPLIT boundary. The linker MECHANISM ships in keel-cms; the DATA — the
entity registry (name variants -> URL -> family/market), the market-to-family map,
the license-phrase pattern and its GA4/modal conventions — is host-owned:

* Registry: ``KEEL_CMS["entity_registry_hook"]`` -> list of entries. Each entry is
  ``{"variants": [...], "name": str, "url": str, "family": str, "market": str}``.
  Default: empty -> the linker is a no-op pass-through.
* Market -> family map: optional ``KEEL_CMS["market_family_map"]`` ({market_slug:
  family}). Default: unmapped -> every family is linkable (the editorial naming
  rules keep names on-market).
* License phrase: optional ``KEEL_CMS["license_phrase_pattern"]`` (a regex string)
  + ``KEEL_CMS["license_modal"]`` ({href, css_class, aria_controls}). Default:
  license linking is disabled.
* Affiliate anchor conventions (rel / data-* attributes) are configurable via
  ``KEEL_CMS["affiliate_anchor"]``; the defaults follow the common
  ``rel="sponsored nofollow noopener"`` + ``target="_blank"`` standard.
"""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache

from bs4 import BeautifulSoup, NavigableString

from .config import entity_registry

# Elements whose text is never linkified: existing links, H2 section headings
# (they are the TOC anchors), code, and non-prose containers.
_SKIP_ANCESTORS = frozenset(
    {"a", "h2", "code", "pre", "script", "style", "svg", "button", "textarea"}
)

_POLICY_VERSION = "v1"

# Default affiliate anchor conventions (host may override via KEEL_CMS).
_DEFAULT_AFFILIATE_ANCHOR = {
    "rel": "sponsored nofollow noopener",
    "target": "_blank",
    "aff_loc": "blog_body",
}


def _keel_cms(key, default=None):
    from django.conf import settings

    return getattr(settings, "KEEL_CMS", {}).get(key, default)


def _market_family_map() -> dict:
    """Blog ``Market.slug`` -> entity family. Host-owned; empty when unset."""
    return _keel_cms("market_family_map", {}) or {}


def _all_families() -> frozenset:
    """Every family present in the configured registry."""
    return frozenset(e["family"] for e in entity_registry() if e.get("family"))


def _license_pattern() -> re.Pattern | None:
    """Compiled license-phrase regex, or ``None`` when license linking is disabled."""
    raw = _keel_cms("license_phrase_pattern")
    if not raw:
        return None
    try:
        return re.compile(raw, re.IGNORECASE)
    except re.error:
        return None


def allowed_families(post) -> frozenset:
    """Entity families linkable on this post (market integrity).

    Union over the post's mapped markets via the host's market->family map; a post
    with no mapped market (cross-market / unmapped, or no map configured) may link
    every family present in the registry — its prose legitimately spans markets and
    the editorial naming rules keep names on-market.
    """
    fam_map = _market_family_map()
    all_fams = _all_families()
    try:
        slugs = [m.slug for m in post.markets.all()]
    except Exception:
        return all_fams
    families = {fam_map[s] for s in slugs if s in fam_map}
    return frozenset(families) if families else all_fams


def _registry_entries() -> tuple:
    """Normalize the host registry into linkable entries (drop entries with no URL)."""
    entries = []
    for e in entity_registry():
        if not e.get("url"):
            continue
        entries.append(
            {
                "variants": tuple(e.get("variants") or (e.get("name"),)),
                "name": e.get("name") or "",
                "url": e["url"],
                "family": e.get("family") or "",
                "market": e.get("market") or "",
            }
        )
    return tuple(entries)


def _compile(registry, families):
    """One alternation regex over every allowed variant + variant->entry map."""
    variant_map = {}
    for entry in registry:
        if families and entry["family"] not in families:
            continue
        for variant in entry["variants"]:
            if variant:
                variant_map[variant] = entry
    if not variant_map:
        return None, variant_map
    ordered = sorted(variant_map, key=len, reverse=True)
    pattern = re.compile(
        r"\b(?:" + "|".join(re.escape(v) for v in ordered) + r")\b"
    )
    return pattern, variant_map


def registry_fingerprint() -> str:
    """Cache-key component: changes whenever a registry URL / the policy does.

    The render caller bakes this into its cache key, so an affiliate-link change
    invalidates every cached body on the next render automatically. Not memoized:
    the registry is host-configurable and cheap to hash.
    """
    reg = _registry_entries()
    lic = _license_pattern()
    blob = "|".join(f"{e['name']}={e['url']}" for e in reg)
    blob += f"|{lic.pattern if lic else ''}|{_POLICY_VERSION}"
    return hashlib.md5(blob.encode()).hexdigest()[:10]


def _broker_anchor(soup, entry, text):
    conv = {**_DEFAULT_AFFILIATE_ANCHOR, **(_keel_cms("affiliate_anchor", {}) or {})}
    a = soup.new_tag(
        "a",
        href=entry["url"],
        target=conv.get("target", "_blank"),
        rel=conv.get("rel", "sponsored nofollow noopener"),
    )
    a["data-broker"] = entry["name"]
    a["data-market"] = entry["market"]
    a["data-aff-loc"] = conv.get("aff_loc", "blog_body")
    a.string = text
    return a


def _license_anchor(soup, text):
    modal = _keel_cms("license_modal", {}) or {}
    a = soup.new_tag("a", href=modal.get("href", "/contact"))
    if modal.get("css_class"):
        a["class"] = modal["css_class"]
    if modal.get("data_attr"):
        a[modal["data_attr"]] = ""
    if modal.get("aria_controls"):
        a["aria-haspopup"] = "dialog"
        a["aria-controls"] = modal["aria_controls"]
    a.string = text
    return a


def link_partner_mentions(html, families, registry=None):
    """Wrap entity names with affiliate links and (optionally) license phrases with
    the modal trigger. Returns ``(html, meta)``; ``meta["license_links"]`` gates the
    modal include on the post template.

    Density: one link per entity per H2 section, and one license trigger per
    section. Component blocks (any ancestor with a ``cp-``-prefixed class) count as
    their own scope. With an empty registry and no license pattern this is an
    identity pass-through.
    """
    reg = registry if registry is not None else _registry_entries()
    pattern, variant_map = _compile(reg, frozenset(families) if families else _all_families())
    license_re = _license_pattern()

    if pattern is None and license_re is None:
        return html, {"broker_links": 0, "license_links": 0}

    soup = BeautifulSoup(html, "html.parser")
    section = 0
    seen = set()
    counts = {"broker_links": 0, "license_links": 0}
    replacements = []

    for node in soup.descendants:
        if not isinstance(node, NavigableString):
            if getattr(node, "name", None) == "h2":
                section += 1
            continue
        text = str(node)
        if not text.strip():
            continue
        parent_tags = [p for p in node.parents if getattr(p, "name", None)]
        if any(p.name in _SKIP_ANCESTORS for p in parent_tags):
            continue
        in_component = any(
            cls.startswith("cp-")
            for p in parent_tags
            for cls in (p.get("class") or [])
        )

        events = []
        if pattern is not None:
            for m in pattern.finditer(text):
                entry = variant_map[m.group(0)]
                key = ("broker", entry["name"], section, in_component)
                if key in seen:
                    continue
                seen.add(key)
                events.append((m.start(), m.end(), "broker", entry))
        if license_re is not None:
            for m in license_re.finditer(text):
                key = ("license", section, in_component)
                if key in seen:
                    continue
                seen.add(key)
                events.append((m.start(), m.end(), "license", None))
        if not events:
            continue

        events.sort(key=lambda ev: ev[0])
        new_nodes, last = [], 0
        for start, end, kind, entry in events:
            if start < last:  # overlapping match - keep the first
                seen.discard(
                    ("license", section, in_component) if kind == "license"
                    else ("broker", entry["name"], section, in_component)
                )
                continue
            if start > last:
                new_nodes.append(text[last:start])
            if kind == "broker":
                new_nodes.append(_broker_anchor(soup, entry, text[start:end]))
                counts["broker_links"] += 1
            else:
                new_nodes.append(_license_anchor(soup, text[start:end]))
                counts["license_links"] += 1
            last = end
        if last < len(text):
            new_nodes.append(text[last:])
        replacements.append((node, new_nodes))

    for node, new_nodes in replacements:
        anchor_point = node
        for new_node in new_nodes:
            if isinstance(new_node, str):
                new_node = NavigableString(new_node)
            anchor_point.insert_after(new_node)
            anchor_point = new_node
        node.extract()

    return str(soup), counts
