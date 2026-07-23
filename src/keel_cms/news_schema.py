"""schema.org JSON-LD for public news pages (NewsArticle, breadcrumbs, comments).

Reuses the shared builders from ``keel_cms.blog_schema``; the site name comes from
``KEEL_CMS["site_name"]``, and host URL patterns (``keel_cms:news_post_detail`` /
``keel_cms:news_author_list`` / ``keel_cms:home`` / ``keel_cms:news_post_list`` /
``keel_cms:news_topic_list``) are reversed defensively.
"""

from __future__ import annotations

from typing import Any, Iterable

from .blog_schema import (
    _abs_url,
    _iso,
    _reverse,
    _truncate,
    _author_same_as_urls,
    breadcrumb_list,
    organization,
    render_json_ld,
    site_name,
    webpage,
)
from .media_urls import featured_image_absolute_url
from .schema_datetime import isoformat_utc_public


def person_for_author_news(request, author) -> dict[str, Any]:
    if not author:
        return {"@type": "Person", "name": "Unknown author"}
    author_path = _reverse("keel_cms:news_author_list", slug=author.slug)
    author_url = _abs_url(request, author_path)
    out: dict[str, Any] = {
        "@type": "Person",
        "@id": author_url + "#person",
        "name": author.name,
        "url": author_url,
    }
    if getattr(author, "avatar_url", None):
        out["image"] = author.avatar_url
    same_as = _author_same_as_urls(getattr(author, "social_links", None))
    if same_as:
        out["sameAs"] = same_as
    return out


def news_article_node(request, post, author, *, post_url: str) -> dict[str, Any]:
    desc = post.meta_description or post.excerpt or ""
    node: dict[str, Any] = {
        "@type": "NewsArticle",
        "@id": post_url + "#newsarticle",
        "headline": post.title,
        "description": _truncate(desc, 160),
        "url": post_url,
        "mainEntityOfPage": {"@type": "WebPage", "@id": post_url},
        "author": {"@id": author["@id"]},
        "publisher": {"@id": organization(request)["@id"]},
    }
    if post.published_at:
        node["datePublished"] = isoformat_utc_public(post.published_at)
    if getattr(post, "updated_at", None):
        node["dateModified"] = isoformat_utc_public(post.updated_at)
    img_abs = featured_image_absolute_url(request, getattr(post, "featured_image_url", None))
    if img_abs:
        node["image"] = img_abs
    return node


def comment_nodes_for_news_post(
    request, post, *, post_url: str, comments: Iterable[Any]
) -> list[dict[str, Any]]:
    posting_id = post_url + "#newsarticle"
    graph: list[dict[str, Any]] = []

    for top_comment in comments:
        top_id = str(getattr(top_comment, "id", ""))
        comment_id = post_url + f"#comment-{top_id}"
        author_name = (getattr(top_comment, "author_name", "") or "").strip()
        if not author_name and getattr(top_comment, "user", None) is not None:
            user = top_comment.user
            author_name = (
                (getattr(user, "get_full_name", None) and user.get_full_name())
                or getattr(user, "username", "")
                or ""
            ).strip()
        author_name = author_name or "Anonymous"

        top_node: dict[str, Any] = {
            "@type": "Comment",
            "@id": comment_id,
            "parentItem": {"@id": posting_id},
            "text": (top_comment.body or "").strip(),
            "datePublished": _iso(getattr(top_comment, "created_at", None)),
            "author": {"@type": "Person", "@id": comment_id + "#author", "name": author_name},
        }
        if getattr(top_comment, "replies", None) is not None:
            replies_list = list(top_comment.replies.all()[:50])
        else:
            replies_list = []

        if replies_list:
            for reply in replies_list:
                reply_id = post_url + f"#comment-{top_id}-reply-{getattr(reply, 'id', '')}"
                reply_author_name = (getattr(reply, "author_name", "") or "").strip()
                if not reply_author_name and getattr(reply, "user", None) is not None:
                    user = reply.user
                    reply_author_name = (
                        (getattr(user, "get_full_name", None) and user.get_full_name())
                        or getattr(user, "username", "")
                        or ""
                    ).strip()
                reply_author_name = reply_author_name or "Anonymous"

                graph.append(
                    {
                        "@type": "Comment",
                        "@id": reply_id,
                        "parentItem": {"@id": comment_id},
                        "text": (reply.body or "").strip(),
                        "datePublished": _iso(getattr(reply, "created_at", None)),
                        "author": {
                            "@type": "Person",
                            "@id": reply_id + "#author",
                            "name": reply_author_name,
                        },
                    }
                )

        graph.append(top_node)

    return graph


def build_news_post_page_schema(request, post, *, post_url: str, author, comments) -> list[dict[str, Any]]:
    author_person = person_for_author_news(request, author)
    page = webpage(
        request,
        _reverse("keel_cms:news_post_detail", slug=post.slug),
        name=f"{post.title} | {site_name()} News".replace("|  News", "| News").strip(),
        description=post.meta_description or post.excerpt,
    )
    org = organization(request)
    bc = breadcrumb_list(
        [
            ("Home", _reverse("keel_cms:home")),
            ("News", _reverse("keel_cms:news_post_list")),
            (
                post.category.name,
                _reverse("keel_cms:news_topic_list", slug=post.category.slug),
            )
            if getattr(post, "category", None)
            else ("News", None),
            (post.title, None),
        ],
        request,
        page_url=post_url,
    )

    article = news_article_node(request, post, author_person, post_url=post_url)
    comments_graph = comment_nodes_for_news_post(
        request, post, post_url=post_url, comments=comments
    )
    return [org, author_person, page, bc, article] + comments_graph


def build_news_list_page_schema(
    request,
    *,
    posts,
    page_name: str,
    page_path: str,
    breadcrumb_items: list[tuple[str, str | None]],
    profile_author=None,
) -> list[dict[str, Any]]:
    org = organization(request)
    page = webpage(request, page_path, name=page_name)
    bc = breadcrumb_list(breadcrumb_items, request, page_url=_abs_url(request, page_path))

    item_list: list[dict[str, Any]] = []
    author_cache: dict[str, dict[str, Any]] = {}
    if profile_author is not None:
        pa = person_for_author_news(request, profile_author)
        author_cache[pa["@id"]] = pa
    post_graph: list[dict[str, Any]] = []
    comment_graph: list[dict[str, Any]] = []

    for post in list(posts)[:12]:
        author = person_for_author_news(request, post.author)
        author_cache[author["@id"]] = author
        post_path = _reverse("keel_cms:news_post_detail", slug=post.slug)
        post_url = _abs_url(request, post_path)
        article = news_article_node(request, post, author, post_url=post_url)
        post_graph.append(article)

        item_list.append(
            {
                "@type": "ListItem",
                "position": len(item_list) + 1,
                "url": post_url,
                "name": post.title,
            }
        )

        top_comments = getattr(post, "approved_root_comments_for_schema", None) or []
        posting_id = post_url + "#newsarticle"
        for top_comment in list(top_comments)[:3]:
            top_id = str(getattr(top_comment, "id", ""))
            comment_id = post_url + f"#comment-{top_id}"
            author_name = (getattr(top_comment, "author_name", "") or "").strip()
            if not author_name and getattr(top_comment, "user", None) is not None:
                user = top_comment.user
                author_name = (
                    (getattr(user, "get_full_name", None) and user.get_full_name())
                    or getattr(user, "username", "")
                    or ""
                ).strip()
            author_name = author_name or "Anonymous"

            comment_graph.append(
                {
                    "@type": "Comment",
                    "@id": comment_id,
                    "parentItem": {"@id": posting_id},
                    "text": (getattr(top_comment, "body", "") or "").strip(),
                    "datePublished": _iso(getattr(top_comment, "created_at", None)),
                    "author": {
                        "@type": "Person",
                        "@id": comment_id + "#author",
                        "name": author_name,
                    },
                }
            )

    return (
        [org, page, bc]
        + list(author_cache.values())
        + post_graph
        + comment_graph
        + [
            {
                "@type": "ItemList",
                "name": page_name,
                "itemListElement": item_list,
            }
        ]
    )


__all__ = [
    "build_news_list_page_schema",
    "build_news_post_page_schema",
    "render_json_ld",
]
