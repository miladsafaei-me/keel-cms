"""Admin OS forms for the keel-cms content models.

Generalized from the source project's admin_os forms: the same three-tab body
editor contract (``content_markdown`` / ``content_html`` / ``content_format``) and
the same tag-as-glossary-term resolution, but every import points at
``keel_cms`` and nothing couples to a specific brand or a Celery re-render task.
Re-rendering ``content_rendered`` is left to the host (persist hook / a post_save
signal) — the forms only write ``content_markdown_source`` + ``content_raw``.
"""
from __future__ import annotations

import json
import logging
import re

from django import forms
from django.utils.text import slugify

from keel_cms.models import Author, Category, ContentScope, NewsPost, Post, Tag

logger = logging.getLogger(__name__)

SOCIAL_PLATFORMS = ["twitter", "linkedin", "github", "instagram", "telegram", "youtube"]


def _strip_nul(value: str) -> str:
    return value.replace("\x00", "") if value else value


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "slug", "description", "content_scope"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "ta-input", "placeholder": "e.g. Trading Strategies"}),
            "slug": forms.TextInput(attrs={"class": "ta-input", "placeholder": "trading-strategies"}),
            "description": forms.Textarea(
                attrs={"class": "ta-textarea", "placeholder": "Brief description of this topic...", "rows": 4}
            ),
            "content_scope": forms.Select(attrs={"class": "ta-select"}),
        }

    def __init__(self, *args, content_scope: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].required = False
        if content_scope is not None and not (self.instance and self.instance.pk):
            self.fields["content_scope"].initial = content_scope
        if self.instance and self.instance.pk:
            self.fields["content_scope"].disabled = True

    def clean_slug(self) -> str:
        slug = (self.cleaned_data.get("slug") or "").strip().lower()
        name = self.cleaned_data.get("name", "")
        if not slug and name:
            slug = slugify(name)
        elif slug:
            slug = slugify(slug) or slug
        return slug or ""

    def clean_content_scope(self) -> str:
        if self.instance and self.instance.pk:
            return self.instance.content_scope
        return self.cleaned_data.get("content_scope") or ContentScope.BLOG

    def clean(self):
        cleaned = super().clean()
        slug = (cleaned.get("slug") or "").strip()
        scope = cleaned.get("content_scope") or ContentScope.BLOG
        if not slug:
            return cleaned
        qs = Category.objects.filter(slug=slug, content_scope=scope)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                "A topic with this slug already exists for this section (blog or news)."
            )
        return cleaned


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ["name", "slug"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "ta-input", "placeholder": "e.g. Risk Management"}),
            "slug": forms.TextInput(attrs={"class": "ta-input", "placeholder": "risk-management"}),
        }

    def clean_slug(self) -> str:
        slug = (self.cleaned_data.get("slug") or "").strip().lower()
        name = self.cleaned_data.get("name", "")
        if not slug and name:
            slug = slugify(name)
        elif slug:
            slug = slugify(slug) or slug
        return slug or ""

    def clean(self):
        cleaned = super().clean()
        slug = (cleaned.get("slug") or "").strip()
        if not slug:
            return cleaned
        qs = Tag.objects.filter(slug=slug)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A tag with this slug already exists.")
        return cleaned


def _set_body(instance, cleaned) -> None:
    """Set ``content_markdown_source`` + ``content_raw`` from the three-tab editor
    fields, honoring ``content_format`` (which view the operator last authored in).

    - ``html``: the HTML / Preview tab is authoritative. Store that HTML (sanitized
      for hand-authored posts; kept verbatim for pipeline posts whose Mermaid /
      Chart.js / custom blocks the sanitizer would strip) and refresh the Markdown
      source from it so the Markdown tab matches.
    - anything else (default / empty): the Markdown tab is authoritative; convert
      Markdown to HTML for ``content_raw``.

    An empty ``content_format`` means the operator authored in no tab this save, so
    the stored body is left exactly as it was.
    """
    from keel_cms.markdown_convert import (
        html_to_markdown_for_edit,
        prepare_blog_content_for_storage,
        prepare_pipeline_content_for_storage,
    )

    is_pipeline = bool(getattr(instance, "is_pipeline_generated", False))
    fmt = (cleaned.get("content_format") or "").strip().lower()
    md = cleaned.get("content_markdown") or ""
    html_src = cleaned.get("content_html") or ""

    if fmt not in ("html", "markdown"):
        return

    if fmt == "html":
        html_clean = _strip_nul(html_src)
        if not is_pipeline:
            from keel_cms.html_sanitize import sanitize_blog_html

            html_clean = sanitize_blog_html(html_clean)
        instance.content_raw = html_clean
        try:
            instance.content_markdown_source = _strip_nul(html_to_markdown_for_edit(html_clean))
        except Exception:
            instance.content_markdown_source = _strip_nul(md)
    else:
        body_prep = (
            prepare_pipeline_content_for_storage if is_pipeline
            else prepare_blog_content_for_storage
        )
        instance.content_markdown_source = _strip_nul(md)
        instance.content_raw = body_prep(md)


def _seed_editor_html(instance, md_initial: str) -> str:
    """HTML that seeds the editor's HTML / Preview tabs on load (auto-convert-on-load).

    Prefer the stored ``content_raw``; if it is empty but a Markdown source exists
    (an imported-but-never-rendered post), convert it once so the form always loads
    with all three tabs populated and no manual "Convert" step.
    """
    existing = _strip_nul(getattr(instance, "content_raw", "") or "")
    if existing.strip():
        return existing
    md = _strip_nul(md_initial or "")
    if not md.strip():
        return ""
    try:
        from keel_cms.markdown_convert import (
            prepare_blog_content_for_storage,
            prepare_pipeline_content_for_storage,
        )

        conv = (
            prepare_pipeline_content_for_storage
            if getattr(instance, "is_pipeline_generated", False)
            else prepare_blog_content_for_storage
        )
        return _strip_nul(conv(md))
    except Exception:
        logger.exception("content editor: could not auto-convert Markdown to HTML on load.")
        return ""


class _BaseContentForm(forms.ModelForm):
    """Shared three-tab editor fields + tag/topic handling for Post and NewsPost."""

    _content_scope = ContentScope.BLOG

    content_markdown = forms.CharField(
        required=False,
        label="Content (Markdown)",
        widget=forms.Textarea(
            attrs={
                "class": "editor-area markdown-editor-source",
                "placeholder": "# Title\n\nUse **Markdown**: lists, [links](https://…), ```code```, tables.",
                "rows": 22,
            }
        ),
    )
    content_html = forms.CharField(
        required=False,
        label="Content (HTML)",
        widget=forms.Textarea(attrs={"class": "ce-html-source", "spellcheck": "false", "rows": 24}),
    )
    content_format = forms.CharField(required=False, widget=forms.HiddenInput())
    tag_names = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "tag-names-input"}),
        help_text="Comma-separated glossary-term names.",
    )
    key_takeaways_markdown = forms.CharField(
        required=False,
        label="Key takeaways (Markdown)",
        widget=forms.Textarea(
            attrs={
                "class": "ta-input min-h-40",
                "placeholder": "- First point\n- Second point",
                "rows": 5,
            }
        ),
    )
    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "h-4 w-4 shrink-0 rounded border-gray-300 text-brand-500 focus:ring-2 focus:ring-brand-500/30"}
        ),
        label="Topics",
        help_text="Tick one or more topics. The first ticked topic becomes the primary topic.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].validators = []
        if self.instance and self.instance.pk:
            if getattr(self.instance, "is_pipeline_generated", False):
                self.fields["content_markdown"].help_text = (
                    "This content was produced by a pipeline. Editing the Markdown re-runs "
                    "the sanitizer on save, which can strip generated visual blocks "
                    "(Mermaid, Chart.js, custom HTML)."
                )
            self.fields["tag_names"].initial = ", ".join(t.name for t in self.instance.tags.all())
            self._seed_markdown_initial()
            self._seed_key_takeaways_initial()
        self.fields["published_at"].required = False
        self.fields["featured_image_url"].required = False
        self.fields["excerpt"].required = False
        self.fields["key_takeaways_markdown"].required = False
        self.fields["meta_title"].required = False
        if "meta_description" in self.fields:
            self.fields["meta_description"].required = False
        if not self.instance.pk and not self.data and "author" not in self.initial:
            first_author = Author.objects.order_by("name").first()
            if first_author is not None:
                self.fields["author"].initial = first_author.pk
        self.fields["categories"].queryset = Category.objects.filter(
            content_scope=self._content_scope
        ).order_by("name")
        if self.instance and self.instance.pk:
            self.fields["categories"].initial = list(
                self.instance.categories.values_list("pk", flat=True)
            )
        elif self.instance and getattr(self.instance, "category_id", None):
            self.fields["categories"].initial = [self.instance.category_id]
        self.fields["content_html"].initial = _seed_editor_html(
            self.instance, self.fields["content_markdown"].initial
        )
        self.fields["content_format"].initial = ""

    def _seed_markdown_initial(self) -> None:
        stored_md = (getattr(self.instance, "content_markdown_source", None) or "").strip()
        raw_body = self.instance.content_raw or ""
        if stored_md:
            self.fields["content_markdown"].initial = _strip_nul(stored_md)
            return
        try:
            from keel_cms.markdown_convert import html_to_markdown_for_edit

            self.fields["content_markdown"].initial = _strip_nul(html_to_markdown_for_edit(raw_body))
        except Exception:
            logger.exception("content editor: could not prepare Markdown initial; using raw body.")
            self.fields["content_markdown"].initial = _strip_nul(raw_body)

    def _seed_key_takeaways_initial(self) -> None:
        stored_kt_md = (getattr(self.instance, "key_takeaways_markdown_source", None) or "").strip()
        kt_html = (getattr(self.instance, "key_takeaways", None) or "").strip()
        if stored_kt_md:
            self.fields["key_takeaways_markdown"].initial = _strip_nul(stored_kt_md)
        elif kt_html:
            try:
                from keel_cms.markdown_convert import html_to_markdown_for_edit

                self.fields["key_takeaways_markdown"].initial = _strip_nul(
                    html_to_markdown_for_edit(kt_html)
                )
            except Exception:
                logger.exception("content editor: could not prepare key takeaways initial.")

    def clean_slug(self) -> str:
        raw = (self.cleaned_data.get("slug") or "").strip()
        if not raw:
            return ""
        s = re.sub(r"\s+", "-", raw)
        s = re.sub(r"-+", "-", s).strip("-")
        return slugify(s) or s

    def save(self, commit=True):
        from keel_cms.markdown_convert import prepare_blog_content_for_storage

        instance = super().save(commit=False)
        selected_categories = list(self.cleaned_data.get("categories") or [])
        instance.category = selected_categories[0] if selected_categories else None
        md_kt = self.cleaned_data.get("key_takeaways_markdown") or ""
        instance.key_takeaways_markdown_source = _strip_nul(md_kt)
        instance.key_takeaways = (
            prepare_blog_content_for_storage(md_kt) if md_kt.strip() else ""
        )
        _set_body(instance, self.cleaned_data)
        if commit:
            instance.save()
            instance.categories.set(selected_categories)
            tag_names = self.cleaned_data.get("tag_names", "")
            names = [n.strip() for n in tag_names.split(",") if n.strip()] if tag_names else []
            instance.tags.set(Tag.resolve_existing_terms(names))
        return instance


class PostForm(_BaseContentForm):
    _content_scope = ContentScope.BLOG

    class Meta:
        model = Post
        fields = [
            "title",
            "slug",
            "excerpt",
            "status",
            "layout",
            "author",
            "reviewer",
            "published_at",
            "featured_image_url",
            "youtube_url",
            "meta_title",
            "meta_description",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "title-input", "placeholder": "Enter post title here..."}),
            "slug": forms.TextInput(attrs={"class": "ta-input", "placeholder": "post-title-slug"}),
            "excerpt": forms.Textarea(attrs={"class": "ta-textarea min-h-40", "placeholder": "A brief summary for search engines and blog grids...", "rows": 6}),
            "status": forms.Select(attrs={"class": "ta-select"}),
            "layout": forms.RadioSelect(),
            "author": forms.Select(attrs={"class": "ta-select"}),
            "reviewer": forms.Select(attrs={"class": "ta-select"}),
            "published_at": forms.DateTimeInput(attrs={"class": "ta-input", "type": "datetime-local"}),
            "featured_image_url": forms.URLInput(attrs={"class": "ta-input", "placeholder": "https://..."}),
            "youtube_url": forms.URLInput(attrs={"class": "ta-input", "placeholder": "https://www.youtube.com/watch?v=..."}),
            "meta_title": forms.TextInput(attrs={"class": "ta-input", "placeholder": "SEO title (optional)"}),
            "meta_description": forms.Textarea(attrs={"class": "ta-textarea", "placeholder": "SEO meta description (optional)", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reviewer"].required = False
        self.fields["reviewer"].empty_label = "No reviewer"
        self.fields["reviewer"].queryset = Author.objects.filter(
            is_active=True, is_reviewer=True
        ).order_by("name")


class NewsPostForm(_BaseContentForm):
    _content_scope = ContentScope.NEWS

    class Meta:
        model = NewsPost
        fields = [
            "title",
            "slug",
            "excerpt",
            "status",
            "author",
            "published_at",
            "featured_image_url",
            "meta_title",
            "meta_description",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "title-input", "placeholder": "Enter headline here..."}),
            "slug": forms.TextInput(attrs={"class": "ta-input", "placeholder": "article-url-slug"}),
            "excerpt": forms.Textarea(attrs={"class": "ta-textarea min-h-40", "placeholder": "A brief summary for search engines and listing grids...", "rows": 6}),
            "status": forms.Select(attrs={"class": "ta-select"}),
            "author": forms.Select(attrs={"class": "ta-select"}),
            "published_at": forms.DateTimeInput(attrs={"class": "ta-input", "type": "datetime-local"}),
            "featured_image_url": forms.URLInput(attrs={"class": "ta-input", "placeholder": "https://..."}),
            "meta_title": forms.TextInput(attrs={"class": "ta-input", "placeholder": "SEO title (optional)"}),
            "meta_description": forms.Textarea(attrs={"class": "ta-textarea", "placeholder": "SEO meta description (optional)", "rows": 3}),
        }


class AuthorForm(forms.ModelForm):
    custom_socials = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={"id": "custom-socials-input"}),
    )
    is_active = forms.TypedChoiceField(
        choices=[(True, "Active (Public)"), (False, "Inactive (Hidden)")],
        coerce=lambda x: str(x).lower() == "true",
        widget=forms.Select(attrs={"class": "ta-select"}),
    )
    is_reviewer = forms.TypedChoiceField(
        required=False,
        choices=[(False, "No"), (True, "Yes — show in reviewer dropdown")],
        coerce=lambda x: str(x).lower() == "true",
        widget=forms.Select(attrs={"class": "ta-select"}),
        label="Eligible as reviewer",
    )

    class Meta:
        model = Author
        fields = ["name", "role", "email", "slug", "bio", "avatar_url"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "ta-input", "placeholder": "e.g. Alex Mercer"}),
            "role": forms.TextInput(attrs={"class": "ta-input", "placeholder": "e.g. Senior Editor"}),
            "email": forms.EmailInput(attrs={"class": "ta-input", "placeholder": "alex@example.com"}),
            "slug": forms.TextInput(attrs={"class": "ta-input", "placeholder": "alex-mercer"}),
            "bio": forms.Textarea(attrs={"class": "ta-input", "placeholder": "Write a brief professional background...", "rows": 4}),
            "avatar_url": forms.URLInput(attrs={"class": "ta-input", "placeholder": "https://..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = False
        self.fields["role"].required = False
        self.fields["bio"].required = False
        self.fields["avatar_url"].required = False
        self.fields["is_active"].initial = getattr(self.instance, "is_active", True)
        self.fields["is_reviewer"].initial = getattr(self.instance, "is_reviewer", False)
        links = self.instance.social_links or {}
        placeholders = {
            "twitter": "https://twitter.com/username",
            "linkedin": "https://linkedin.com/in/username",
            "github": "https://github.com/username",
            "instagram": "https://instagram.com/username",
            "telegram": "https://t.me/username",
            "youtube": "https://youtube.com/@username",
        }
        for platform in SOCIAL_PLATFORMS:
            self.fields[f"{platform}_url"] = forms.URLField(
                required=False,
                widget=forms.URLInput(
                    attrs={"class": "ta-input", "placeholder": placeholders.get(platform, f"https://{platform}.com/...")}
                ),
            )
            self.fields[f"{platform}_url"].initial = links.get(platform, "")
        if self.instance and self.instance.social_links:
            self.fields["custom_socials"].initial = json.dumps(
                self.instance.social_links.get("custom", [])
            )

    def clean_slug(self) -> str:
        slug = (self.cleaned_data.get("slug") or "").strip().lower()
        name = self.cleaned_data.get("name", "")
        if not slug and name:
            slug = slugify(name)
        elif slug:
            slug = slugify(slug) or slug
        return slug or ""

    def save(self, commit=True):
        instance = super().save(commit=commit)
        instance.is_active = self.cleaned_data.get("is_active", True)
        instance.is_reviewer = self.cleaned_data.get("is_reviewer", False)
        links = {}
        for platform in SOCIAL_PLATFORMS:
            url = self.cleaned_data.get(f"{platform}_url", "")
            if url:
                links[platform] = url
        custom_json = self.cleaned_data.get("custom_socials", "[]")
        try:
            links["custom"] = json.loads(custom_json) if custom_json else []
        except json.JSONDecodeError:
            links["custom"] = []
        instance.social_links = links
        if commit:
            instance.save(update_fields=["social_links", "is_active", "is_reviewer"])
        return instance
