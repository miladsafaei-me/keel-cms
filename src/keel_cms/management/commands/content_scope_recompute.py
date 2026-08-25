"""``./manage.py content_scope_recompute`` — re-derive scope levels after a widening.

The point of recording L4-L5 instead of discarding them is that a later scope
expansion promotes from that shelf. This is the command that performs the promotion,
and it is deterministic because the rows carry the *answers* (``scope_axes``), not
just the computed level.

The usual sequence when a definition moves — a product category is added, a market
opens, a partner is signed:

1. Flip the axis whose definition changed, for the rows it can touch::

       ./manage.py content_scope_recompute --set-axis service=true \\
           --where-axis scope=false --match "copy trading" --ruleset 2026-11-03

2. Re-derive every level from the stored answers::

       ./manage.py content_scope_recompute --ruleset 2026-11-03

Both steps print what they would do and change nothing until ``--apply``. Rows with
no stored answers are reported and skipped — they were graded before the answers were
recorded and still need a real re-judge; this command never invents an axis answer.
"""
from __future__ import annotations

from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from keel_cms import scope_levels
from keel_cms.models import ContentPlan


def _parse_axis_assignment(raw):
    """``name=true`` / ``name=false`` -> ``(name, bool)``."""
    if "=" not in raw:
        raise CommandError(f"expected axis=true|false, got {raw!r}")
    name, _, value = raw.partition("=")
    name = name.strip()
    value = value.strip().lower()
    if not name:
        raise CommandError(f"empty axis name in {raw!r}")
    if value in ("true", "yes", "1"):
        return name, True
    if value in ("false", "no", "0"):
        return name, False
    raise CommandError(f"expected true|false for axis {name!r}, got {value!r}")


class Command(BaseCommand):
    help = ("Re-derive ContentPlan.scope_relevance from the stored scope_axes, and "
            "optionally flip one axis first (a scope widening).")

    def add_arguments(self, parser):
        parser.add_argument(
            "--set-axis", metavar="NAME=BOOL",
            help="Flip this axis on every matched row before recomputing "
                 "(e.g. service=true). Omit to recompute from the answers as stored.")
        parser.add_argument(
            "--where-axis", metavar="NAME=BOOL", action="append", default=[],
            help="Only touch rows whose stored answer for NAME is BOOL. Repeatable.")
        parser.add_argument(
            "--match", default="",
            help="Only touch rows whose title or slug contains this text "
                 "(case-insensitive).")
        parser.add_argument(
            "--ruleset", default="",
            help="Stamp this ruleset identifier on every row the run writes. Required "
                 "with --set-axis: a changed answer belongs to a changed ruleset.")
        parser.add_argument(
            "--stale-only", action="store_true",
            help="Only touch rows whose stored ruleset differs from --ruleset.")
        parser.add_argument("--apply", action="store_true",
                            help="Write the changes. Without it, this is a dry run.")

    def handle(self, *args, **options):
        set_axis = options["set_axis"]
        ruleset = options["ruleset"].strip()
        if set_axis and not ruleset:
            raise CommandError(
                "--set-axis changes an answer, so it needs --ruleset to record which "
                "scope definitions produced it.")
        if options["stale_only"] and not ruleset:
            raise CommandError("--stale-only needs --ruleset to compare against.")

        axis_name = axis_value = None
        if set_axis:
            axis_name, axis_value = _parse_axis_assignment(set_axis)
        filters = [_parse_axis_assignment(w) for w in options["where_axis"]]

        qs = ContentPlan.objects.all()
        if options["match"]:
            m = options["match"]
            qs = qs.filter(Q(title__icontains=m) | Q(slug__icontains=m))
        if options["stale_only"]:
            qs = qs.exclude(scope_ruleset=ruleset)

        stats = Counter()
        moves = Counter()
        changed = []
        ungraded = []

        for row in qs.iterator():
            axes = row.scope_axes
            if not isinstance(axes, dict) or not axes:
                stats["no_stored_axes"] += 1
                if len(ungraded) < 10:
                    ungraded.append(row.slug or row.title)
                continue
            if any(bool(axes.get(n)) is not v for n, v in filters):
                stats["filtered_out"] += 1
                continue

            new_axes = dict(axes)
            if axis_name is not None:
                new_axes[axis_name] = axis_value
            try:
                level = scope_levels.derive_scope_level(new_axes)
            except scope_levels.ScopeAxesError as exc:
                stats["unusable_axes"] += 1
                self.stderr.write(f"  {row.slug or row.title}: {exc}")
                continue

            stats["considered"] += 1
            dirty = (new_axes != axes) or (level != row.scope_relevance)
            if ruleset and row.scope_ruleset != ruleset:
                dirty = True
            if not dirty:
                stats["unchanged"] += 1
                continue

            if level != row.scope_relevance:
                moves[(row.scope_relevance, level)] += 1
            row.scope_axes = new_axes
            row.scope_relevance = level
            if ruleset:
                row.scope_ruleset = ruleset
            changed.append(row)

        if options["apply"] and changed:
            ContentPlan.objects.bulk_update(
                changed, ["scope_axes", "scope_relevance", "scope_ruleset"], batch_size=500)

        verb = "Updated" if options["apply"] else "Would update"
        self.stdout.write(f"{verb} {len(changed)} of {stats['considered']} row(s) with stored axes.")
        for (old, new), n in sorted(moves.items(), key=lambda kv: (-kv[1], str(kv[0]))):
            arrow = "promoted" if new is not None and old is not None and new < old else "moved"
            self.stdout.write(f"  L{old} -> L{new}: {n} row(s) ({arrow})")
        if stats["filtered_out"]:
            self.stdout.write(f"  skipped by --where-axis: {stats['filtered_out']}")
        if stats["unusable_axes"]:
            self.stdout.write(f"  skipped, axes unusable: {stats['unusable_axes']}")
        if stats["no_stored_axes"]:
            sample = ", ".join(ungraded)
            more = " …" if stats["no_stored_axes"] > len(ungraded) else ""
            self.stdout.write(
                f"  {stats['no_stored_axes']} row(s) have no stored axes and were skipped — "
                f"they need a real re-judge, not a recompute: {sample}{more}")
        if not options["apply"]:
            self.stdout.write("Dry run — re-run with --apply to write.")
