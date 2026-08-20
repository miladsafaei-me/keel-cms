"""``./manage.py glossary_tier_apply`` — write the computed tiers onto the term rows.

The ranking itself is always computed live (`glossary_tiers`), but views, sitemaps and
the noindex gate need the tier as a plain column they can filter on. This command is the
one writer of that column: it recomputes the whole corpus and bulk-updates every row whose
stored tier drifted from the computed one.

Run it after ingesting verdicts, after a batch of new terms, and after any related-terms
rewiring — axis 3 moves for the whole corpus when the citation graph changes.

    ./manage.py glossary_tier_apply
    ./manage.py glossary_tier_apply --dry-run
"""
from __future__ import annotations

from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from keel_cms import glossary_tiers


class Command(BaseCommand):
    help = "Recompute T1-T5 tiers and store them on the term rows (relevancy_tier)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        cfg = glossary_tiers.config()
        model = glossary_tiers.term_model(cfg)
        if not hasattr(model, "relevancy_tier"):
            raise CommandError(
                f"{cfg['term_model']} has no 'relevancy_tier' field — add one (CharField, "
                "max_length=2, blank=True, db_index=True) before applying tiers."
            )

        verdicts = glossary_tiers.load_verdicts(cfg=cfg)
        ranked = glossary_tiers.rank(glossary_tiers.term_rows(cfg), verdicts, cfg)
        by_pk = {r["pk"]: r["tier"] for r in ranked}

        changed = []
        moves: Counter = Counter()
        for term in model.objects.filter(pk__in=by_pk).only("pk", "relevancy_tier"):
            wanted = by_pk[term.pk]
            if (term.relevancy_tier or "") != wanted:
                moves[f"{term.relevancy_tier or '-'} -> {wanted}"] += 1
                term.relevancy_tier = wanted
                changed.append(term)

        spread = glossary_tiers.distribution(ranked)
        summary = " · ".join(f"{tier} {spread[tier]}" for tier in spread)

        if options["dry_run"]:
            self.stdout.write(f"[dry-run] {len(changed)} of {len(ranked)} rows would change")
        else:
            if changed:
                model.objects.bulk_update(changed, ["relevancy_tier"], batch_size=500)
            glossary_tiers.reset_caches()
            self.stdout.write(self.style.SUCCESS(f"{len(changed)} of {len(ranked)} rows updated"))

        for move, count in moves.most_common(10):
            self.stdout.write(f"  {move}: {count}")
        self.stdout.write(summary)
