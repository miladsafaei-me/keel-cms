"""``./manage.py glossary_tier_sync_landings`` — de-index terms below the tier bar.

A host that declares ``noindex_tiers`` wants those term pages out of the index and out
of the sitemap. Both follow from one flag: keel-seo's gate renders a page ``index,follow``
only while an indexable ``Landing`` row exists for its path, and every sitemap bucket is
built from the same rows. So the whole job is flipping ``is_indexable`` off for the term
URLs whose stored tier is below the bar.

**One-way by design: this command only ever de-indexes.** Re-indexing a term is the host's
seeder's call, because only the host knows its other exclusion rules (merged slugs, thin
pages, editorial holds) — silently flipping a landing back on here would resurrect pages a
project deliberately buried.

Run it after ``glossary_tier_apply``. The landing model is the swappable
``KEEL_CMS_LANDING_MODEL`` (default ``keel_seo.Landing``); term URLs come from the host's
``term_url_template`` when it sets one, otherwise each term's ``get_absolute_url()``.

    ./manage.py glossary_tier_sync_landings --dry-run
    ./manage.py glossary_tier_sync_landings
"""
from __future__ import annotations

from collections import Counter

from django.apps import apps as django_apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from keel_cms import glossary_tiers


class Command(BaseCommand):
    help = "Flip is_indexable off for glossary terms whose tier is in noindex_tiers."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit-report", type=int, default=10, help="sample URLs to print")

    def handle(self, *args, **options):
        cfg = glossary_tiers.config()
        if not cfg["noindex_tiers"]:
            self.stdout.write("No noindex_tiers declared — nothing to do.")
            return

        label = getattr(settings, "KEEL_CMS_LANDING_MODEL", "keel_seo.Landing")
        try:
            Landing = django_apps.get_model(label)
        except (LookupError, ValueError) as exc:
            raise CommandError(f"Cannot resolve landing model {label!r}: {exc}")

        model = glossary_tiers.term_model(cfg)
        terms = model.objects.filter(relevancy_tier__in=sorted(cfg["noindex_tiers"]))
        by_url = {}
        for term in terms:
            url = glossary_tiers.term_url(term, cfg)
            if url:
                by_url[url] = term.relevancy_tier
        if not by_url:
            self.stdout.write("No term URLs resolved for the noindex tiers — nothing to do.")
            return

        stale = Landing.objects.filter(url__in=by_url, is_indexable=True)
        urls = sorted(stale.values_list("url", flat=True))
        tiers = Counter(by_url[u] for u in urls)
        spread = " · ".join(f"{tier} {count}" for tier, count in sorted(tiers.items()))

        for url in urls[: max(0, options["limit_report"])]:
            self.stdout.write(f"  {by_url[url]}  {url}")
        if len(urls) > options["limit_report"]:
            self.stdout.write(f"  … {len(urls) - options['limit_report']} more")

        if options["dry_run"]:
            self.stdout.write(f"[dry-run] {len(urls)} term landings would be de-indexed ({spread})")
            return

        updated = Landing.objects.filter(url__in=urls).update(is_indexable=False)
        # A bulk update fires no post_save, so keel-seo's per-path landing cache would keep
        # serving the pre-flip row (and its index,follow meta) until the TTL expired. Drop
        # the affected keys explicitly, matching keel_seo.signals' key shape.
        try:
            from django.core.cache import cache

            cache.delete_many([f"landing:{url}" for url in urls])
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"landing cache not cleared ({exc}); it expires on TTL"))
        self.stdout.write(
            self.style.SUCCESS(f"{updated} term landings de-indexed ({spread}); sitemap follows automatically.")
        )
