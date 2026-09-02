"""``manage.py read_time_recompute`` — restate every post's stored read time.

``blog_post.read_time_minutes`` was backfilled from a counter that ran
``strip_tags`` over the rendered body. ``strip_tags`` drops the tags but keeps
what sits between them, so every in-article component that ships its data as
inline ``<script>`` — a chart's candle series, a calculator's config — was
counted as prose. Component-heavy articles ended up advertising several times
their real length, and because the stored value short-circuits the accessor,
fixing the calculation alone changes nothing on already-imported posts.

This walks both content models, recomputes from
:func:`keel_cms.models.read_time_minutes_for`, and writes back only the rows
that actually move. ``--dry-run`` reports the deltas without touching anything.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from keel_cms.models import NewsPost, Post, read_time_minutes_for

BATCH = 200


class Command(BaseCommand):
    help = "Recompute stored read_time_minutes for posts and news posts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing.",
        )
        parser.add_argument(
            "--model",
            choices=("post", "news", "all"),
            default="all",
            help="Limit the pass to one content model (default: all).",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        which = options["model"]
        targets = []
        if which in ("post", "all"):
            targets.append(("Post", Post))
        if which in ("news", "all"):
            targets.append(("NewsPost", NewsPost))

        for label, model in targets:
            pending, changed, scanned = [], 0, 0
            moves = []
            qs = model.objects.all().only("pk", "read_time_minutes",
                                          "content_rendered", "content_raw")
            for obj in qs.iterator(chunk_size=BATCH):
                scanned += 1
                fresh = read_time_minutes_for(obj.content_rendered or obj.content_raw or "")
                if fresh == obj.read_time_minutes:
                    continue
                moves.append((obj.read_time_minutes - fresh, str(obj.pk),
                              obj.read_time_minutes, fresh))
                changed += 1
                if dry:
                    continue
                obj.read_time_minutes = fresh
                pending.append(obj)
                if len(pending) >= BATCH:
                    model.objects.bulk_update(pending, ["read_time_minutes"])
                    pending = []
            if pending:
                model.objects.bulk_update(pending, ["read_time_minutes"])

            verb = "would change" if dry else "changed"
            self.stdout.write(f"{label}: scanned {scanned}, {verb} {changed}")
            moves.sort(reverse=True)
            for delta, pk, was, now in moves[:8]:
                self.stdout.write(f"    {-delta:>+4} min  {pk}  {was} -> {now}")
