"""Content sitemaps — blog posts, news articles, and desk/topic/tag archives.

Companion to keel-seo's ``LandingSitemap``: a host composes its full ``sitemaps``
dict from ``LandingSitemap`` (money pages) plus the content buckets built here.
The convenience ``all_sitemaps()`` does that composition when keel-seo is
installed; ``content_sitemaps()`` returns only the content buckets for a host
that owns its landing sitemap separately.

Every bucket lists only **indexable** URLs, so the sitemap never disagrees with a
page's robots meta:

* ``BlogPostSitemap``   — published blog posts.
* ``NewsPostSitemap``   — published news articles.
* ``DeskArchiveSitemap`` / ``TopicArchiveSitemap`` / ``TagArchiveSitemap`` —
  editorial-desk / blog-category / tag archives, but only once they list more
  than ``archive_min_contents - 1`` published contents (the same thin-content
  rule that gates their on-page robots meta). The threshold is
  ``KEEL_CMS["archive_min_contents"]`` (default 4 → "more than 3").

Regeneration is automatic: every request to the sitemap view reads current DB
state, so publishing a post or toggling a flag is reflected on the next fetch —
no cron, no rebuild step.

URLs resolve through the ``keel_cms`` URL namespace, which the host maps to its
real serving paths (``keel_cms.contrib.urls`` is the reference wiring; a host that
serves blog/news at other paths registers its own ``app_name = "keel_cms"``
aliases at those paths). A bucket whose URL name is not registered on the host is
emitted empty rather than raising, so a host with no topic/desk/tag pages simply
omits those buckets without any per-project sitemap code.

URL ordering: posts newest-first (``-published_at``); archives alphabetical by
slug. Field emission (``changefreq`` / ``priority`` / ``lastmod``) matches the
Django sitemap defaults the source projects already published.
"""
from django.contrib.sitemaps import Sitemap
from django.db.models import Count, Q
from django.urls import NoReverseMatch, reverse

from .config import archive_min_contents


def _resolvable(name: str) -> bool:
    """Whether a slug-taking ``keel_cms`` detail route is registered on the host.

    Probed with a throwaway slug so an unregistered bucket degrades to empty
    instead of raising ``NoReverseMatch`` mid-render.
    """
    try:
        reverse(name, kwargs={"slug": "_probe"})
        return True
    except NoReverseMatch:
        return False


class _PostSitemapBase(Sitemap):
    """Published article pages (blog + news), which are indexable."""

    changefreq = "weekly"
    priority = 0.7

    def lastmod(self, obj):
        return getattr(obj, "updated_at", None) or getattr(obj, "published_at", None)


class BlogPostSitemap(_PostSitemapBase):
    def items(self):
        if not _resolvable("keel_cms:post_detail"):
            return []
        from .models import Post

        return list(
            Post.objects.filter(status=Post.Status.PUBLISHED).order_by("-published_at")
        )

    def location(self, obj) -> str:
        return reverse("keel_cms:post_detail", kwargs={"slug": obj.slug})


class NewsPostSitemap(_PostSitemapBase):
    def items(self):
        if not _resolvable("keel_cms:news_post_detail"):
            return []
        from .models import NewsPost

        return list(
            NewsPost.objects.filter(status=NewsPost.Status.PUBLISHED).order_by(
                "-published_at"
            )
        )

    def location(self, obj) -> str:
        return reverse("keel_cms:news_post_detail", kwargs={"slug": obj.slug})


class _ArchiveSitemapBase(Sitemap):
    """Author / category / tag archives — included only once they list more than
    ``archive_min_contents - 1`` published contents, matching the on-page
    thin-content robots-meta rule."""

    changefreq = "weekly"
    priority = 0.4


class DeskArchiveSitemap(_ArchiveSitemapBase):
    """Editorial-desk author pages — Board reviewer rows excluded; only desks
    listing at least ``archive_min_contents`` published posts are indexed."""

    def items(self):
        if not _resolvable("keel_cms:team_desk"):
            return []
        from .models import Author, Post

        return list(
            Author.objects.filter(is_reviewer=False)
            .annotate(
                n=Count(
                    "posts",
                    filter=Q(
                        posts__status=Post.Status.PUBLISHED, posts__is_deleted=False
                    ),
                )
            )
            .filter(n__gte=archive_min_contents())
            .order_by("slug")
        )

    def location(self, obj) -> str:
        return reverse("keel_cms:team_desk", kwargs={"slug": obj.slug})


class TopicArchiveSitemap(_ArchiveSitemapBase):
    """Blog-category (topic) archives — only categories in the BLOG scope with at
    least ``archive_min_contents`` published posts are indexed."""

    def items(self):
        if not _resolvable("keel_cms:topic_list"):
            return []
        from .models import Category, ContentScope, Post

        return list(
            Category.objects.filter(content_scope=ContentScope.BLOG)
            .annotate(
                n=Count(
                    "posts_multi",
                    filter=Q(
                        posts_multi__status=Post.Status.PUBLISHED,
                        posts_multi__is_deleted=False,
                    ),
                )
            )
            .filter(n__gte=archive_min_contents())
            .order_by("slug")
        )

    def location(self, obj) -> str:
        return reverse("keel_cms:topic_list", kwargs={"slug": obj.slug})


class TagArchiveSitemap(_ArchiveSitemapBase):
    """Tag archives (non-glossary tags) whose combined blog + news published
    content count is at least ``archive_min_contents``."""

    def items(self):
        if not _resolvable("keel_cms:tag_detail"):
            return []
        from .models import NewsPost, Post, Tag

        threshold = archive_min_contents()
        tags = Tag.objects.filter(is_term=False).annotate(
            blog_n=Count(
                "posts",
                filter=Q(posts__status=Post.Status.PUBLISHED, posts__is_deleted=False),
                distinct=True,
            ),
            news_n=Count(
                "news_posts",
                filter=Q(
                    news_posts__status=NewsPost.Status.PUBLISHED,
                    news_posts__is_deleted=False,
                ),
                distinct=True,
            ),
        )
        return sorted(
            (t for t in tags if (t.blog_n + t.news_n) >= threshold),
            key=lambda t: t.slug,
        )

    def location(self, obj) -> str:
        return reverse("keel_cms:tag_detail", kwargs={"slug": obj.slug})


def content_sitemaps() -> dict:
    """The ordered content buckets a host merges into its ``sitemaps`` dict.

    Order (blog posts → news → desk → topic → tag) and section keys are stable so
    a host's composed sitemap output is deterministic across releases.
    """
    return {
        "blog-posts": BlogPostSitemap,
        "news-posts": NewsPostSitemap,
        "blog-desks": DeskArchiveSitemap,
        "blog-topics": TopicArchiveSitemap,
        "tags": TagArchiveSitemap,
    }


def all_sitemaps() -> dict:
    """Landing sitemap (keel-seo) + content buckets, ready to hand to the Django
    ``sitemap`` view. Falls back to just the content buckets if keel-seo is not
    installed, so keel-cms carries no hard dependency on it.
    """
    sitemaps = {}
    try:
        from keel_seo.sitemaps import LandingSitemap

        sitemaps["landings"] = LandingSitemap
    except Exception:
        pass
    sitemaps.update(content_sitemaps())
    return sitemaps
