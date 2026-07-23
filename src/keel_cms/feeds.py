"""RSS 2.0 feed for the blog.

Exposes the most recently published posts using Django's syndication framework.
Item and channel links resolve to absolute URLs via the request host, so the feed
is valid for external readers without hard-coding a domain. The feed title /
description read the brand string from ``KEEL_CMS["site_name"]``.
"""
from django.contrib.syndication.views import Feed
from django.urls import reverse
from django.utils.feedgenerator import Rss201rev2Feed

from .config import cms_setting
from .models import Post

FEED_ITEM_LIMIT = 50


class BlogFeedGenerator(Rss201rev2Feed):
    """RSS 2.0 served as ``text/xml`` instead of ``application/rss+xml``.

    Browsers render their native, indented, collapsible XML viewer for
    ``text/xml``/``application/xml`` documents, but dump raw one-line source for
    ``application/rss+xml`` — so this content type is what gives a clean in-browser
    view. The RSS structure is byte-for-byte unchanged and every feed reader
    accepts ``text/xml`` identically.
    """

    content_type = "text/xml; charset=utf-8"


class BlogRssFeed(Feed):
    feed_type = BlogFeedGenerator

    @property
    def title(self):
        name = cms_setting("site_name")
        return f"{name} Blog".strip() if name else "Blog"

    @property
    def description(self):
        name = cms_setting("site_name")
        return f"Latest posts from {name}.".strip() if name else "Latest posts."

    def link(self):
        return reverse("keel_cms:post_list")

    def items(self):
        return (
            Post.objects.filter(status=Post.Status.PUBLISHED)
            .select_related("author", "category")
            .order_by("-published_at")[:FEED_ITEM_LIMIT]
        )

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.meta_description or item.excerpt or ""

    def item_link(self, item):
        return reverse("keel_cms:post_detail", kwargs={"slug": item.slug})

    # No item_guid override: the syndication framework then defaults the GUID to
    # the item's link *after* domain-prefixing, so the guid is a full absolute URL.
    item_guid_is_permalink = True

    def item_pubdate(self, item):
        return item.published_at

    def item_author_name(self, item):
        return item.author.name if item.author_id else None

    def item_categories(self, item):
        return [item.category.name] if item.category_id else []
