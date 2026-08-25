"""Record the axis answers behind ``ContentPlan.scope_relevance``, not just the level.

Additive and nullable on purpose: the deploy applies migrations before the canary
renders, so a new column must be safe for the *old* code still serving traffic.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("keel_cms", "0009_tag_relevancy_tier"),
    ]

    operations = [
        migrations.AddField(
            model_name="contentplan",
            name="scope_axes",
            field=models.JSONField(
                blank=True,
                null=True,
                help_text="The yes/no answer to each scope axis that produced "
                "scope_relevance, e.g. {\"scope\": true, \"service\": true, "
                "\"partnership\": false}. Axis names are the consumer's; the backbone "
                "axis is required. NULL = the level was graded without recording its "
                "inputs.",
            ),
        ),
        migrations.AddField(
            model_name="contentplan",
            name="scope_ruleset",
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=64,
                help_text="Identifier of the scope definitions in force when scope_axes "
                "was answered (e.g. a date or a version string). Rows carrying an older "
                "ruleset are the ones a scope widening has to revisit.",
            ),
        ),
    ]
