"""Short-lived cache for news sidebar querysets; invalidated on content changes (see keel_cms.signals)."""

from __future__ import annotations

from django.core.cache import cache

from .news_sidebar_data import (
    news_popular_posts_global,
    news_sidebar_categories,
    news_sidebar_top_tags,
)

NEWS_SIDEBAR_CATEGORIES_KEY = "news:sidebar:categories:v1"
NEWS_SIDEBAR_TOP_TAGS_KEY = "news:sidebar:top_tags:v1"
NEWS_SIDEBAR_POPULAR_GLOBAL_KEY = "news:sidebar:popular_global:v1"

_SIDEBAR_TTL_SECONDS = 600


def invalidate_news_sidebar_cache() -> None:
    cache.delete_many(
        [
            NEWS_SIDEBAR_CATEGORIES_KEY,
            NEWS_SIDEBAR_TOP_TAGS_KEY,
            NEWS_SIDEBAR_POPULAR_GLOBAL_KEY,
        ]
    )


def get_news_sidebar_categories():
    data = cache.get(NEWS_SIDEBAR_CATEGORIES_KEY)
    if data is None:
        data = list(news_sidebar_categories())
        cache.set(NEWS_SIDEBAR_CATEGORIES_KEY, data, _SIDEBAR_TTL_SECONDS)
    return data


def get_news_sidebar_top_tags(limit: int = 5):
    data = cache.get(NEWS_SIDEBAR_TOP_TAGS_KEY)
    if data is None:
        data = list(news_sidebar_top_tags(limit))
        cache.set(NEWS_SIDEBAR_TOP_TAGS_KEY, data, _SIDEBAR_TTL_SECONDS)
    return data


def get_news_popular_posts_global(limit: int = 5):
    data = cache.get(NEWS_SIDEBAR_POPULAR_GLOBAL_KEY)
    if data is None:
        data = news_popular_posts_global(limit)
        cache.set(NEWS_SIDEBAR_POPULAR_GLOBAL_KEY, data, _SIDEBAR_TTL_SECONDS)
    return data
