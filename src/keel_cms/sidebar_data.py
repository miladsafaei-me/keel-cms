"""Pure queryset helpers for blog sidebar widgets (used by views and sidebar cache)."""

from django.db.models import Count, Q, Sum

from .models import Category, ContentScope, Post, Tag


# A post is "published content" only when it is published AND not soft-deleted.
# The Count aggregate joins the M2M directly (it does not pass through
# ActivePostManager), so is_deleted must be excluded explicitly.
_LIVE_POST = Q(posts__status=Post.Status.PUBLISHED, posts__is_deleted=False)


def blog_sidebar_categories():
    """Explore Topics: blog topics that actually have live published content (no empty links)."""
    return (
        Category.objects.filter(content_scope=ContentScope.BLOG)
        .annotate(post_count=Count("posts", filter=_LIVE_POST))
        .filter(post_count__gt=0)
        .order_by("name")
    )


def blog_sidebar_top_tags(limit: int = 5):
    """Popular Tags: glossary terms (is_term=True) with live published posts, ranked by
    popularity — the total views of the posts carrying each tag (post count is the
    tiebreak). Blog tags are drawn exclusively from the glossary vocabulary, so
    non-glossary rows never list."""
    return (
        Tag.objects.filter(is_term=True)
        .annotate(
            post_count=Count("posts", filter=_LIVE_POST),
            total_views=Sum("posts__view_count", filter=_LIVE_POST),
        )
        .filter(post_count__gt=0)
        .order_by("-total_views", "-post_count", "name")[:limit]
    )


def blog_popular_posts_global(limit: int = 5):
    """Popular Insights: most-viewed live published posts (recency breaks ties)."""
    return list(
        Post.objects.filter(status=Post.Status.PUBLISHED)
        .select_related("author", "category")
        .order_by("-view_count", "-published_at")[:limit]
    )
