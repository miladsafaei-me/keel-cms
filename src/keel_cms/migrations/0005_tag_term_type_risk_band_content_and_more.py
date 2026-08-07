from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('keel_cms', '0004_contentplan_status_backlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='tag',
            name='term_type',
            field=models.CharField(blank=True, db_index=True, help_text="Discriminator for the kind of glossary term (e.g. concept, contract, indicator, pattern, strategy, risk, psychology, scam). Domain-neutral: the allowed set and each type's required/optional field schema are host content, declared via KEEL_CMS['glossary_term_types'] and ['glossary_field_schema']. Drives the niche-purity gate + score.", max_length=40),
        ),
        migrations.AddField(
            model_name='tag',
            name='one_line_definition',
            field=models.CharField(blank=True, help_text='One-sentence TL;DR. Feeds the card subtitle, meta description, schema.org DefinedTerm.description, and internal-link hover previews.', max_length=280),
        ),
        migrations.AddField(
            model_name='tag',
            name='facets',
            field=models.JSONField(blank=True, default=list, help_text="Cross-cutting labels beyond the parent/child tree (e.g. 'trend', 'momentum', '60-second', 'otc'); powers related-term discovery and filters."),
        ),
        migrations.AddField(
            model_name='tag',
            name='content',
            field=models.JSONField(blank=True, default=dict, help_text="Typed content store for host-domain fields keyed by the consumer's glossary_field_schema (e.g. impact_on_expectancy, expiry_and_timing, execution_and_platform_nuances). Keeps domain-specific prose out of the shared columns so the engine stays business-neutral."),
        ),
        migrations.AddField(
            model_name='tag',
            name='risk_band',
            field=models.CharField(blank=True, choices=[('none', 'None'), ('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('extreme', 'Extreme')], db_index=True, help_text='Structured risk level for the sidebar risk card and filtering; replaces parsing a leading band word out of prose. Blank when risk is not applicable.', max_length=16),
        ),
    ]
