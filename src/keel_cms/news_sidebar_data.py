"""Pure queryset helpers for news sidebar widgets (used by views and sidebar cache)."""

from django.db.models import Count, Q

from .models import Category, ContentScope, NewsPost, Tag


def news_sidebar_categories():
    return Category.objects.filter(content_scope=ContentScope.NEWS).annotate(
        post_count=Count(
            "news_posts", filter=Q(news_posts__status=NewsPost.Status.PUBLISHED)
        )
    ).order_by("name")


def news_sidebar_top_tags(limit: int = 5):
    return (
        Tag.objects.annotate(
            post_count=Count(
                "news_posts", filter=Q(news_posts__status=NewsPost.Status.PUBLISHED)
            )
        )
        .filter(post_count__gt=0)
        .order_by("-post_count", "name")[:limit]
    )


def news_popular_posts_global(limit: int = 5):
    return list(
        NewsPost.objects.filter(status=NewsPost.Status.PUBLISHED)
        .select_related("author", "category")
        .order_by("-published_at")[:limit]
    )
