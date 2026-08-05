from django.db import migrations, models


class Migration(migrations.Migration):
    """Add the ``backlog`` ContentPlan status — a pre-queue shelf.

    Choices-only AlterField: the column is already varchar(12) and ``backlog`` is
    7 characters, so no data is touched and no row changes status. It exists so an
    approved content idea can sit in the roadmap without any queue reader picking
    it up (``content_next_action`` reads reconciled/generating, reconcile reads
    planned/reconciled — ``backlog`` is in neither set).
    """

    dependencies = [
        ("keel_cms", "0003_tag_at_a_glance_tag_comparison_tag_how_it_works_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="contentplan",
            name="status",
            field=models.CharField(
                choices=[
                    ("backlog", "Backlog (not queued)"),
                    ("planned", "Planned"),
                    ("reconciled", "Reconciled"),
                    ("generating", "Generating"),
                    ("drafted", "Drafted"),
                    ("published", "Published"),
                    ("rejected", "Rejected"),
                    ("merged", "Merged (deduped)"),
                ],
                db_index=True,
                default="planned",
                max_length=12,
            ),
        ),
    ]
