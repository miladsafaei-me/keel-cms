"""Add ``Post.images_ready`` + ``Post.pending_visuals``.

The content pipeline no longer produces the bespoke hero and the in-article NB2
photoreal images inline — they are made by a standalone pass after
``content_import`` (see keel-content's ``generate_post_images``). These two fields
carry the handoff: ``images_ready`` says whether a post's visuals exist yet, and
``pending_visuals`` holds the work order until they do.

Both columns are new in every mode (unlike 0001 there is nothing to adopt), so the
operations run against the database normally.

Backfill: every post that already exists predates the split and was produced by the
old inline pipeline, so its visuals are already in place — those rows are set
``images_ready=True``. The field default is ``False``, so everything imported from
here on correctly lands as "needs images".
"""
from django.db import migrations, models


def mark_existing_posts_ready(apps, schema_editor):
    Post = apps.get_model("keel_cms", "Post")
    Post.objects.all().update(images_ready=True)


def unmark_all_posts(apps, schema_editor):
    Post = apps.get_model("keel_cms", "Post")
    Post.objects.all().update(images_ready=False)


class Migration(migrations.Migration):

    dependencies = [
        ("keel_cms", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="images_ready",
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text=(
                    "True once this post's machine-produced visuals — the bespoke featured "
                    "hero and any in-article NB2 photoreal images — have been generated. The "
                    "content pipeline no longer produces them inline (they added ~123 minutes "
                    "of chain per cluster and nothing in the run consumes them), so a freshly "
                    "imported post lands False and the standalone images pass "
                    "(`generate_post_images`) flips it True. DO NOT PUBLISH a post while this "
                    "is False: its hero is a generic fallback and any NB2 image is still a "
                    "placeholder block in the body."
                ),
            ),
        ),
        migrations.AddField(
            model_name="post",
            name="pending_visuals",
            field=models.JSONField(
                default=dict,
                blank=True,
                help_text=(
                    "Work order for the standalone images pass, written by content_import "
                    'when a post lands without its visuals: {"image_requests": [...], '
                    '"hero_needed": bool, "body_markdown": "..."}. The pass rehydrates a '
                    "bundle from this, runs the hero / NB2 agents against it, applies the "
                    "results back, and clears this field. Empty once images_ready is True."
                ),
            ),
        ),
        migrations.RunPython(mark_existing_posts_ready, unmark_all_posts),
    ]
