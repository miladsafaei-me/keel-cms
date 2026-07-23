"""Render a glossary term's ``visuals`` specs via the keel-ui component library.

Each item in ``term.visuals`` is ``{"component_id": str, "spec": {...}, "caption": str?}``.
The component library (``keel_ui``) owns the typed catalog: it validates ``spec``
against the component's JSON Schema and renders the component's server-authored
template, so the model/editor never emits raw HTML/CSS. The same engine backs the
in-editor "visualize selection" button — this tag is just the build-time caller for
glossary.

Rendering is best-effort: a missing component or invalid spec is skipped (and
logged), so a bad spec can never 500 a term page. Terms with no ``visuals`` render
nothing.
"""

from __future__ import annotations

import logging

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from keel_ui import render as render_component
from keel_ui.registry import ComponentNotFound, get_component
from keel_ui.renderer import RenderError, SpecValidationError

register = template.Library()
log = logging.getLogger(__name__)

# Default eyebrow kicker per component category, so every visual carries an
# editorial label without per-term authoring. An item may override with its own
# ``eyebrow`` key (set "" to hide it).
_EYEBROW_BY_CATEGORY = {
    "structure": "Key idea",
    "compare": "Side by side",
    "charts": "Worked example",
    "risk-performance": "The risk picture",
    "flows": "How it flows",
    "structure-maps": "How it's structured",
    "trade-visuals": "Live example",
    "interactive": "Try it yourself",
    "reference": "For reference",
}


def _eyebrow_for(item: dict, component_id: str) -> str:
    """Resolve an item's eyebrow: explicit value wins, else a category default."""
    if "eyebrow" in item:
        return str(item.get("eyebrow") or "")
    try:
        category = get_component(component_id).category
    except Exception:
        return ""
    return _EYEBROW_BY_CATEGORY.get(category, "")


@register.simple_tag
def glossary_visuals(term) -> str:
    """Return the rendered visuals section for ``term`` (empty string when none)."""
    items = getattr(term, "visuals", None) or []
    if not isinstance(items, list):
        return ""

    blocks: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        component_id = item.get("component_id")
        spec = item.get("spec") or {}
        if not component_id or not isinstance(spec, dict):
            continue
        try:
            html = render_component(component_id, spec)
        except (ComponentNotFound, SpecValidationError, RenderError) as exc:
            log.warning("glossary visual skipped (component=%s): %s", component_id, exc)
            continue
        caption = item.get("caption")
        cap_html = (
            f'<figcaption class="tg-term__visual-cap">{escape(caption)}</figcaption>'
            if caption
            else ""
        )
        eyebrow = _eyebrow_for(item, component_id)
        eye_html = (
            f'<div class="tg-term__visual-eyebrow">{escape(eyebrow)}</div>' if eyebrow else ""
        )
        blocks.append(f'<figure class="tg-term__visual">{eye_html}{html}{cap_html}</figure>')

    if not blocks:
        return ""

    body = "\n".join(blocks)
    return mark_safe(
        f'<section class="tg-term__visuals" aria-label="Visual explanation">{body}</section>'
    )
