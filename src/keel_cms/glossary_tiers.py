"""Glossary relevancy tiers (T1-T5) — the shared priority engine for term corpora.

Every Keel glossary faces the same question: with hundreds or thousands of terms and
a finite content budget, *which term earns the next full article*. This module answers
it with three yes/no axes, combined by a fixed table into one tier:

1. **Service proximity** — does the term sit on a surface this project actually sells
   or monetizes? Business-specific by definition, so the host declares its own answer:
   a set of categories/facets that are service-adjacent, a judged verdict per term, or
   both (see ``proximity_mode``). The engine never hardcodes a vertical.
2. **Search demand** — would a real person type this term into a search engine? Judged
   per term as a band (``high`` / ``medium`` / ``low`` / ``none``) and read from the
   verdict store. No keyword tool is involved: the judgement is an LLM estimate, made
   once per term and written to a reviewable JSON file that lives in the host repo.
3. **Hub value** — how many other terms name this one as a prerequisite (in-degree in
   the related-terms graph). A high-in-degree term is load-bearing: expanding it lifts
   every page that links to it, so this axis only ever promotes, never buries.

| Service proximity | Search demand | Hub value | Tier |
|---|---|---|---|
| yes | yes | yes | T1 |
| yes | yes | no  | T2 |
| no  | yes | yes | T2 |
| yes | no  | yes | T3 |
| yes | no  | no  | T3 |
| no  | yes | no  | T3 |
| no  | no  | yes | T4 |
| no  | no  | no  | T5 |

T1 is the production queue; T4-T5 are merge-into-a-neighbour candidates rather than
standalone articles.

The module is model-agnostic: the host names its term model and maps its field names
through ``KEEL_CMS['glossary_tiers']``, so a keel-cms ``Tag(is_term=True)`` corpus and a
forked local model (``core.PropTerm``) rank identically. Importing this module pulls in
no Django models — every DB reach happens inside a function call.

Host configuration (all keys optional; defaults target ``keel_cms.Tag``)::

    KEEL_CMS = {
        "glossary_tiers": {
            "term_model": "core.PropTerm",
            "field_map": {"name": "term", "category": "parent_category"},
            "queryset_filter": {"is_term": True},
            "service_profile": "What this project sells, in prose, for the judge.",
            "service_categories": ["Payouts, Pricing & Math"],
            "service_facets": ["payout"],
            "proximity_mode": "hybrid",          # categories | judged | hybrid
            "volume_true_bands": ["high", "medium"],
            "hub_threshold": "auto",             # or an int
            "verdicts_path": BASE_DIR / "data" / "glossary-tier-verdicts.json",
        },
    }
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

VERDICTS_SCHEMA = "keel-cms/glossary-tier-verdicts@1"

VOLUME_BANDS = ("high", "medium", "low", "none")

TIER_TABLE = {
    (True, True, True): "T1",
    (True, True, False): "T2",
    (False, True, True): "T2",
    (True, False, True): "T3",
    (True, False, False): "T3",
    (False, True, False): "T3",
    (False, False, True): "T4",
    (False, False, False): "T5",
}

TIER_ORDER = {"T1": 0, "T2": 1, "T3": 2, "T4": 3, "T5": 4}

DEFAULT_FIELD_MAP = {
    "slug": "slug",
    "name": "name",
    "category": "parent_category",
    "child_category": "child_category",
    "facets": "facets",
    "aka": "aka",
    "summary": "one_line_definition",
    "related": "related_terms",
}

DEFAULTS = {
    "term_model": "keel_cms.Tag",
    "field_map": {},
    "queryset_filter": {"is_term": True},
    "service_profile": "",
    "service_categories": [],
    "service_facets": [],
    "service_slugs": [],
    "proximity_mode": "hybrid",
    "volume_true_bands": ["high", "medium"],
    "hub_threshold": "auto",
    "verdicts_path": "",
    "noindex_tiers": [],
    "require_verdict_on_save": False,
    "term_url_template": "",
}


def config() -> dict:
    """The resolved ``KEEL_CMS['glossary_tiers']`` block, with defaults filled in."""
    try:
        from django.conf import settings

        raw = (getattr(settings, "KEEL_CMS", {}) or {}).get("glossary_tiers", {}) or {}
    except Exception:
        raw = {}
    cfg = dict(DEFAULTS)
    cfg.update({k: v for k, v in raw.items() if v is not None})
    field_map = dict(DEFAULT_FIELD_MAP)
    field_map.update(cfg.get("field_map") or {})
    cfg["field_map"] = field_map
    cfg["service_categories"] = {str(c).strip() for c in cfg["service_categories"] if str(c).strip()}
    cfg["service_facets"] = {str(f).strip().lower() for f in cfg["service_facets"] if str(f).strip()}
    cfg["service_slugs"] = {str(s).strip() for s in cfg["service_slugs"] if str(s).strip()}
    cfg["volume_true_bands"] = {str(b).strip().lower() for b in cfg["volume_true_bands"]}
    cfg["noindex_tiers"] = {str(t).strip().upper() for t in cfg["noindex_tiers"] if str(t).strip()}
    mode = str(cfg.get("proximity_mode") or "hybrid").strip().lower()
    cfg["proximity_mode"] = mode if mode in {"categories", "judged", "hybrid"} else "hybrid"
    return cfg


def verdicts_path(cfg: dict | None = None) -> Path:
    """Where the judged verdicts live. Falls back to ``<cwd>/glossary-tier-verdicts.json``."""
    cfg = cfg or config()
    raw = cfg.get("verdicts_path") or ""
    if raw:
        return Path(raw)
    return Path("glossary-tier-verdicts.json")


def load_verdicts(path: Path | str | None = None, cfg: dict | None = None) -> dict:
    """Read the verdict store: ``{slug: {search_volume, service_proximity, ...}}``."""
    p = Path(path) if path else verdicts_path(cfg)
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    verdicts = data.get("verdicts") if isinstance(data, dict) else None
    return verdicts if isinstance(verdicts, dict) else {}


def save_verdicts(verdicts: dict, path: Path | str | None = None, cfg: dict | None = None,
                  project: str = "") -> Path:
    """Write the verdict store back, sorted by slug so the diff stays reviewable."""
    p = Path(path) if path else verdicts_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": VERDICTS_SCHEMA,
        "project": project,
        "count": len(verdicts),
        "verdicts": {k: verdicts[k] for k in sorted(verdicts)},
    }
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def _get(obj: Any, field: str, default: Any = "") -> Any:
    value = getattr(obj, field, None)
    return default if value is None else value


def term_model(cfg: dict | None = None):
    """Resolve the host's term model from its dotted label."""
    from django.apps import apps as django_apps

    cfg = cfg or config()
    return django_apps.get_model(cfg["term_model"])


def term_rows(cfg: dict | None = None) -> list[dict]:
    """Every term as a plain dict, with its related-terms in-degree already counted."""
    cfg = cfg or config()
    fm = cfg["field_map"]
    model = term_model(cfg)
    qs = model.objects.all()
    flt = cfg.get("queryset_filter") or {}
    valid_filter = {k: v for k, v in flt.items() if _has_field(model, k.split("__")[0])}
    if valid_filter:
        qs = qs.filter(**valid_filter)
    related_field = fm["related"] if _has_field(model, fm["related"]) else ""
    if related_field:
        qs = qs.prefetch_related(related_field)

    terms = list(qs)
    indegree: Counter = Counter()
    if related_field:
        for t in terms:
            for other in getattr(t, related_field).all():
                indegree[other.pk] += 1

    rows = []
    for t in terms:
        rows.append(
            {
                "pk": t.pk,
                "slug": str(_get(t, fm["slug"])),
                "name": str(_get(t, fm["name"])),
                "category": str(_get(t, fm["category"])).strip(),
                "child_category": str(_get(t, fm["child_category"])).strip(),
                "facets": list(_get(t, fm["facets"], []) or []),
                "aka": list(_get(t, fm["aka"], []) or []),
                "summary": str(_get(t, fm["summary"])).strip(),
                "indegree": indegree.get(t.pk, 0),
            }
        )
    rows.sort(key=lambda r: r["name"].lower())
    return rows


def _has_field(model, name: str) -> bool:
    try:
        model._meta.get_field(name)
        return True
    except Exception:
        return False


def hub_threshold(rows: Iterable[dict], cfg: dict | None = None) -> int:
    """The in-degree at which a term counts as a hub.

    ``"auto"`` (the default) uses the median in-degree across terms that are cited at
    least once, floored at 2 — a corpus-relative bar, so a sparsely-linked corpus does
    not end up with zero hubs and a densely-linked one does not call everything a hub.
    """
    cfg = cfg or config()
    raw = cfg.get("hub_threshold", "auto")
    if isinstance(raw, int) and not isinstance(raw, bool):
        return max(1, raw)
    cited = sorted(r["indegree"] for r in rows if r["indegree"] > 0)
    if not cited:
        return 1
    mid = len(cited) // 2
    median = cited[mid] if len(cited) % 2 else (cited[mid - 1] + cited[mid]) / 2
    return max(2, int(round(median)))


def service_proximity(row: dict, verdict: dict, cfg: dict) -> bool:
    """Axis 1 — is this term close to what the project sells?

    ``categories``: the host's declared category/facet/slug lists decide, alone.
    ``judged``: the per-term verdict decides, alone.
    ``hybrid`` (default): a declared match wins outright; anything it does not cover
    falls through to the judged verdict, so a host gets a deterministic core plus
    judged coverage of the long tail.
    """
    declared = (
        row["category"] in cfg["service_categories"]
        or row["slug"] in cfg["service_slugs"]
        or bool({str(f).strip().lower() for f in row["facets"]} & cfg["service_facets"])
    )
    judged = bool(verdict.get("service_proximity"))
    mode = cfg["proximity_mode"]
    if mode == "categories":
        return declared
    if mode == "judged":
        return judged
    return declared or judged


def search_demand(verdict: dict, cfg: dict) -> bool:
    """Axis 2 — does the term carry real "what is X" search demand (judged band)."""
    band = str(verdict.get("search_volume") or "").strip().lower()
    return band in cfg["volume_true_bands"]


def rank(rows: Iterable[dict], verdicts: dict | None = None, cfg: dict | None = None) -> list[dict]:
    """Attach the three axes and the tier to every row; hardest-working first."""
    cfg = cfg or config()
    rows = list(rows)
    verdicts = verdicts or {}
    threshold = hub_threshold(rows, cfg)

    ranked = []
    for row in rows:
        verdict = verdicts.get(row["slug"]) or {}
        proximity = service_proximity(row, verdict, cfg)
        demand = search_demand(verdict, cfg)
        hub = row["indegree"] >= threshold
        ranked.append(
            {
                **row,
                "service_proximity": proximity,
                "search_demand": demand,
                "search_volume": str(verdict.get("search_volume") or "").strip().lower(),
                "hub_value": hub,
                "hub_threshold": threshold,
                "judged": bool(verdict),
                "tier": TIER_TABLE[(proximity, demand, hub)],
            }
        )
    ranked.sort(key=lambda r: (TIER_ORDER[r["tier"]], -r["indegree"], r["name"].lower()))
    return ranked


def distribution(ranked: Iterable[dict]) -> dict:
    """``{"T1": n, ... "T5": n}`` with every tier present, even at zero."""
    counts = Counter(r["tier"] for r in ranked)
    return {tier: counts.get(tier, 0) for tier in TIER_ORDER}


def unjudged(ranked: Iterable[dict]) -> list[dict]:
    """Terms with no verdict yet — the export queue."""
    return [r for r in ranked if not r["judged"]]


class TierNotJudged(Exception):
    """A term reached ``save()`` with no tier verdict, under a host that requires one.

    Raised only when ``require_verdict_on_save`` is on. The message carries the exact
    commands that resolve it, because the caller is usually an authoring pipeline that
    has no other way to learn what it is missing.
    """


def tier_for_term(term: Any, cfg: dict | None = None, verdicts: dict | None = None) -> str:
    """The tier a single term object would get right now, judged verdict included.

    Hub value is read from the term's own related-terms edges, so an unsaved term (which
    has none yet) is simply not a hub until ``glossary_tier_apply`` recomputes the corpus.
    """
    cfg = cfg or config()
    fm = cfg["field_map"]
    verdicts = load_verdicts(cfg=cfg) if verdicts is None else verdicts
    slug = str(_get(term, fm["slug"]))
    verdict = verdicts.get(slug) or {}
    row = {
        "slug": slug,
        "category": str(_get(term, fm["category"])).strip(),
        "facets": list(_get(term, fm["facets"], []) or []),
        "indegree": _indegree_of(term, fm["related"]),
    }
    proximity = service_proximity(row, verdict, cfg)
    demand = search_demand(verdict, cfg)
    hub = row["indegree"] >= _stored_hub_threshold(cfg)
    return TIER_TABLE[(proximity, demand, hub)]


def _indegree_of(term: Any, related_field: str) -> int:
    """Incoming related-terms edges for one term; 0 for an unsaved row or a model without the M2M."""
    if not getattr(term, "pk", None):
        return 0
    incoming = getattr(term, "related_from", None)
    if incoming is None:
        return 0
    try:
        return incoming.count()
    except Exception:
        return 0


_HUB_CACHE: dict[str, int] = {}


def reset_caches() -> None:
    """Drop the memoized hub threshold. Call after a corpus-wide recompute."""
    _HUB_CACHE.clear()


def _stored_hub_threshold(cfg: dict) -> int:
    """Hub bar for a single-term decision: the configured int, or the corpus median.

    The ``"auto"`` median costs a full corpus scan, and this runs on every term save, so
    it is memoized per process. A stale bar can only mis-stamp axis 3 on a single row
    between corpus recomputes, and ``glossary_tier_apply`` (which resets the cache) is
    what restates the whole corpus anyway.
    """
    raw = cfg.get("hub_threshold", "auto")
    if isinstance(raw, int) and not isinstance(raw, bool):
        return max(1, raw)
    key = str(cfg.get("term_model"))
    if key not in _HUB_CACHE:
        try:
            _HUB_CACHE[key] = hub_threshold(term_rows(cfg), cfg)
        except Exception:
            return 2
    return _HUB_CACHE[key]


def stamp_tier(term: Any, is_new: bool = False, cfg: dict | None = None) -> str:
    """Write the current tier onto ``term.relevancy_tier`` before it is saved.

    With ``require_verdict_on_save`` on, an unjudged NEW term raises ``TierNotJudged``
    instead of being saved unranked — the corpus stays fully tiered by construction.
    An already-saved term is never blocked: re-saving an old row must not fail because
    the judging pass has not reached it yet.
    """
    cfg = cfg or config()
    if not hasattr(term, "relevancy_tier"):
        return ""
    fm = cfg["field_map"]
    slug = str(_get(term, fm["slug"]))
    verdicts = load_verdicts(cfg=cfg)
    if slug not in verdicts:
        if is_new and cfg.get("require_verdict_on_save"):
            raise TierNotJudged(
                f"Glossary term '{slug}' has no tier verdict, and this project requires one "
                f"before a new term is saved. Judge it first:\n"
                f"  ./manage.py glossary_tier_export --candidates <file.json> --out <dir>\n"
                f"  (hand the batch to a Sonnet subagent, then)\n"
                f"  ./manage.py glossary_tier_ingest <answers.json> --allow-new"
            )
        if term.relevancy_tier:
            return term.relevancy_tier
    tier = tier_for_term(term, cfg, verdicts)
    term.relevancy_tier = tier
    return tier


def is_indexable_tier(tier: str, cfg: dict | None = None) -> bool:
    """False when the host has declared this tier noindex. Unjudged (blank) stays indexable."""
    cfg = cfg or config()
    return str(tier or "").strip().upper() not in cfg["noindex_tiers"]


def term_url(term: Any, cfg: dict | None = None) -> str:
    """Public URL of a term: the host's ``term_url_template`` if set, else the model's own.

    A host whose glossary route is not the one ``get_absolute_url()`` reverses (terms served
    from a shared tag route, a second glossary, a non-keel-cms model) sets
    ``term_url_template`` to something like ``"/tag/{slug}"`` and the whole tier tooling
    resolves URLs correctly without touching the model.
    """
    cfg = cfg or config()
    template = str(cfg.get("term_url_template") or "").strip()
    if template:
        return template.format(slug=_get(term, cfg["field_map"]["slug"]))
    getter = getattr(term, "get_absolute_url", None)
    return getter() if callable(getter) else ""
