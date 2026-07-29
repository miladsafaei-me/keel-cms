"""Shared content-engine models for keel-cms (blog + news + glossary).

This single module merges the SignalBots ``blog.models`` and ``news.models`` into
one reusable Django app. The literal ``db_table`` names from the source project are
preserved (``blog_post``, ``blog_tag``, ``news_post``, ...) so a host can adopt
keel-cms with only a metadata-level ``AlterModelTable`` / ``RenameModel`` migration
rather than a data copy — the same adoption strategy keel-seo uses for its Landing
table. Override a table name only if the host truly needs to.

Business coupling is neutralized into ``keel_cms.config`` hooks:

* ``Tag.get_meta_title()`` reads the brand string + glossary title suffix from
  ``KEEL_CMS`` config instead of hardcoding a project name.
* ``TopicCluster.conversion_landing`` targets ``settings.KEEL_CMS_LANDING_MODEL``
  (default ``"keel_seo.Landing"``) so the host supplies its own money-page model.

The public URL reversers (``Tag.get_absolute_url``) name host URL patterns
(``keel_cms:trading_glossary_term`` / ``keel_cms:tag_detail``); they are guarded so
a standalone import (no URLconf wired) never raises.
"""

import math
import re
import uuid

from django.conf import settings
from django.db import models
from django.utils.html import strip_tags

from .config import cms_setting, landing_model_ref


class ContentScope(models.TextChoices):
    """Whether taxonomy (category/tag) applies to blog posts or news articles."""

    BLOG = "blog", "Blog"
    NEWS = "news", "News"


class Author(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blog_author",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=150, unique=True)
    role = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    bio = models.TextField(blank=True)
    avatar_url = models.URLField(max_length=500, blank=True)
    icon = models.CharField(
        max_length=60,
        blank=True,
        help_text="Font Awesome class for editorial-desk byline/team icon, e.g. 'fa-solid fa-chart-line'.",
    )
    accent = models.CharField(
        max_length=30,
        blank=True,
        help_text="Muted accent key selecting the .desk-icon--<accent> tint class.",
    )
    social_links = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    is_reviewer = models.BooleanField(
        default=False,
        help_text="Eligible to be selected as the reviewer of a post.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "blog_author"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    content_scope = models.CharField(
        max_length=10,
        choices=ContentScope.choices,
        default=ContentScope.BLOG,
        db_index=True,
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "blog_category"
        verbose_name = "Topic"
        verbose_name_plural = "Topics"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["slug", "content_scope"],
                name="blog_category_slug_content_scope_uniq",
            ),
        ]

    def __str__(self):
        return self.name


def _abbreviation_already_in_tag_name(abbreviation: str, name: str) -> bool:
    """
    Return True when ``name`` already surfaces the abbreviation, so ``ABBR: name`` would repeat it.

    Handles leading ``ABBR:``, ``ABBR ``, parenthetical ``(ABBR)``, and whole-token occurrences
    (case-insensitive; uses casefolded name for boundary checks).
    """
    abbr = (abbreviation or "").strip()
    term = (name or "").strip()
    if not abbr or not term:
        return False
    ac = abbr.casefold()
    tc = term.casefold()
    if tc == ac:
        return True
    if tc.startswith(ac + ":") or tc.startswith(ac + "："):
        return True
    if tc.startswith(ac + " "):
        return True
    if re.search(rf"\(\s*{re.escape(abbr)}\s*\)", term, re.IGNORECASE):
        return True
    escaped = re.escape(ac)
    if re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", tc):
        return True
    return False


class Tag(models.Model):
    """Shared taxonomy for blog posts, news articles, and glossary terms."""

    id = models.BigAutoField(primary_key=True)
    slug = models.SlugField(max_length=120, unique=True)
    abbreviation = models.CharField(max_length=100, blank=True)
    name = models.CharField(max_length=255)
    is_term = models.BooleanField(default=False, db_index=True)
    aka = models.JSONField(
        default=list,
        blank=True,
        help_text="Alternate names; list of strings.",
    )
    what_is = models.TextField(blank=True)
    why_it_matters_for_partnership = models.TextField(blank=True)
    why_it_matters = models.TextField(
        blank=True,
        help_text="Glossary-term value statement (trading terms use this; "
        "partner-glossary terms use why_it_matters_for_partnership).",
    )
    formula = models.TextField(null=True, blank=True)
    real_world_example = models.TextField(blank=True)
    pro_tip = models.TextField(blank=True)
    common_pitfalls = models.TextField(blank=True)
    trade_impact = models.JSONField(
        default=list,
        blank=True,
        help_text="Two-item list [level, explanation]; level is Low/Medium/High/Critical.",
    )
    product_context = models.TextField(
        blank=True,
        db_column="signalbots_context",
        help_text="How the term maps to the host product / delivery surfaces. The DB "
        "column keeps its original name for zero-migration adoption; content is host-defined.",
    )
    related_surfaces = models.JSONField(
        default=list,
        blank=True,
        help_text="List of internal landing URLs to link from this term page.",
    )
    visuals = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Ordered list of visualization specs rendered on the term page. Each item is "
            "{component_id, spec, caption?}; component_id is a keel-ui component and spec "
            "is validated against that component's JSON Schema at render time."
        ),
    )
    risk_warning_required = models.BooleanField(
        default=False,
        help_text="When true, the term page links to a risk-warning surface (performance/results content).",
    )
    faq = models.JSONField(
        default=list,
        blank=True,
        help_text="List of objects with question and answer strings.",
    )
    stakeholder_relevance = models.JSONField(
        default=list,
        blank=True,
        help_text="Audience labels, e.g. broker, ib.",
    )
    toolbox = models.JSONField(
        default=list,
        blank=True,
        help_text="List of objects with tools_desc and tools (string list).",
    )
    experience_level = models.CharField(max_length=64, blank=True)
    parent_category = models.CharField(max_length=200, blank=True)
    child_category = models.CharField(max_length=200, blank=True)
    related_terms = models.ManyToManyField(
        "self",
        symmetrical=False,
        related_name="related_from",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "blog_tag"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        """Canonical public URL: glossary terms under the term route, else the tag route.

        Names host URL patterns (``keel_cms:trading_glossary_term`` /
        ``keel_cms:tag_detail``). Guarded so a standalone import with no URLconf
        wired returns an empty string rather than raising ``NoReverseMatch``.
        """
        from django.urls import NoReverseMatch, reverse

        try:
            if getattr(self, "is_term", False):
                return reverse("keel_cms:trading_glossary_term", kwargs={"slug": self.slug})
            return reverse("keel_cms:tag_detail", kwargs={"slug": self.slug})
        except NoReverseMatch:
            return ""

    def get_public_heading(self) -> str:
        """Visible heading: ``Abbreviation: Term`` when useful, else ``name`` alone (no duplicate abbr)."""
        abbr = (self.abbreviation or "").strip()
        name = (self.name or "").strip()
        if abbr and not _abbreviation_already_in_tag_name(abbr, name):
            return f"{abbr}: {name}"
        return name

    def get_meta_title(self) -> str:
        """Browser ``<title>`` for public tag/term pages (SEO phrasing).

        The brand suffix comes from ``KEEL_CMS`` config, not a hardcoded project
        name: glossary terms append ``glossary_title_suffix``; tag pages append
        ``"| <site_name>"`` when a site name is configured.
        """
        heading = self.get_public_heading()
        if getattr(self, "is_term", False):
            suffix = cms_setting("glossary_title_suffix")
            return f"What is {heading}?{(' ' + suffix) if suffix else ''}".rstrip()
        site = cms_setting("site_name")
        return f"What is {heading}?{(' | ' + site) if site else ''}".rstrip()

    def get_glossary_category_label(self) -> str:
        """Single label for filters and chips (parent / child hierarchy)."""
        parent = (self.parent_category or "").strip()
        child = (self.child_category or "").strip()
        if parent and child:
            return f"{parent} › {child}"
        return child or parent or "General"

    @classmethod
    def resolve_existing_terms(cls, names):
        """Resolve names/slugs to EXISTING glossary terms (``is_term=True``); never create.

        Blog tags are drawn exclusively from the glossary vocabulary, so every
        tag-assignment path routes through this. A name that does not match an
        existing glossary term — a typo, a broker name, a free-text label — is
        dropped (logged), never minted as a new Tag row. Order-preserving and
        de-duplicated.
        """
        import logging
        from django.utils.text import slugify

        logger = logging.getLogger(__name__)
        out: list[Tag] = []
        seen: set = set()
        for raw in names or []:
            value = (raw or "").strip()
            if not value:
                continue
            term = (
                cls.objects.filter(is_term=True, slug=slugify(value)).first()
                or cls.objects.filter(is_term=True, name__iexact=value).first()
            )
            if term is None:
                logger.warning(
                    "keel_cms.Tag.resolve_existing_terms: glossary term %r not found; skipped", value
                )
            elif term.pk not in seen:
                seen.add(term.pk)
                out.append(term)
        return out


class Market(models.Model):
    """A tradable market facet for content (Forex, Crypto, Binary Options, ...)."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "blog_market"
        ordering = ["name"]

    def __str__(self):
        return self.name


class AudienceRole(models.Model):
    """Reader role a content targets - e.g. Trader or IB."""

    name = models.CharField(max_length=50)
    slug = models.SlugField(max_length=50, unique=True)

    class Meta:
        db_table = "blog_audience_role"
        ordering = ["name"]

    def __str__(self):
        return self.name


class AudienceLevel(models.Model):
    """Reader expertise level - Beginner, Mid-Level, Advanced."""

    name = models.CharField(max_length=50)
    slug = models.SlugField(max_length=50, unique=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "blog_audience_level"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class TopicCluster(models.Model):
    """A group of related audience needs - the 1:1 spine of content organization.

    One pillar + N spokes; every content belongs to exactly one cluster, and
    Category / Market / Audience are multi-valued facets layered on top.
    """

    class Status(models.TextChoices):
        PROPOSED = "proposed", "Proposed"
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PROPOSED, db_index=True
    )
    pillar = models.ForeignKey(
        "Post",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pillar_of_clusters",
        help_text="The comprehensive hub post of this cluster.",
    )
    primary_category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="primary_topic_clusters",
        help_text="The cluster's home in the two-level tree (Category -> Topic "
        "Cluster -> content). The categories M2M stays the multi-valued facet.",
    )
    conversion_landing = models.ForeignKey(
        landing_model_ref(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="funnel_clusters",
        help_text="The money page this cluster's contents funnel to (CTA target). "
        "A pointer, not a member — landings never join the hub-spoke. Target is the "
        "swappable KEEL_CMS_LANDING_MODEL.",
    )
    key_terms = models.ManyToManyField(
        "Tag",
        related_name="key_in_clusters",
        blank=True,
        limit_choices_to={"is_term": True},
        help_text="The glossary terms most central to this cluster's need-space.",
    )
    brief = models.JSONField(
        default=dict,
        blank=True,
        help_text="Cluster-level brief written by the brief stage's cluster pass: "
        "element ownership across siblings, per-content scope fences, and the "
        "glossary terms members link instead of re-explaining.",
    )
    categories = models.ManyToManyField(Category, related_name="topic_clusters", blank=True)
    markets = models.ManyToManyField(Market, related_name="topic_clusters", blank=True)
    audience_roles = models.ManyToManyField(AudienceRole, related_name="topic_clusters", blank=True)
    audience_levels = models.ManyToManyField(AudienceLevel, related_name="topic_clusters", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "blog_topic_cluster"
        ordering = ["name"]

    def __str__(self):
        return self.name


class ActivePostManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


# watch?v=ID | youtu.be/ID | shorts/ID | embed/ID - the 11-char YouTube video id.
# Kept local so the Post property has zero external dependency.
_YOUTUBE_ID_RE = re.compile(
    r"(?:youtube(?:-nocookie)?\.com/(?:watch\?(?:[^#\s]*&)?v=|embed/|shorts/)|youtu\.be/)"
    r"([A-Za-z0-9_-]{11})"
)


class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class Layout(models.TextChoices):
        SIDEBAR = "sidebar", "Two-column (with sidebar)"
        EDITORIAL = "editorial", "Single-column (editorial hero)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    h1 = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="On-page H1 heading. Falls back to title when blank, so the visible heading can differ from the SEO title tag.",
    )
    slug = models.SlugField(max_length=255, unique=True)
    excerpt = models.TextField(blank=True)
    key_takeaways = models.TextField(
        blank=True,
        help_text="Sanitized HTML for public display; generated from Key takeaways Markdown on save.",
    )
    key_takeaways_markdown_source = models.TextField(
        blank=True,
        default="",
        help_text="Markdown source for Key takeaways in the admin editor (round-trip).",
    )
    content_raw = models.TextField(
        blank=True,
        default="",
        help_text="Sanitized HTML produced from the Markdown editor (before auto-linking).",
    )
    content_markdown_source = models.TextField(
        blank=True,
        default="",
        help_text="Last Markdown source from the admin editor (round-trip; not shown publicly).",
    )
    content_rendered = models.TextField(
        blank=True,
        null=True,
        help_text="Final HTML with injected internal links. Populated by the auto-linker task.",
    )
    featured_image_url = models.URLField(max_length=500, blank=True)
    youtube_url = models.URLField(
        max_length=500,
        blank=True,
        default="",
        help_text=(
            "Source YouTube video this post was written from (YouTube-transcript "
            "route). Stored so the post can link to or embed the original video."
        ),
    )
    read_time_minutes = models.PositiveIntegerField(default=0)
    view_count = models.PositiveIntegerField(
        default=0,
        db_index=True,
        help_text="Lifetime detail-page views; drives the 'Popular' widgets (recency is the tiebreak).",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    layout = models.CharField(
        max_length=20,
        choices=Layout.choices,
        default=Layout.EDITORIAL,
        help_text=(
            "Detail-page layout. 'Single-column' (default) renders a centered "
            "editorial hero (H1 + byline only) with the sidebar boxes moved below "
            "the article; 'Two-column' keeps the classic main + sidebar grid."
        ),
    )
    is_pipeline_generated = models.BooleanField(
        default=False,
        db_index=True,
        help_text=(
            "True when this post was produced by a content pipeline. "
            "Render flow skips HTML sanitization for these posts so that pipeline-emitted "
            "visual blocks (Mermaid, Chart.js canvases, custom HTML) survive. "
            "Editing the markdown via admin will re-trigger sanitize and may strip blocks."
        ),
    )
    needs_human_assets = models.BooleanField(
        default=False,
        db_index=True,
        help_text=(
            "True when the pipeline author left asset-request placeholders in the "
            "body (video / screenshot / first-party data the LLM cannot produce). "
            "The content team filters on this and replaces each placeholder before publishing."
        ),
    )
    asset_requests = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Structured list of the human-supplied elements this post still needs: "
            '[{"id", "type", "description", "placement"}, ...]. Mirrors the '
            "placeholders rendered in the body; kept for filtering/reporting."
        ),
    )
    images_ready = models.BooleanField(
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
    )
    pending_visuals = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Work order for the standalone images pass, written by content_import "
            'when a post lands without its visuals: {"image_requests": [...], '
            '"hero_needed": bool, "body_markdown": "..."}. The pass rehydrates a '
            "bundle from this, runs the hero / NB2 agents against it, applies the "
            "results back, and clears this field. Empty once images_ready is True."
        ),
    )
    author = models.ForeignKey(
        Author,
        on_delete=models.RESTRICT,
        related_name="posts",
    )
    reviewer = models.ForeignKey(
        Author,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_posts",
        help_text="Optional. Editor or expert who reviewed the post for accuracy.",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="posts",
        verbose_name="Primary topic",
        help_text="Auto-set to the first topic ticked in the editor; used for breadcrumbs and list cards.",
    )
    categories = models.ManyToManyField(
        Category,
        related_name="posts_multi",
        blank=True,
        verbose_name="Topics",
        help_text="One or more topics. The first ticked topic is also stored as the primary topic.",
    )
    tags = models.ManyToManyField(Tag, through="PostTag", related_name="posts", blank=True)
    topic_cluster = models.ForeignKey(
        TopicCluster,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posts",
        help_text="The topic cluster this post belongs to (the 1:1 content spine).",
    )
    markets = models.ManyToManyField(Market, related_name="posts", blank=True)
    audience_roles = models.ManyToManyField(AudienceRole, related_name="posts", blank=True)
    audience_levels = models.ManyToManyField(AudienceLevel, related_name="posts", blank=True)
    related_terms = models.ManyToManyField(
        Tag,
        related_name="referencing_posts",
        blank=True,
        limit_choices_to={"is_term": True},
        help_text="Glossary terms (is_term=True) this post links to.",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_blog_posts",
    )

    objects = ActivePostManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "blog_post"
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return self.title

    @property
    def youtube_video_id(self) -> str:
        """The 11-char YouTube id parsed from ``youtube_url`` (or "" if none/invalid)."""
        m = _YOUTUBE_ID_RE.search(self.youtube_url or "")
        return m.group(1) if m else ""

    def save(self, *args, update_fields=None, **kwargs):
        """Always bump ``updated_at`` on save — including partial saves.

        ``updated_at`` is ``auto_now``, but Django only persists an ``auto_now``
        field on a partial save when it is listed in ``update_fields``. Callers
        that write a subset of fields would otherwise leave "Last Updated" stale.
        Rule: any change to a post refreshes its edit timestamp.
        """
        if update_fields is not None:
            update_fields = {*update_fields, "updated_at"}
        super().save(*args, update_fields=update_fields, **kwargs)

    def soft_delete(self, user=None):
        from django.utils import timezone

        self.is_deleted = True
        self.deleted_at = timezone.now()
        if user is not None and getattr(user, "pk", None):
            self.deleted_by = user
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])

    def get_read_time_minutes(self):
        """Calculate read time from content. Standard: ~200 words/min."""
        if self.read_time_minutes and self.read_time_minutes > 0:
            return self.read_time_minutes
        content = self.content_rendered or self.content_raw or ""
        text = strip_tags(content)
        words = len(re.findall(r"\S+", text))
        return max(1, math.ceil(words / 200))

    @property
    def content(self):
        """Display content: prefer rendered (with links), fallback to raw."""
        return self.content_rendered or self.content_raw or ""

    @property
    def demand_stats(self):
        """Measured demand behind this post, read off its ContentPlan row.

        Keyword-route posts carry the intent's keyword count + summed monthly
        search volume; top-pages posts carry the competitor-URL count + the
        competitor group's total traffic. ``None`` when the post was never
        planned. List views should ``select_related("content_plan")`` to keep
        this O(1).
        """
        plan = getattr(self, "content_plan", None)
        if plan is None:
            return None
        return {
            "source": plan.source_type,
            "keyword_count": len(plan.keywords or []),
            "keyword_volume": plan.keyword_volume or 0,
            "competitor_count": len(plan.competitor_urls or []),
            "competitor_traffic": plan.competitor_traffic or 0,
        }

    def display_tags(self):
        """Public tag chips: glossary terms only (``is_term=True``)."""
        return self.tags.filter(is_term=True)

    def get_cluster_related(self, limit=3):
        """Published posts in the same topic cluster — pillar first, then siblings.

        Powers the cluster-aware "Continue Reading" rail so every pillar/spoke
        post links to its cluster mates. Rendered live, it is the self-reconciling
        structural half of the blog->blog internal-link graph. Returns an empty
        list when the post has no cluster.
        """
        if not self.topic_cluster_id:
            return []
        siblings = list(
            Post.objects.filter(
                status=Post.Status.PUBLISHED, topic_cluster_id=self.topic_cluster_id
            )
            .exclude(pk=self.pk)
            .select_related("author", "reviewer", "category")
            .prefetch_related("tags")
            .order_by("-published_at")
        )
        pillar_id = self.topic_cluster.pillar_id
        if pillar_id and pillar_id != self.pk:
            siblings.sort(key=lambda p: 0 if p.pk == pillar_id else 1)
        return siblings[:limit]


class PostTag(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="post_tags")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="post_tags")

    class Meta:
        db_table = "blog_post_tags"
        unique_together = [["post", "tag"]]


class UserIntent(models.Model):
    """Represents a user intent with a target URL for internal linking."""

    name = models.CharField(max_length=255, verbose_name="Intent name")
    target_url = models.URLField(max_length=500, unique=True, verbose_name="Target URL")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "blog_user_intent"
        verbose_name = "User intent"
        verbose_name_plural = "User intents"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Keyword(models.Model):
    """Keyword phrase linked to a user intent for automated internal linking."""

    intent = models.ForeignKey(
        UserIntent,
        on_delete=models.CASCADE,
        related_name="keywords",
        verbose_name="User intent",
    )
    phrase = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        verbose_name="Keyword phrase",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "blog_keyword"
        verbose_name = "Keyword"
        verbose_name_plural = "Keywords"
        ordering = ["phrase"]

    def __str__(self):
        return f"{self.phrase} → {self.intent.name}"


class Comment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        SPAM = "spam", "Spam"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blog_comments",
    )
    author_name = models.CharField(max_length=150, blank=True)
    author_email = models.EmailField(blank=True)
    body = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    depth = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "blog_comment"
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author_name or self.user} on {self.post}"


# Intent Frame (what a title does) -> the pipeline's search_intent enum. Kept
# local so a table-sourced worklist spec is identical to a workbook-sourced one.
_FRAME_TO_INTENT = {
    "what-is": "informational",
    "how-to": "informational",
    "guide": "informational",
    "best": "commercial",
    "compare": "commercial",
    "review": "commercial",
    "vs": "commercial",
}


class ContentPlan(models.Model):
    """The single source of truth for planned blog/news content — the production
    queue AND, via ``canonical_key``, the cross-run intent registry that prevents
    cannibalization over time.

    Every content-planning path deposits here (competitor top-pages, keyword
    clustering, landing-support ideation, YouTube/Twitter intake). The content
    pipeline reads ``planned`` / ``reconciled`` rows out of this table, generates
    them, and writes the produced ``Post`` + status back. So there is always one
    explicit, queryable production queue and a durable record of which user need
    each page owns.

    Internal/staff only — it carries NO public URL, so a row is never an
    indexable surface.

    The dedup spine: ``canonical_key`` is the controlled-vocabulary label of the
    user NEED. The persistent set of distinct ``canonical_key`` values across all
    rows IS the intent registry.
    """

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        RECONCILED = "reconciled", "Reconciled"
        GENERATING = "generating", "Generating"
        DRAFTED = "drafted", "Drafted"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"
        MERGED = "merged", "Merged (deduped)"

    class Source(models.TextChoices):
        TOP_PAGES = "top_pages", "Competitor Top Pages"
        KEYWORD_CLUSTERING = "keyword_clustering", "Keyword Clustering"
        IDEATION = "ideation", "Landing-Support Ideation"
        MANUAL = "manual", "Manual / Back-filled"
        YOUTUBE = "youtube", "YouTube Video Transcript"
        TWITTER = "twitter", "Twitter/X Post"

    class Role(models.TextChoices):
        PILLAR = "pillar", "Pillar"
        SPOKE = "spoke", "Spoke"

    class Target(models.TextChoices):
        BLOG = "blog", "Blog"
        NEWS = "news", "News"
        GLOSSARY_TERM = "glossary_term", "Glossary Term"

    class Feasibility(models.TextChoices):
        LLM_FULL = "llm_full", "LLM writes it fully"
        LLM_WITH_ASSETS = "llm_with_assets", "LLM writes + human supplies assets"
        HUMAN_ONLY = "human_only", "Human author only (brief handed off)"

    slug = models.SlugField(
        max_length=255,
        unique=True,
        help_text="Stable identity; equals the produced Post.slug. The upsert + resume key.",
    )
    canonical_key = models.SlugField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="Controlled-vocabulary key for the user NEED. Synonym needs share one "
        "key; the cross-run dedup spine is keyed on this.",
    )
    title = models.CharField(max_length=255)
    h1 = models.CharField(max_length=255, blank=True, default="")
    intent = models.TextField(blank=True, help_text="One-line user need this page satisfies.")
    role = models.CharField(max_length=10, choices=Role.choices, blank=True)
    target = models.CharField(max_length=16, choices=Target.choices, default=Target.BLOG)
    intent_frame = models.CharField(max_length=40, blank=True)
    entity = models.CharField(max_length=160, blank=True)
    observed_intent = models.TextField(
        blank=True,
        help_text="Intent derived from reading the real competitor pages (reconcile Layer 1).",
    )
    scope_includes = models.JSONField(default=list, blank=True)
    scope_excludes = models.JSONField(default=list, blank=True)
    canonical_owner = models.JSONField(
        default=dict,
        blank=True,
        help_text="Which spoke owns each shared asset (expectancy widget, stat, ...).",
    )
    competitor_traffic = models.PositiveIntegerField(null=True, blank=True)
    competitor_urls = models.JSONField(default=list, blank=True)
    keyword_volume = models.PositiveIntegerField(null=True, blank=True)
    keywords = models.JSONField(
        default=list,
        blank=True,
        help_text="Demand evidence from the keyword-clustering path: "
        '[{"keyword": str, "volume": int}, ...]. Flows into the author brief as '
        "intent-comprehension evidence (never a stuffing quota).",
    )
    brief = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured per-article author brief written by the brief stage "
        "(intent statement, essential/complementary elements, headings outline, "
        "keyword usage, SERP evidence). Empty dict = not briefed yet.",
    )
    feasibility = models.CharField(
        max_length=20,
        choices=Feasibility.choices,
        default=Feasibility.LLM_FULL,
        db_index=True,
        help_text="Brief-stage verdict on who can produce this content. "
        "'human_only' rows never enter the generation queue; their brief is the "
        "handoff to the human writer.",
    )
    priority = models.FloatField(null=True, blank=True, db_index=True)
    clarity = models.PositiveSmallIntegerField(null=True, blank=True)
    source_type = models.CharField(max_length=20, choices=Source.choices, db_index=True)
    source_ref = models.CharField(
        max_length=500,
        blank=True,
        help_text="Workbook path / run id the row was ingested from.",
    )
    youtube_url = models.URLField(
        max_length=500,
        blank=True,
        default="",
        help_text="For source_type=youtube: the source video. Copied onto the "
        "produced Post so the blog can link to or embed the original video.",
    )
    source_transcript = models.TextField(
        blank=True,
        default="",
        help_text="For source_type=youtube: the cleaned video transcript. Fed to the "
        "generator as the PRIMARY source material the article is written from.",
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PLANNED, db_index=True
    )
    topic_cluster = models.ForeignKey(
        TopicCluster,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_plans",
        help_text="The 1:1 content spine this planned content belongs to.",
    )
    categories = models.ManyToManyField(Category, related_name="content_plans", blank=True)
    markets = models.ManyToManyField(Market, related_name="content_plans", blank=True)
    audience_roles = models.ManyToManyField(AudienceRole, related_name="content_plans", blank=True)
    audience_levels = models.ManyToManyField(AudienceLevel, related_name="content_plans", blank=True)
    glossary_terms = models.ManyToManyField(
        Tag,
        related_name="planned_in",
        blank=True,
        limit_choices_to={"is_term": True},
        help_text="Glossary terms (is_term=True) this planned content will link to.",
    )
    produced_post = models.OneToOneField(
        "Post",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="content_plan",
        help_text="The Post generated from this plan row (set by content_import).",
    )
    produced_term = models.ForeignKey(
        Tag,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="produced_from_plans",
        limit_choices_to={"is_term": True},
        help_text="For target=glossary_term rows: the live Tag(is_term=True) this "
        "queued term became once authored + persisted.",
    )
    merged_into = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merged_rows",
        help_text="When status=merged, the surviving plan row this need was deduped into.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "blog_content_plan"
        ordering = ["-created_at"]
        verbose_name = "Content plan"
        verbose_name_plural = "Content plan"

    def __str__(self):
        return self.title or self.slug

    @property
    def is_produced(self) -> bool:
        """True once a Post (or, for term rows, a glossary Tag) exists for this row."""
        return self.produced_post_id is not None or self.produced_term_id is not None

    def to_worklist_spec(self) -> dict:
        """Project this row into the worklist-spec shape.

        Lets the generation workflow consume a table-sourced worklist identically
        to a workbook-sourced one. The caller must prefetch the M2M facets to
        avoid N+1 queries.
        """
        return {
            "topic_cluster": self.topic_cluster.name if self.topic_cluster_id else "",
            "topic_cluster_slug": self.topic_cluster.slug if self.topic_cluster_id else "",
            "title": self.title,
            "h1": self.h1,
            "intent": self.intent,
            "intent_frame": self.intent_frame,
            "search_intent": _FRAME_TO_INTENT.get(self.intent_frame, "informational"),
            "entity": self.entity,
            "content_type": self.target,
            "role": self.role,
            "categories": [c.name for c in self.categories.all()],
            "markets": [m.name for m in self.markets.all()],
            "audience_roles": [r.name for r in self.audience_roles.all()],
            "audience_levels": [lv.name for lv in self.audience_levels.all()],
            "glossary_terms": [t.name for t in self.glossary_terms.all()],
            "priority": self.priority or 0,
            "clarity": self.clarity or 0,
            "competitors": len(self.competitor_urls or []),
            "traffic": self.competitor_traffic or 0,
            "keyword_volume": self.keyword_volume or 0,
            "competitor_urls": list(self.competitor_urls or []),
            "keywords": list(self.keywords or []),
            "brief": self.brief or {},
            "feasibility": self.feasibility,
            "observed_intent": self.observed_intent,
            "canonical_key": self.canonical_key,
            "scope_includes": list(self.scope_includes or []),
            "scope_excludes": list(self.scope_excludes or []),
            "canonical_owner": self.canonical_owner or {},
            "source_type": self.source_type,
            "youtube_url": self.youtube_url,
            "source_transcript": self.source_transcript,
            "slug": self.slug,
            "content_id": self.slug,
            "produced": self.produced_post_id is not None,
        }


class ActiveNewsPostManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class NewsPost(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    excerpt = models.TextField(blank=True)
    key_takeaways = models.TextField(
        blank=True,
        help_text="Sanitized HTML for public display; generated from Key takeaways Markdown on save.",
    )
    key_takeaways_markdown_source = models.TextField(
        blank=True,
        default="",
        help_text="Markdown source for Key takeaways in the admin editor (round-trip).",
    )
    content_raw = models.TextField(
        blank=True,
        default="",
        help_text="Sanitized HTML produced from the Markdown editor (before auto-linking).",
    )
    content_markdown_source = models.TextField(
        blank=True,
        default="",
        help_text="Last Markdown source from the admin editor (round-trip; not shown publicly).",
    )
    content_rendered = models.TextField(
        blank=True,
        null=True,
        help_text="Final HTML with injected internal links. Populated by the auto-linker task.",
    )
    featured_image_url = models.URLField(max_length=500, blank=True)
    read_time_minutes = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    is_pipeline_generated = models.BooleanField(
        default=False,
        db_index=True,
        help_text=(
            "True when this article was produced by a content pipeline. "
            "Render flow skips HTML sanitization for these articles so that pipeline-emitted "
            "visual blocks (Mermaid, Chart.js canvases, custom HTML) survive."
        ),
    )
    author = models.ForeignKey(
        Author,
        on_delete=models.RESTRICT,
        related_name="news_posts",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="news_posts",
        limit_choices_to={"content_scope": ContentScope.NEWS},
        verbose_name="Primary topic",
        help_text="Auto-set to the first topic ticked in the editor; used for breadcrumbs and list cards.",
    )
    categories = models.ManyToManyField(
        Category,
        related_name="news_posts_multi",
        blank=True,
        limit_choices_to={"content_scope": ContentScope.NEWS},
        verbose_name="Topics",
        help_text="One or more topics. The first ticked topic is also stored as the primary topic.",
    )
    tags = models.ManyToManyField(
        Tag,
        through="NewsPostTag",
        related_name="news_posts",
        blank=True,
    )
    topic_cluster = models.ForeignKey(
        TopicCluster,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="news_posts",
        help_text="The topic cluster this article belongs to (the 1:1 content spine).",
    )
    markets = models.ManyToManyField(Market, related_name="news_posts", blank=True)
    audience_roles = models.ManyToManyField(AudienceRole, related_name="news_posts", blank=True)
    audience_levels = models.ManyToManyField(AudienceLevel, related_name="news_posts", blank=True)
    related_terms = models.ManyToManyField(
        Tag,
        related_name="referencing_news_posts",
        blank=True,
        limit_choices_to={"is_term": True},
        help_text="Glossary terms (is_term=True) this article links to.",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_news_posts",
    )

    objects = ActiveNewsPostManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "news_post"
        ordering = ["-published_at", "-created_at"]

    def __str__(self) -> str:
        return self.title

    def soft_delete(self, user=None):
        from django.utils import timezone

        self.is_deleted = True
        self.deleted_at = timezone.now()
        if user is not None and getattr(user, "pk", None):
            self.deleted_by = user
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])

    def get_read_time_minutes(self) -> int:
        if self.read_time_minutes and self.read_time_minutes > 0:
            return self.read_time_minutes
        content = self.content_rendered or self.content_raw or ""
        text = strip_tags(content)
        words = len(re.findall(r"\S+", text))
        return max(1, math.ceil(words / 200))

    @property
    def content(self) -> str:
        return self.content_rendered or self.content_raw or ""


class NewsPostTag(models.Model):
    news_post = models.ForeignKey(
        NewsPost,
        on_delete=models.CASCADE,
        related_name="news_post_tags",
    )
    tag = models.ForeignKey(
        Tag,
        on_delete=models.CASCADE,
        related_name="news_post_tags",
    )

    class Meta:
        db_table = "news_post_tags"
        unique_together = [["news_post", "tag"]]


class NewsComment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        SPAM = "spam", "Spam"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    news_post = models.ForeignKey(
        NewsPost,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="news_comments",
    )
    author_name = models.CharField(max_length=150, blank=True)
    author_email = models.EmailField(blank=True)
    body = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    depth = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "news_comment"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Comment by {self.author_name or self.user} on {self.news_post}"
