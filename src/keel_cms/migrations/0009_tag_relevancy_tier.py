from django.db import migrations, models


class Migration(migrations.Migration):
    """Denormalise the glossary relevancy tier onto the term row.

    The tier is always computed live by ``keel_cms.glossary_tiers``; this column is the
    stored copy that views, sitemaps and the noindex gate filter on, written by
    ``glossary_tier_apply``. Additive and blank-by-default, so a consumer that never runs
    the framework is unaffected.
    """

    dependencies = [
        ("keel_cms", "0008_post_cluster_position"),
    ]

    operations = [
        migrations.AddField(
            model_name="tag",
            name="relevancy_tier",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text=(
                    "Production-priority tier T1-T5 computed by keel_cms.glossary_tiers "
                    "(service proximity / search demand / hub value). Denormalised onto the "
                    "row so views, sitemaps and the noindex gate can filter on it without "
                    "recomputing; ``glossary_tier_apply`` is what refreshes it. Blank means "
                    "never tiered."
                ),
                max_length=2,
            ),
        ),
    ]
