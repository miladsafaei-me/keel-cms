"""Short-lived cache for blog sidebar querysets; invalidated on content changes (see keel_cms.signals)."""

from __future__ import annotations

from django.core.cache import cache

from .sidebar_data import (
    blog_popular_posts_global,
    blog_sidebar_categories,
    blog_sidebar_top_tags,
)

BLOG_SIDEBAR_CATEGORIES_KEY = "blog:sidebar:categories:v1"
BLOG_SIDEBAR_TOP_TAGS_KEY = "blog:sidebar:top_tags:v1"
BLOG_SIDEBAR_POPULAR_GLOBAL_KEY = "blog:sidebar:popular_global:v1"

_SIDEBAR_TTL_SECONDS = 600


def invalidate_blog_sidebar_cache() -> None:
    cache.delete_many(
        [
            BLOG_SIDEBAR_CATEGORIES_KEY,
            BLOG_SIDEBAR_TOP_TAGS_KEY,
            BLOG_SIDEBAR_POPULAR_GLOBAL_KEY,
        ]
    )


def get_blog_sidebar_categories():
    data = cache.get(BLOG_SIDEBAR_CATEGORIES_KEY)
    if data is None:
        data = list(blog_sidebar_categories())
        cache.set(BLOG_SIDEBAR_CATEGORIES_KEY, data, _SIDEBAR_TTL_SECONDS)
    return data


def get_blog_sidebar_top_tags(limit: int = 5):
    key = BLOG_SIDEBAR_TOP_TAGS_KEY
    data = cache.get(key)
    if data is None:
        data = list(blog_sidebar_top_tags(limit))
        cache.set(key, data, _SIDEBAR_TTL_SECONDS)
    return data


def get_blog_popular_posts_global(limit: int = 5):
    key = BLOG_SIDEBAR_POPULAR_GLOBAL_KEY
    data = cache.get(key)
    if data is None:
        data = blog_popular_posts_global(limit)
        cache.set(key, data, _SIDEBAR_TTL_SECONDS)
    return data
