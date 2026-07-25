"""Opt-in public content views for keel-cms.

Thin presentation over the keel-cms engine: every query runs against keel-cms's
shared taxonomy models, and the glossary pages reuse keel-cms's context builders
verbatim. Templates render under the ``keel_cms/`` namespace, so a host overrides
any page by shadowing the same template path. All list queries are scoped to
published, non-deleted rows, so an empty database renders empty pages rather than
erroring. The brand string comes from the ``KEEL_CMS`` config (``site_name``); no
consumer-specific business logic lives here.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404, render

from keel_cms.config import site_name
from keel_cms.models import Author, Category, ContentScope, NewsPost, Post, Tag
from keel_cms.trading_glossary import (
    trading_glossary_index_context,
    trading_glossary_term_context,
)


def _published_posts():
    return (
        Post.objects.filter(status=Post.Status.PUBLISHED, published_at__isnull=False)
        .select_related("author", "category")
        .order_by("-published_at")
    )


def _published_news():
    return (
        NewsPost.objects.filter(
            status=NewsPost.Status.PUBLISHED, published_at__isnull=False
        )
        .select_related("author", "category")
        .order_by("-published_at")
    )


def _ctx(**extra):
    base = {"brand_name": site_name()}
    base.update(extra)
    return base


def home(request):
    return render(
        request,
        "keel_cms/home.html",
        _ctx(latest_posts=_published_posts()[:6], latest_news=_published_news()[:6]),
    )


def post_list(request):
    return render(
        request,
        "keel_cms/post_list.html",
        _ctx(page_title="Blog", posts=_published_posts()),
    )


def post_detail(request, slug):
    post = get_object_or_404(_published_posts(), slug=slug)
    return render(request, "keel_cms/post_detail.html", _ctx(post=post))


def topic_list(request, slug):
    category = get_object_or_404(Category, slug=slug, content_scope=ContentScope.BLOG)
    return render(
        request,
        "keel_cms/post_list.html",
        _ctx(page_title=category.name, posts=_published_posts().filter(category=category)),
    )


def tag_detail(request, slug):
    tag = get_object_or_404(Tag, slug=slug)
    return render(
        request,
        "keel_cms/tag_detail.html",
        _ctx(tag=tag, posts=_published_posts().filter(tags=tag)),
    )


def trading_glossary(request):
    return render(
        request, "keel_cms/glossary_index.html", _ctx(**trading_glossary_index_context())
    )


def trading_glossary_term(request, slug):
    tag = get_object_or_404(Tag, slug=slug, is_term=True)
    return render(
        request, "keel_cms/glossary_term.html", _ctx(**trading_glossary_term_context(tag))
    )


def team_desk(request, slug):
    author = get_object_or_404(Author, slug=slug)
    return render(
        request,
        "keel_cms/team_desk.html",
        _ctx(author=author, posts=_published_posts().filter(author=author)),
    )


def news_post_list(request):
    return render(
        request,
        "keel_cms/news_list.html",
        _ctx(page_title="News", posts=_published_news()),
    )


def news_post_detail(request, slug):
    post = get_object_or_404(_published_news(), slug=slug)
    return render(request, "keel_cms/news_detail.html", _ctx(post=post))


def news_topic_list(request, slug):
    category = get_object_or_404(Category, slug=slug, content_scope=ContentScope.NEWS)
    return render(
        request,
        "keel_cms/news_list.html",
        _ctx(page_title=category.name, posts=_published_news().filter(category=category)),
    )


def news_author_list(request, slug):
    author = get_object_or_404(Author, slug=slug)
    return render(
        request,
        "keel_cms/news_list.html",
        _ctx(page_title=author.name, posts=_published_news().filter(author=author)),
    )
