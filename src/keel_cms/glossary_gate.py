"""
Niche-purity gate + score for glossary terms — the schema-driven admission rule.

The host declares, per ``term_type``, which fields are *required* and which are
*optional* (``KEEL_CMS['glossary_field_schema']``). This module turns that config
into two mechanical checks the host (or keel-content authoring) runs over a term:

* **gate** — a term is admitted only when its ``term_type`` is set (and, if the
  host constrains the set, allowed) and every required field for that type is
  filled. A missing required field is the rejection signal.
* **score** — the number of filled optional fields (a purity/relevance signal:
  the more binary-specific optional fields a term carries, the more central to the
  niche it is). Used for build priority, internal-link weight, featured placement.

A field name is either a first-class attribute on the term (``"what_is"``,
``"formula"``, ``"risk_band"``, ``"one_line_definition"``) or a dotted ``content``
key (``"content.impact_on_expectancy"``). The functions operate on any object that
exposes those attributes plus a ``content`` dict and a ``term_type``, so they are
usable on the ORM model, an unsaved instance, or a plain dict-like row.

With no host schema declared (default), the gate passes everything and the score is
zero — the engine stays business-neutral until a consumer opts in.
"""
from __future__ import annotations

from typing import Any


def _is_filled(value: Any) -> bool:
    """True when a field carries real content (non-empty string / list / dict / not None)."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) > 0
    return True


def field_value(term: Any, field_name: str) -> Any:
    """Resolve a schema field name to its value: a ``content.<key>`` path or a plain attribute."""
    name = (field_name or "").strip()
    if not name:
        return None
    if name.startswith("content."):
        key = name[len("content.") :]
        content = getattr(term, "content", None)
        if isinstance(content, dict):
            return content.get(key)
        return None
    return getattr(term, name, None)


def _schema_for(term: Any, field_schema: dict | None) -> dict:
    """Return the {required, optional} entry for this term's type (empty when none)."""
    if field_schema is None:
        from .config import glossary_field_schema

        field_schema = glossary_field_schema()
    ttype = (getattr(term, "term_type", "") or "").strip()
    entry = (field_schema or {}).get(ttype) or {}
    return entry if isinstance(entry, dict) else {}


def missing_required_fields(term: Any, field_schema: dict | None = None) -> list[str]:
    """Required fields for the term's type that are empty (empty list -> nothing missing)."""
    required = _schema_for(term, field_schema).get("required") or []
    return [f for f in required if not _is_filled(field_value(term, f))]


def purity_score(term: Any, field_schema: dict | None = None) -> int:
    """Count of filled optional fields for the term's type (the niche-relevance signal)."""
    optional = _schema_for(term, field_schema).get("optional") or []
    return sum(1 for f in optional if _is_filled(field_value(term, f)))


def passes_gate(
    term: Any,
    field_schema: dict | None = None,
    allowed_types: list | None = None,
) -> bool:
    """
    True when the term is admissible: it has a ``term_type`` (allowed, if the host
    constrains the set) and no required field for that type is missing.
    """
    ttype = (getattr(term, "term_type", "") or "").strip()
    if allowed_types is None:
        from .config import glossary_term_types

        allowed_types = glossary_term_types()
    if allowed_types and ttype not in allowed_types:
        return False
    # With a declared schema, a type carrying required fields must be set + complete.
    schema = _schema_for(term, field_schema)
    if schema.get("required") and not ttype:
        return False
    return not missing_required_fields(term, field_schema)
