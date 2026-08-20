"""``./manage.py glossary_tier_ingest`` — take the judged verdicts back into the store.

Reads one or more agent answer files (the JSON shape the export brief asks for, either
as ``{"verdicts": [...]}`` or a bare list) and merges them into the host's verdict file.
Ingestion is deterministic and defensive: a verdict is accepted only when its slug is a
real term and its band is one of high/medium/low/none. Everything else is reported and
skipped, so a malformed agent answer can never quietly corrupt the tiers.

    ./manage.py glossary_tier_ingest /tmp/tiers/answers-*.json
    ./manage.py glossary_tier_ingest answers.json --dry-run
"""
from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from keel_cms import glossary_tiers


def _iter_verdicts(payload):
    if isinstance(payload, dict):
        rows = payload.get("verdicts")
        if isinstance(rows, dict):
            for slug, entry in rows.items():
                yield {"slug": slug, **(entry if isinstance(entry, dict) else {})}
            return
        payload = rows
    if isinstance(payload, list):
        for entry in payload:
            if isinstance(entry, dict):
                yield entry


class Command(BaseCommand):
    help = "Merge judged search-demand / service-proximity verdicts into the tier verdict store."

    def add_arguments(self, parser):
        parser.add_argument("paths", nargs="+", help="agent answer files (JSON)")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--project", default="")
        parser.add_argument("--judge", default="sonnet", help="label for who made the judgement")
        parser.add_argument(
            "--allow-new",
            action="store_true",
            help="accept verdicts for slugs that are not in the corpus yet (terms judged "
                 "before they are authored, which is what the save-time gate requires)",
        )

    def handle(self, *args, **options):
        cfg = glossary_tiers.config()
        known = {r["slug"] for r in glossary_tiers.term_rows(cfg)}
        if not known:
            raise CommandError(f"No terms found in {cfg['term_model']} — check the tier config.")

        store = glossary_tiers.load_verdicts(cfg=cfg)
        today = timezone.localdate().isoformat()
        accepted = updated = 0
        unknown_slugs: list[str] = []
        bad_bands: list[str] = []

        for raw_path in options["paths"]:
            path = Path(raw_path)
            if not path.exists():
                raise CommandError(f"No such answer file: {path}")
            payload = json.loads(path.read_text(encoding="utf-8"))
            for entry in _iter_verdicts(payload):
                slug = str(entry.get("slug") or "").strip()
                band = str(entry.get("search_volume") or "").strip().lower()
                if slug not in known and not (options["allow_new"] and slug):
                    unknown_slugs.append(slug or "(blank)")
                    continue
                if band not in glossary_tiers.VOLUME_BANDS:
                    bad_bands.append(f"{slug}={band or '(blank)'}")
                    continue
                was = slug in store
                store[slug] = {
                    "search_volume": band,
                    "service_proximity": bool(entry.get("service_proximity")),
                    "note": str(entry.get("note") or "").strip()[:120],
                    "judged_by": options["judge"],
                    "judged_at": today,
                }
                accepted += 1
                updated += 1 if was else 0

        for label, items in (("unknown slug", unknown_slugs), ("invalid band", bad_bands)):
            if items:
                self.stdout.write(
                    self.style.WARNING(f"skipped {len(items)} ({label}): {', '.join(items[:8])}"
                                       + (" ..." if len(items) > 8 else ""))
                )

        if options["dry_run"]:
            self.stdout.write(f"[dry-run] would store {accepted} verdicts ({updated} overwrites)")
            return

        path = glossary_tiers.save_verdicts(store, cfg=cfg, project=options["project"])
        self.stdout.write(
            self.style.SUCCESS(
                f"{accepted} verdicts ingested ({updated} overwrites); store now holds "
                f"{len(store)} of {len(known)} terms -> {path}"
            )
        )
