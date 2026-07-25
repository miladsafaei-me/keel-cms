"""Opt-in Django admin registration for the keel-cms content models.

keel-cms ships the models but no admin so a host can wire its own add/edit forms
(including the 3-tab body editor). ``register()`` provides plain, authorable-out-of-
the-box registrations: slug fields are prepopulated and the editorial models get
sensible list columns/filters.

This module NEVER auto-registers at import time. Registration is opt-in and gated by
the ``KEEL_CMS_CONTRIB_ADMIN`` setting (default False), wired through
``KeelCmsContribConfig.ready()`` in ``apps.py``. A host may also call ``register()``
directly. ``register()`` is idempotent: models already registered are skipped, so a
double call (setting + explicit) does not raise.
"""

from __future__ import annotations

from django.contrib import admin

from keel_cms.models import (
    Author,
    Category,
    ContentPlan,
    Market,
    NewsPost,
    Post,
    Tag,
    TopicCluster,
)


class AuthorAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "role", "is_active")
    list_filter = ("is_active", "is_reviewer")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "content_scope")
    list_filter = ("content_scope",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_term", "parent_category")
    list_filter = ("is_term",)
    search_fields = ("name", "slug", "abbreviation")
    prepopulated_fields = {"slug": ("name",)}


class MarketAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class TopicClusterAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "status")
    list_filter = ("status",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "status", "author", "category", "published_at")
    list_filter = ("status", "category")
    search_fields = ("title", "slug")
    date_hierarchy = "published_at"
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("author", "category")


class NewsPostAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "status", "author", "category", "published_at")
    list_filter = ("status", "category")
    search_fields = ("title", "slug")
    date_hierarchy = "published_at"
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("author", "category")


class ContentPlanAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "status")
    list_filter = ("status",)
    search_fields = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}


_REGISTRY = (
    (Author, AuthorAdmin),
    (Category, CategoryAdmin),
    (Tag, TagAdmin),
    (Market, MarketAdmin),
    (TopicCluster, TopicClusterAdmin),
    (Post, PostAdmin),
    (NewsPost, NewsPostAdmin),
    (ContentPlan, ContentPlanAdmin),
)


def register(site: admin.AdminSite | None = None) -> None:
    """Register the keel-cms content models on ``site`` (default: the global admin).

    Idempotent — models already registered on the target site are skipped, so this
    is safe to call more than once (e.g. via the AppConfig hook and a host call).
    """
    target = site or admin.site
    for model, model_admin in _REGISTRY:
        if not target.is_registered(model):
            target.register(model, model_admin)
