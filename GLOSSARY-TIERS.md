# Glossary relevancy tiers (T1–T5)

Every Keel glossary hits the same wall: hundreds or thousands of terms, a finite content
budget, and no defensible answer to *which term earns the next full article*. This is the
shared answer — three yes/no axes, one fixed combination table, five tiers. It ships in
`keel_cms.glossary_tiers` plus three management commands, and it is corpus-agnostic: a
keel-cms `Tag(is_term=True)` glossary and a host's own forked term model rank identically.

Originally built for the SignalBots glossary (347 terms, 2026-08-19) and generalised into
the package on 2026-08-20 so every consumer shares one framework instead of a fork.

## The three axes

**1 · Service proximity — is the term close to what *this* project sells?**
Business-specific by definition, so the host declares its own answer. Three modes:

| `proximity_mode` | Axis 1 is decided by |
|---|---|
| `categories` | the host's declared `service_categories` / `service_facets` / `service_slugs`, alone |
| `judged` | the per-term verdict, alone — for corpora whose categories are too broad to stand in for "close to what we sell" |
| `hybrid` *(default)* | a declared match wins outright; everything it does not cover falls through to the judged verdict |

The host also writes a `service_profile`: a short prose statement of what the project
sells and what counts as adjacent. It is the only thing the judge sees about the business,
so it carries the whole axis — write it as "service-proximate when …, NOT when …".

**2 · Search demand — would a real person type this term into a search engine?**
Judged per term as a band: `high` / `medium` / `low` / `none`. By default `high` + `medium`
count as ✓ (`volume_true_bands`). **No keyword tool is involved.** The judgement is an LLM
estimate of the *term string as a query*, made once per term, written to a JSON file in the
host repo, and reviewable in a diff — which is reproducible, costs nothing per re-run, and
does not tie the framework to a paid API. A category-level proxy (e.g. "not Advanced")
was the previous stand-in and is strictly worse: it mislabels well-known vocabulary that
happens to be tagged advanced.

**3 · Hub value — how load-bearing is the term inside the corpus?**
In-degree in the related-terms graph: how many other terms name this one. This axis only
ever promotes — a term many pages depend on lifts the whole neighbourhood when it is
expanded. `hub_threshold: "auto"` (default) uses the median in-degree among cited terms,
floored at 2, so the bar is relative to how densely the corpus is wired; an int pins it.

## The tier table

| Service proximity | Search demand | Hub value | Tier |
|---|---|---|---|
| ✓ | ✓ | ✓ | **T1** |
| ✓ | ✓ | ✗ | **T2** |
| ✗ | ✓ | ✓ | **T2** |
| ✓ | ✗ | ✓ | **T3** |
| ✓ | ✗ | ✗ | **T3** |
| ✗ | ✓ | ✗ | **T3** |
| ✗ | ✗ | ✓ | **T4** |
| ✗ | ✗ | ✗ | **T5** |

**T1** is the production queue — expand these first, in in-degree order. **T2** is next up.
**T3** is the long tail worth keeping current. **T4–T5** are merge-into-a-neighbour
candidates (fold into a related term's `aka` / a section of a bigger page) rather than
standalone articles.

## Host configuration

```python
KEEL_CMS = {
    "glossary_tiers": {
        # Which model holds the terms (default: keel_cms.Tag) and how its fields map.
        "term_model": "core.PropTerm",
        "field_map": {"name": "term", "summary": "tldr"},
        "queryset_filter": {"is_term": True},   # dropped silently if the field is absent

        # Axis 1.
        "service_profile": "What this project sells, and what counts as adjacent.",
        "service_categories": ["Payouts and Profit Splits"],
        "service_facets": [],
        "service_slugs": [],
        "proximity_mode": "hybrid",             # categories | judged | hybrid

        # Axis 2.
        "volume_true_bands": ["high", "medium"],

        # Axis 3.
        "hub_threshold": "auto",                # or an int

        # Where the judged verdicts live (git-tracked, reviewable).
        "verdicts_path": BASE_DIR / "data" / "glossary-tier-verdicts.json",
    },
}
```

`field_map` keys: `slug`, `name`, `category`, `child_category`, `facets`, `aka`, `summary`,
`related`. Defaults match `keel_cms.Tag`; override only what differs.

## The judging loop

The judgement is made by an agent reading a batch file — no API key, no keyword tool, no
network call from the app.

```bash
./manage.py glossary_tier_export --out /app/backend/.tier-batches --batch-size 120
```

Writes `batch-NNN.json`, each carrying the rendered brief (rubric + this project's service
profile) and up to 120 terms with name, aka, category and summary. Only unjudged terms are
exported unless `--all` is passed. `--brief` prints the brief alone.

Hand each batch to one Sonnet subagent — that is the intended model tier for this job; it
is a bounded classification over a supplied list, and the framework is deliberately cheap
to re-run. Each agent answers with:

```json
{"verdicts": [{"slug": "…", "search_volume": "high|medium|low|none",
               "service_proximity": true, "note": "…"}]}
```

```bash
./manage.py glossary_tier_ingest /app/backend/.tier-batches/answers-*.json
```

Merges the answers into `verdicts_path`. Defensive by design: a verdict is accepted only
when its slug is a real term and its band is one of the four, so a malformed agent answer
is reported and skipped rather than quietly corrupting the tiers. `--dry-run` reports
without writing.

```bash
./manage.py glossary_tiers                  # distribution table
./manage.py glossary_tiers --by-category    # tier spread per category
./manage.py glossary_tiers --tier T1 --limit 40
./manage.py glossary_tiers --json | --csv tiers.csv
```

Nothing is cached: re-run after new terms, rewired related-terms edges, or a fresh judging
pass. New terms simply show as unjudged (they land in T3–T5 until judged), so the loop is
incremental — export only the new ones, judge, ingest.

## What re-judging costs

The verdict store is per-term and permanent until re-judged. Re-run the loop when the
service profile changes (the business pivots, a new money surface appears) — that
invalidates axis 1 for the whole corpus, so re-export with `--all`. Adding terms never
invalidates existing verdicts.
