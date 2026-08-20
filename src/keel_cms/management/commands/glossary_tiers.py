"""``./manage.py glossary_tiers`` — rank the glossary by T1-T5 and report the spread.

The reporting front-end for ``keel_cms.glossary_tiers``: it joins the host's term model
with the judged verdict store, computes the three axes, and prints the tier distribution
(plus the per-tier queue when asked). Re-run it after any batch of new terms, any
related-terms rewiring, or any fresh judging pass — nothing is cached.

    ./manage.py glossary_tiers                    # distribution table
    ./manage.py glossary_tiers --by-category      # tier spread per category
    ./manage.py glossary_tiers --tier T1 --limit 40
    ./manage.py glossary_tiers --json             # machine-readable, for a report step
    ./manage.py glossary_tiers --csv tiers.csv    # one row per term
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand

from keel_cms import glossary_tiers


class Command(BaseCommand):
    help = "Rank glossary terms into T1-T5 relevancy tiers and report the distribution."

    def add_arguments(self, parser):
        parser.add_argument("--tier", default="", help="list the terms in one tier (T1..T5)")
        parser.add_argument("--limit", type=int, default=25, help="how many terms to list")
        parser.add_argument("--by-category", action="store_true", help="tier spread per category")
        parser.add_argument("--json", action="store_true", help="emit the full ranking as JSON")
        parser.add_argument("--csv", default="", help="write one row per term to this path")

    def handle(self, *args, **options):
        cfg = glossary_tiers.config()
        verdicts = glossary_tiers.load_verdicts(cfg=cfg)
        ranked = glossary_tiers.rank(glossary_tiers.term_rows(cfg), verdicts, cfg)
        spread = glossary_tiers.distribution(ranked)
        total = len(ranked)
        pending = len(glossary_tiers.unjudged(ranked))

        if options["json"]:
            self.stdout.write(json.dumps(
                {
                    "total": total,
                    "unjudged": pending,
                    "hub_threshold": ranked[0]["hub_threshold"] if ranked else 0,
                    "distribution": spread,
                    "terms": ranked,
                },
                ensure_ascii=False,
            ))
            return

        if options["csv"]:
            path = Path(options["csv"])
            path.parent.mkdir(parents=True, exist_ok=True)
            fields = ["tier", "slug", "name", "category", "service_proximity",
                      "search_volume", "search_demand", "indegree", "hub_value", "judged"]
            with path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(ranked)
            self.stdout.write(self.style.SUCCESS(f"{total} rows -> {path}"))

        if options["tier"]:
            wanted = options["tier"].upper()
            rows = [r for r in ranked if r["tier"] == wanted][: max(1, options["limit"])]
            self.stdout.write(f"{wanted} — {spread.get(wanted, 0)} terms (showing {len(rows)})")
            for r in rows:
                self.stdout.write(
                    f"  {r['name'][:52]:<54} in={r['indegree']:<3} vol={r['search_volume'] or '-':<6}"
                    f" svc={'y' if r['service_proximity'] else 'n'}  {r['category'][:28]}"
                )
            return

        self.stdout.write(f"{cfg['term_model']} — {total} terms, {pending} still unjudged")
        self.stdout.write(f"hub threshold (in-degree): {ranked[0]['hub_threshold'] if ranked else 0}")
        self.stdout.write("")
        self.stdout.write(f"{'Tier':<6}{'Terms':>8}{'Share':>9}   Axes (service / search / hub)")
        axes = {
            "T1": "yes / yes / yes",
            "T2": "yes+yes+no  or  no+yes+yes",
            "T3": "yes+no, or no+yes+no",
            "T4": "no / no / yes",
            "T5": "no / no / no",
        }
        for tier in ("T1", "T2", "T3", "T4", "T5"):
            count = spread[tier]
            share = f"{(100 * count / total):.1f}%" if total else "-"
            self.stdout.write(f"{tier:<6}{count:>8}{share:>9}   {axes[tier]}")
        self.stdout.write(f"{'total':<6}{total:>8}")

        if options["by_category"]:
            per = defaultdict(Counter)
            for r in ranked:
                per[r["category"] or "(uncategorised)"][r["tier"]] += 1
            self.stdout.write("")
            header = f"{'Category':<42}" + "".join(f"{t:>7}" for t in ("T1", "T2", "T3", "T4", "T5")) + f"{'total':>8}"
            self.stdout.write(header)
            for category in sorted(per, key=lambda c: -sum(per[c].values())):
                counts = per[category]
                row = f"{category[:40]:<42}" + "".join(f"{counts.get(t, 0):>7}" for t in ("T1", "T2", "T3", "T4", "T5"))
                self.stdout.write(row + f"{sum(counts.values()):>8}")
