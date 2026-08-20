"""``./manage.py glossary_tier_export`` — batch the unjudged glossary terms for judging.

Axis 2 (search demand) and, where the host asks for it, axis 1 (service proximity) are
*judgements*, not database facts. This command writes them out as batch files an LLM
agent reads: each batch carries the project's own service profile, the band rubric, and
a list of terms with just enough context to judge them (name, aka, category, one-line
summary). The agent answers with one JSON verdict per term; ``glossary_tier_ingest``
takes those answers back.

No keyword tool and no LLM API key is involved — the judging step is an agent reading a
batch file, which keeps the whole loop reproducible and reviewable in git.

    ./manage.py glossary_tier_export --out /tmp/tiers --batch-size 100
    ./manage.py glossary_tier_export --out /tmp/tiers --all      # re-judge everything
    ./manage.py glossary_tier_export --brief                     # print the brief only
"""
from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from keel_cms import glossary_tiers

BRIEF = """You are judging glossary terms for the {project} glossary.

For every term in `terms`, return two judgements.

1. search_volume — how much standalone search demand the exact term name carries as a
   query someone types into Google (think "what is <term>", "<term> meaning"). Judge the
   STRING as a query, not how important the concept is:
     high   — widely-known industry vocabulary, a query many people type every month.
     medium — real but niche vocabulary; practitioners search it, the general public does not.
     low    — rarely searched on its own; mostly read inside other content.
     none   — internal jargon, a coined phrase, or a long descriptive label nobody types.
   Long multi-word descriptive phrases are almost always `low` or `none`. Brand-flavoured
   phrasings are `low` unless the brand itself is a household name in this niche.

2. service_proximity — true when the term sits on or directly next to what this project
   sells or monetizes, judged against the service profile below; false when it is general
   background knowledge for the niche.

SERVICE PROFILE — {project}:
{service_profile}

Return JSON only, in exactly this shape, one entry per term, same slugs, nothing else:

{{"verdicts": [
  {{"slug": "<slug>", "search_volume": "high|medium|low|none", "service_proximity": true,
    "note": "<= 12 words"}}
]}}
"""


def _candidate_rows(path: Path) -> list[dict]:
    """Normalise a candidate file (terms that are not in the corpus yet) to export rows."""
    if not path.exists():
        raise CommandError(f"No such candidates file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("terms") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise CommandError("Candidates file must be a list of terms, or {\"terms\": [...]}.")
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        slug = str(item.get("slug") or "").strip()
        name = str(item.get("name") or item.get("term") or "").strip()
        if not slug or not name:
            raise CommandError(f"Every candidate needs a slug and a name; got {item!r}")
        rows.append(
            {
                "slug": slug,
                "name": name,
                "aka": list(item.get("aka") or []),
                "category": str(item.get("category") or "").strip(),
                "summary": str(item.get("summary") or "").strip(),
            }
        )
    return rows


class Command(BaseCommand):
    help = "Export unjudged glossary terms as agent-ready judging batches."

    def add_arguments(self, parser):
        parser.add_argument("--out", default="", help="directory to write batch files into")
        parser.add_argument("--batch-size", type=int, default=100)
        parser.add_argument("--limit", type=int, default=0, help="cap the number of terms exported")
        parser.add_argument("--all", action="store_true", help="export every term, judged or not")
        parser.add_argument("--project", default="", help="project label written into each batch")
        parser.add_argument("--brief", action="store_true", help="print the judging brief and exit")
        parser.add_argument(
            "--candidates",
            default="",
            help="JSON file of terms that do not exist yet ([{slug, name, category, summary}] "
                 "or {\"terms\": [...]}); batches those instead of reading the corpus, so a "
                 "new term can be judged BEFORE it is authored and saved",
        )

    def handle(self, *args, **options):
        cfg = glossary_tiers.config()
        project = options["project"] or cfg.get("project_name") or "this project"
        brief = BRIEF.format(project=project, service_profile=cfg["service_profile"] or "(not declared)")

        if options["brief"]:
            self.stdout.write(brief)
            return

        if options["candidates"]:
            pending = _candidate_rows(Path(options["candidates"]))
        else:
            verdicts = glossary_tiers.load_verdicts(cfg=cfg)
            ranked = glossary_tiers.rank(glossary_tiers.term_rows(cfg), verdicts, cfg)
            pending = ranked if options["all"] else glossary_tiers.unjudged(ranked)
        pending.sort(key=lambda r: r["name"].lower())
        if options["limit"]:
            pending = pending[: options["limit"]]

        if not pending:
            self.stdout.write(self.style.SUCCESS("Nothing to judge — every term has a verdict."))
            return

        out_dir = Path(options["out"] or ".")
        out_dir.mkdir(parents=True, exist_ok=True)
        size = max(1, options["batch_size"])
        batches = [pending[i : i + size] for i in range(0, len(pending), size)]

        for index, batch in enumerate(batches, start=1):
            payload = {
                "schema": "keel-cms/glossary-tier-batch@1",
                "project": project,
                "batch": index,
                "of": len(batches),
                "brief": brief,
                "terms": [
                    {
                        "slug": r["slug"],
                        "name": r["name"],
                        "aka": r["aka"],
                        "category": r["category"],
                        "summary": r["summary"][:200],
                    }
                    for r in batch
                ],
            }
            path = out_dir / f"batch-{index:03d}.json"
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.stdout.write(f"{path}  ({len(batch)} terms)")

        self.stdout.write(
            self.style.SUCCESS(f"{len(pending)} terms across {len(batches)} batches -> {out_dir}")
        )
