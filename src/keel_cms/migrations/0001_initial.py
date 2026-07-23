"""Hand-written initial migration for keel_cms.

**Adoption-first (state-only).** Like keel-seo's Landing move and keel-content's
Twitter move, every operation is wrapped in ``SeparateDatabaseAndState`` with empty
``database_operations``: the ``blog_*`` / ``news_*`` tables are the host's existing
ones, adopted untouched — Django only records the models in its migration STATE, no
``CREATE TABLE`` runs. A host that already ran the source project's ``blog`` / ``news``
migrations keeps its data; those apps then remove these models from *their* state with
matching state-only ``DeleteModel`` migrations. Because no DDL runs, the automated
deploy ``migrate`` applies this cleanly with zero risk of a "table already exists"
failure. (A genuinely fresh project seeds these tables out-of-band.)

The literal ``db_table`` names from the source project are preserved (``blog_post``,
``blog_tag``, ``news_post``, ...) so index/constraint names auto-derive from the same
table names and ``makemigrations --check`` stays clean after adoption.

The ``TopicCluster.conversion_landing`` FK targets the swappable
``KEEL_CMS_LANDING_MODEL`` (default ``keel_seo.Landing``). Its migration dependency
is computed from that setting; a host that points the setting at a different app
gets the right dependency automatically. If the target app provides no migration
graph (e.g. a bare model), remove or adjust the computed dependency below.
"""
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

from keel_cms.config import landing_model_ref

_LANDING_MODEL = landing_model_ref()
_LANDING_APP = _LANDING_MODEL.split(".", 1)[0]


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        migrations.swappable_dependency(_LANDING_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
        migrations.CreateModel(
            name="Author",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("slug", models.SlugField(max_length=150, unique=True)),
                ("role", models.CharField(blank=True, max_length=100)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("bio", models.TextField(blank=True)),
                ("avatar_url", models.URLField(blank=True, max_length=500)),
                ("icon", models.CharField(blank=True, help_text="Font Awesome class for editorial-desk byline/team icon, e.g. 'fa-solid fa-chart-line'.", max_length=60)),
                ("accent", models.CharField(blank=True, help_text="Muted accent key selecting the .desk-icon--<accent> tint class.", max_length=30)),
                ("social_links", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("is_reviewer", models.BooleanField(default=False, help_text="Eligible to be selected as the reviewer of a post.")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="blog_author", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "blog_author", "ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100)),
                ("slug", models.SlugField(max_length=100)),
                ("content_scope", models.CharField(choices=[("blog", "Blog"), ("news", "News")], db_index=True, default="blog", max_length=10)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "blog_category",
                "verbose_name": "Topic",
                "verbose_name_plural": "Topics",
                "ordering": ["name"],
            },
        ),
        migrations.AddConstraint(
            model_name="category",
            constraint=models.UniqueConstraint(fields=("slug", "content_scope"), name="blog_category_slug_content_scope_uniq"),
        ),
        migrations.CreateModel(
            name="Tag",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("slug", models.SlugField(max_length=120, unique=True)),
                ("abbreviation", models.CharField(blank=True, max_length=100)),
                ("name", models.CharField(max_length=255)),
                ("is_term", models.BooleanField(db_index=True, default=False)),
                ("aka", models.JSONField(blank=True, default=list, help_text="Alternate names; list of strings.")),
                ("what_is", models.TextField(blank=True)),
                ("why_it_matters_for_partnership", models.TextField(blank=True)),
                ("why_it_matters", models.TextField(blank=True, help_text="Glossary-term value statement (trading terms use this; partner-glossary terms use why_it_matters_for_partnership).")),
                ("formula", models.TextField(blank=True, null=True)),
                ("real_world_example", models.TextField(blank=True)),
                ("pro_tip", models.TextField(blank=True)),
                ("common_pitfalls", models.TextField(blank=True)),
                ("trade_impact", models.JSONField(blank=True, default=list, help_text="Two-item list [level, explanation]; level is Low/Medium/High/Critical.")),
                ("product_context", models.TextField(blank=True, db_column="signalbots_context", help_text="How the term maps to the host product / delivery surfaces. The DB column keeps its original name for zero-migration adoption; content is host-defined.")),
                ("related_surfaces", models.JSONField(blank=True, default=list, help_text="List of internal landing URLs to link from this term page.")),
                ("visuals", models.JSONField(blank=True, default=list, help_text="Ordered list of visualization specs rendered on the term page. Each item is {component_id, spec, caption?}; component_id is a keel-ui component and spec is validated against that component's JSON Schema at render time.")),
                ("risk_warning_required", models.BooleanField(default=False, help_text="When true, the term page links to a risk-warning surface (performance/results content).")),
                ("faq", models.JSONField(blank=True, default=list, help_text="List of objects with question and answer strings.")),
                ("stakeholder_relevance", models.JSONField(blank=True, default=list, help_text="Audience labels, e.g. broker, ib.")),
                ("toolbox", models.JSONField(blank=True, default=list, help_text="List of objects with tools_desc and tools (string list).")),
                ("experience_level", models.CharField(blank=True, max_length=64)),
                ("parent_category", models.CharField(blank=True, max_length=200)),
                ("child_category", models.CharField(blank=True, max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("related_terms", models.ManyToManyField(blank=True, related_name="related_from", to="keel_cms.tag")),
            ],
            options={"db_table": "blog_tag", "ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Market",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("slug", models.SlugField(max_length=100, unique=True)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "blog_market", "ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="AudienceRole",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=50)),
                ("slug", models.SlugField(max_length=50, unique=True)),
            ],
            options={"db_table": "blog_audience_role", "ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="AudienceLevel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=50)),
                ("slug", models.SlugField(max_length=50, unique=True)),
                ("order", models.PositiveSmallIntegerField(default=0)),
            ],
            options={"db_table": "blog_audience_level", "ordering": ["order", "name"]},
        ),
        migrations.CreateModel(
            name="Post",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=255)),
                ("h1", models.CharField(blank=True, default="", help_text="On-page H1 heading. Falls back to title when blank, so the visible heading can differ from the SEO title tag.", max_length=255)),
                ("slug", models.SlugField(max_length=255, unique=True)),
                ("excerpt", models.TextField(blank=True)),
                ("key_takeaways", models.TextField(blank=True, help_text="Sanitized HTML for public display; generated from Key takeaways Markdown on save.")),
                ("key_takeaways_markdown_source", models.TextField(blank=True, default="", help_text="Markdown source for Key takeaways in the admin editor (round-trip).")),
                ("content_raw", models.TextField(blank=True, default="", help_text="Sanitized HTML produced from the Markdown editor (before auto-linking).")),
                ("content_markdown_source", models.TextField(blank=True, default="", help_text="Last Markdown source from the admin editor (round-trip; not shown publicly).")),
                ("content_rendered", models.TextField(blank=True, null=True, help_text="Final HTML with injected internal links. Populated by the auto-linker task.")),
                ("featured_image_url", models.URLField(blank=True, max_length=500)),
                ("youtube_url", models.URLField(blank=True, default="", help_text="Source YouTube video this post was written from (YouTube-transcript route). Stored so the post can link to or embed the original video.", max_length=500)),
                ("read_time_minutes", models.PositiveIntegerField(default=0)),
                ("view_count", models.PositiveIntegerField(db_index=True, default=0, help_text="Lifetime detail-page views; drives the 'Popular' widgets (recency is the tiebreak).")),
                ("status", models.CharField(choices=[("draft", "Draft"), ("published", "Published"), ("archived", "Archived")], default="draft", max_length=20)),
                ("layout", models.CharField(choices=[("sidebar", "Two-column (with sidebar)"), ("editorial", "Single-column (editorial hero)")], default="editorial", help_text="Detail-page layout. 'Single-column' (default) renders a centered editorial hero (H1 + byline only) with the sidebar boxes moved below the article; 'Two-column' keeps the classic main + sidebar grid.", max_length=20)),
                ("is_pipeline_generated", models.BooleanField(db_index=True, default=False, help_text="True when this post was produced by a content pipeline. Render flow skips HTML sanitization for these posts so that pipeline-emitted visual blocks (Mermaid, Chart.js canvases, custom HTML) survive. Editing the markdown via admin will re-trigger sanitize and may strip blocks.")),
                ("needs_human_assets", models.BooleanField(db_index=True, default=False, help_text="True when the pipeline author left asset-request placeholders in the body (video / screenshot / first-party data the LLM cannot produce). The content team filters on this and replaces each placeholder before publishing.")),
                ("asset_requests", models.JSONField(blank=True, default=list, help_text='Structured list of the human-supplied elements this post still needs: [{"id", "type", "description", "placement"}, ...]. Mirrors the placeholders rendered in the body; kept for filtering/reporting.')),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("meta_title", models.CharField(blank=True, max_length=70)),
                ("meta_description", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.RESTRICT, related_name="posts", to="keel_cms.author")),
                ("reviewer", models.ForeignKey(blank=True, help_text="Optional. Editor or expert who reviewed the post for accuracy.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_posts", to="keel_cms.author")),
                ("category", models.ForeignKey(blank=True, help_text="Auto-set to the first topic ticked in the editor; used for breadcrumbs and list cards.", null=True, on_delete=django.db.models.deletion.RESTRICT, related_name="posts", to="keel_cms.category", verbose_name="Primary topic")),
                ("categories", models.ManyToManyField(blank=True, help_text="One or more topics. The first ticked topic is also stored as the primary topic.", related_name="posts_multi", to="keel_cms.category", verbose_name="Topics")),
                ("markets", models.ManyToManyField(blank=True, related_name="posts", to="keel_cms.market")),
                ("audience_roles", models.ManyToManyField(blank=True, related_name="posts", to="keel_cms.audiencerole")),
                ("audience_levels", models.ManyToManyField(blank=True, related_name="posts", to="keel_cms.audiencelevel")),
                ("related_terms", models.ManyToManyField(blank=True, help_text="Glossary terms (is_term=True) this post links to.", limit_choices_to={"is_term": True}, related_name="referencing_posts", to="keel_cms.tag")),
                ("deleted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="deleted_blog_posts", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "blog_post", "ordering": ["-published_at", "-created_at"]},
        ),
        migrations.CreateModel(
            name="TopicCluster",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("slug", models.SlugField(max_length=200, unique=True)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("proposed", "Proposed"), ("active", "Active"), ("archived", "Archived")], db_index=True, default="proposed", max_length=20)),
                ("brief", models.JSONField(blank=True, default=dict, help_text="Cluster-level brief written by the brief stage's cluster pass: element ownership across siblings, per-content scope fences, and the glossary terms members link instead of re-explaining.")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("pillar", models.ForeignKey(blank=True, help_text="The comprehensive hub post of this cluster.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pillar_of_clusters", to="keel_cms.post")),
                ("primary_category", models.ForeignKey(blank=True, help_text="The cluster's home in the two-level tree (Category -> Topic Cluster -> content). The categories M2M stays the multi-valued facet.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="primary_topic_clusters", to="keel_cms.category")),
                ("conversion_landing", models.ForeignKey(blank=True, help_text="The money page this cluster's contents funnel to (CTA target). A pointer, not a member - landings never join the hub-spoke. Target is the swappable KEEL_CMS_LANDING_MODEL.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="funnel_clusters", to=_LANDING_MODEL)),
                ("key_terms", models.ManyToManyField(blank=True, help_text="The glossary terms most central to this cluster's need-space.", limit_choices_to={"is_term": True}, related_name="key_in_clusters", to="keel_cms.tag")),
                ("categories", models.ManyToManyField(blank=True, related_name="topic_clusters", to="keel_cms.category")),
                ("markets", models.ManyToManyField(blank=True, related_name="topic_clusters", to="keel_cms.market")),
                ("audience_roles", models.ManyToManyField(blank=True, related_name="topic_clusters", to="keel_cms.audiencerole")),
                ("audience_levels", models.ManyToManyField(blank=True, related_name="topic_clusters", to="keel_cms.audiencelevel")),
            ],
            options={"db_table": "blog_topic_cluster", "ordering": ["name"]},
        ),
        migrations.AddField(
            model_name="post",
            name="topic_cluster",
            field=models.ForeignKey(blank=True, help_text="The topic cluster this post belongs to (the 1:1 content spine).", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="posts", to="keel_cms.topiccluster"),
        ),
        migrations.CreateModel(
            name="PostTag",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("post", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="post_tags", to="keel_cms.post")),
                ("tag", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="post_tags", to="keel_cms.tag")),
            ],
            options={"db_table": "blog_post_tags", "unique_together": {("post", "tag")}},
        ),
        migrations.AddField(
            model_name="post",
            name="tags",
            field=models.ManyToManyField(blank=True, related_name="posts", through="keel_cms.PostTag", to="keel_cms.tag"),
        ),
        migrations.CreateModel(
            name="UserIntent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255, verbose_name="Intent name")),
                ("target_url", models.URLField(max_length=500, unique=True, verbose_name="Target URL")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "blog_user_intent",
                "verbose_name": "User intent",
                "verbose_name_plural": "User intents",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Keyword",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("phrase", models.CharField(db_index=True, max_length=255, unique=True, verbose_name="Keyword phrase")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("intent", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="keywords", to="keel_cms.userintent", verbose_name="User intent")),
            ],
            options={
                "db_table": "blog_keyword",
                "verbose_name": "Keyword",
                "verbose_name_plural": "Keywords",
                "ordering": ["phrase"],
            },
        ),
        migrations.CreateModel(
            name="Comment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("author_name", models.CharField(blank=True, max_length=150)),
                ("author_email", models.EmailField(blank=True, max_length=254)),
                ("body", models.TextField()),
                ("status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("spam", "Spam"), ("rejected", "Rejected")], default="pending", max_length=20)),
                ("depth", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("post", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comments", to="keel_cms.post")),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="replies", to="keel_cms.comment")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="blog_comments", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "blog_comment", "ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="ContentPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(help_text="Stable identity; equals the produced Post.slug. The upsert + resume key.", max_length=255, unique=True)),
                ("canonical_key", models.SlugField(blank=True, db_index=True, help_text="Controlled-vocabulary key for the user NEED. Synonym needs share one key; the cross-run dedup spine is keyed on this.", max_length=255)),
                ("title", models.CharField(max_length=255)),
                ("h1", models.CharField(blank=True, default="", max_length=255)),
                ("intent", models.TextField(blank=True, help_text="One-line user need this page satisfies.")),
                ("role", models.CharField(blank=True, choices=[("pillar", "Pillar"), ("spoke", "Spoke")], max_length=10)),
                ("target", models.CharField(choices=[("blog", "Blog"), ("news", "News"), ("glossary_term", "Glossary Term")], default="blog", max_length=16)),
                ("intent_frame", models.CharField(blank=True, max_length=40)),
                ("entity", models.CharField(blank=True, max_length=160)),
                ("observed_intent", models.TextField(blank=True, help_text="Intent derived from reading the real competitor pages (reconcile Layer 1).")),
                ("scope_includes", models.JSONField(blank=True, default=list)),
                ("scope_excludes", models.JSONField(blank=True, default=list)),
                ("canonical_owner", models.JSONField(blank=True, default=dict, help_text="Which spoke owns each shared asset (expectancy widget, stat, ...).")),
                ("competitor_traffic", models.PositiveIntegerField(blank=True, null=True)),
                ("competitor_urls", models.JSONField(blank=True, default=list)),
                ("keyword_volume", models.PositiveIntegerField(blank=True, null=True)),
                ("keywords", models.JSONField(blank=True, default=list, help_text='Demand evidence from the keyword-clustering path: [{"keyword": str, "volume": int}, ...]. Flows into the author brief as intent-comprehension evidence (never a stuffing quota).')),
                ("brief", models.JSONField(blank=True, default=dict, help_text="Structured per-article author brief written by the brief stage (intent statement, essential/complementary elements, headings outline, keyword usage, SERP evidence). Empty dict = not briefed yet.")),
                ("feasibility", models.CharField(choices=[("llm_full", "LLM writes it fully"), ("llm_with_assets", "LLM writes + human supplies assets"), ("human_only", "Human author only (brief handed off)")], db_index=True, default="llm_full", help_text="Brief-stage verdict on who can produce this content. 'human_only' rows never enter the generation queue; their brief is the handoff to the human writer.", max_length=20)),
                ("priority", models.FloatField(blank=True, db_index=True, null=True)),
                ("clarity", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("source_type", models.CharField(choices=[("top_pages", "Competitor Top Pages"), ("keyword_clustering", "Keyword Clustering"), ("ideation", "Landing-Support Ideation"), ("manual", "Manual / Back-filled"), ("youtube", "YouTube Video Transcript"), ("twitter", "Twitter/X Post")], db_index=True, max_length=20)),
                ("source_ref", models.CharField(blank=True, help_text="Workbook path / run id the row was ingested from.", max_length=500)),
                ("youtube_url", models.URLField(blank=True, default="", help_text="For source_type=youtube: the source video. Copied onto the produced Post so the blog can link to or embed the original video.", max_length=500)),
                ("source_transcript", models.TextField(blank=True, default="", help_text="For source_type=youtube: the cleaned video transcript. Fed to the generator as the PRIMARY source material the article is written from.")),
                ("status", models.CharField(choices=[("planned", "Planned"), ("reconciled", "Reconciled"), ("generating", "Generating"), ("drafted", "Drafted"), ("published", "Published"), ("rejected", "Rejected"), ("merged", "Merged (deduped)")], db_index=True, default="planned", max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("topic_cluster", models.ForeignKey(blank=True, help_text="The 1:1 content spine this planned content belongs to.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="content_plans", to="keel_cms.topiccluster")),
                ("categories", models.ManyToManyField(blank=True, related_name="content_plans", to="keel_cms.category")),
                ("markets", models.ManyToManyField(blank=True, related_name="content_plans", to="keel_cms.market")),
                ("audience_roles", models.ManyToManyField(blank=True, related_name="content_plans", to="keel_cms.audiencerole")),
                ("audience_levels", models.ManyToManyField(blank=True, related_name="content_plans", to="keel_cms.audiencelevel")),
                ("glossary_terms", models.ManyToManyField(blank=True, help_text="Glossary terms (is_term=True) this planned content will link to.", limit_choices_to={"is_term": True}, related_name="planned_in", to="keel_cms.tag")),
                ("produced_post", models.OneToOneField(blank=True, help_text="The Post generated from this plan row (set by content_import).", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="content_plan", to="keel_cms.post")),
                ("produced_term", models.ForeignKey(blank=True, help_text="For target=glossary_term rows: the live Tag(is_term=True) this queued term became once authored + persisted.", limit_choices_to={"is_term": True}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="produced_from_plans", to="keel_cms.tag")),
                ("merged_into", models.ForeignKey(blank=True, help_text="When status=merged, the surviving plan row this need was deduped into.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="merged_rows", to="keel_cms.contentplan")),
            ],
            options={
                "db_table": "blog_content_plan",
                "ordering": ["-created_at"],
                "verbose_name": "Content plan",
                "verbose_name_plural": "Content plan",
            },
        ),
        migrations.CreateModel(
            name="NewsPost",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=255)),
                ("slug", models.SlugField(max_length=255, unique=True)),
                ("excerpt", models.TextField(blank=True)),
                ("key_takeaways", models.TextField(blank=True, help_text="Sanitized HTML for public display; generated from Key takeaways Markdown on save.")),
                ("key_takeaways_markdown_source", models.TextField(blank=True, default="", help_text="Markdown source for Key takeaways in the admin editor (round-trip).")),
                ("content_raw", models.TextField(blank=True, default="", help_text="Sanitized HTML produced from the Markdown editor (before auto-linking).")),
                ("content_markdown_source", models.TextField(blank=True, default="", help_text="Last Markdown source from the admin editor (round-trip; not shown publicly).")),
                ("content_rendered", models.TextField(blank=True, null=True, help_text="Final HTML with injected internal links. Populated by the auto-linker task.")),
                ("featured_image_url", models.URLField(blank=True, max_length=500)),
                ("read_time_minutes", models.PositiveIntegerField(default=0)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("published", "Published"), ("archived", "Archived")], default="draft", max_length=20)),
                ("is_pipeline_generated", models.BooleanField(db_index=True, default=False, help_text="True when this article was produced by a content pipeline. Render flow skips HTML sanitization for these articles so that pipeline-emitted visual blocks (Mermaid, Chart.js canvases, custom HTML) survive.")),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("meta_title", models.CharField(blank=True, max_length=70)),
                ("meta_description", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.RESTRICT, related_name="news_posts", to="keel_cms.author")),
                ("category", models.ForeignKey(blank=True, help_text="Auto-set to the first topic ticked in the editor; used for breadcrumbs and list cards.", limit_choices_to={"content_scope": "news"}, null=True, on_delete=django.db.models.deletion.RESTRICT, related_name="news_posts", to="keel_cms.category", verbose_name="Primary topic")),
                ("categories", models.ManyToManyField(blank=True, help_text="One or more topics. The first ticked topic is also stored as the primary topic.", limit_choices_to={"content_scope": "news"}, related_name="news_posts_multi", to="keel_cms.category", verbose_name="Topics")),
                ("topic_cluster", models.ForeignKey(blank=True, help_text="The topic cluster this article belongs to (the 1:1 content spine).", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="news_posts", to="keel_cms.topiccluster")),
                ("markets", models.ManyToManyField(blank=True, related_name="news_posts", to="keel_cms.market")),
                ("audience_roles", models.ManyToManyField(blank=True, related_name="news_posts", to="keel_cms.audiencerole")),
                ("audience_levels", models.ManyToManyField(blank=True, related_name="news_posts", to="keel_cms.audiencelevel")),
                ("related_terms", models.ManyToManyField(blank=True, help_text="Glossary terms (is_term=True) this article links to.", limit_choices_to={"is_term": True}, related_name="referencing_news_posts", to="keel_cms.tag")),
                ("deleted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="deleted_news_posts", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "news_post", "ordering": ["-published_at", "-created_at"]},
        ),
        migrations.CreateModel(
            name="NewsPostTag",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("news_post", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="news_post_tags", to="keel_cms.newspost")),
                ("tag", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="news_post_tags", to="keel_cms.tag")),
            ],
            options={"db_table": "news_post_tags", "unique_together": {("news_post", "tag")}},
        ),
        migrations.AddField(
            model_name="newspost",
            name="tags",
            field=models.ManyToManyField(blank=True, related_name="news_posts", through="keel_cms.NewsPostTag", to="keel_cms.tag"),
        ),
        migrations.CreateModel(
            name="NewsComment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("author_name", models.CharField(blank=True, max_length=150)),
                ("author_email", models.EmailField(blank=True, max_length=254)),
                ("body", models.TextField()),
                ("status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("spam", "Spam"), ("rejected", "Rejected")], default="pending", max_length=20)),
                ("depth", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("news_post", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comments", to="keel_cms.newspost")),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="replies", to="keel_cms.newscomment")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="news_comments", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "news_comment", "ordering": ["created_at"]},
        ),
            ],
        ),
    ]
