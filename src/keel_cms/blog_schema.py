"""
schema.org JSON-LD builders for blog pages.

Goal: provide precise, standard markup for BlogPosting, Organization (author desk),
Comment (post discussion, including replies), and BreadcrumbList.

Neutralized from the source project: the ``SITE_NAME`` constant now reads from
``KEEL_CMS["site_name"]``; the publisher Organization node is resolved through the
``organization_node_hook`` (with a minimal default); the Editorial Board reviewer
is resolved through the editorial-desks framework's board hook. Host URL patterns
(``keel_cms:team_desk`` / ``keel_cms:post_detail`` / ``keel_cms:home`` /
``keel_cms:post_list`` / ``keel_cms:topic_list``) are reversed defensively so a
standalone import with no URLconf never raises.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from django.urls import NoReverseMatch, reverse
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe

from .config import cms_setting, _resolve_hook
from .editorial_desks import board_review_anchor, board_schema_name
from .media_urls import featured_image_absolute_url
from .schema_datetime import isoformat_utc_public

SITE_URL_FALLBACK = "/"  # used only if request isn't available


def site_name() -> str:
    return cms_setting("site_name") or ""


def _reverse(name: str, **kwargs) -> str:
    """Reverse a host URL pattern; return "" (never raise) when unwired."""
    try:
        return reverse(name, kwargs=kwargs) if kwargs else reverse(name)
    except NoReverseMatch:
        return ""


def _abs_url(request, path: str) -> str:
    if not path:
        path = SITE_URL_FALLBACK
    return request.build_absolute_uri(path) if request else SITE_URL_FALLBACK


def _iso(dt) -> str | None:
    return isoformat_utc_public(dt)


def _truncate(text: str, max_len: int = 160) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _plain_from_html(html_text: str | None) -> str:
    if not html_text:
        return ""
    return _truncate(strip_tags(html_text))


def render_json_ld(graph: list[dict[str, Any]]) -> str:
    payload = {"@context": "https://schema.org", "@graph": graph}
    raw = json.dumps(payload, ensure_ascii=False, default=str)
    return mark_safe(f'<script type="application/ld+json">{raw}</script>')


def _default_organization_node(request) -> dict[str, Any]:
    """Minimal publisher Organization node when no ``organization_node_hook`` is set."""
    base = _abs_url(request, "/")
    base = base[:-1] if base.endswith("/") else base
    node: dict[str, Any] = {
        "@type": "Organization",
        "@id": (base or "") + "#organization",
        "url": base or SITE_URL_FALLBACK,
    }
    name = site_name()
    if name:
        node["name"] = name
    return node


def organization(request) -> dict[str, Any]:
    """The publisher Organization node - host hook if configured, else the default."""
    hook = _resolve_hook("organization_node_hook")
    if hook is not None:
        try:
            return dict(hook(request) or {})
        except Exception:
            pass
    return _default_organization_node(request)


def _author_same_as_urls(social_links: Any) -> list[str]:
    """Collect profile / social URLs for schema.org sameAs (Person)."""
    if not social_links or not isinstance(social_links, dict):
        return []
    order_keys = (
        "twitter",
        "linkedin",
        "github",
        "instagram",
        "telegram",
        "youtube",
        "website",
    )
    out: list[str] = []
    seen: set[str] = set()
    for key in order_keys:
        raw = social_links.get(key)
        if not raw:
            continue
        url = str(raw).strip()
        if url and url not in seen:
            out.append(url)
            seen.add(url)
    custom = social_links.get("custom")
    if isinstance(custom, list):
        for item in custom:
            if not isinstance(item, dict):
                continue
            raw = item.get("url") or ""
            url = str(raw).strip()
            if url and url not in seen:
                out.append(url)
                seen.add(url)
    return out


def organization_for_desk(request, author) -> dict[str, Any]:
    """schema.org Organization node for an Editorial Desk (the post author)."""
    if not author:
        return {"@type": "Organization", "name": site_name()}
    desk_path = _reverse("keel_cms:team_desk", slug=author.slug)
    desk_url = _abs_url(request, desk_path)
    return {
        "@type": "Organization",
        "@id": desk_url + "#desk",
        "name": author.name,
        "url": desk_url,
    }


def editorial_team_node(request) -> dict[str, Any]:
    """Fixed reviewedBy Organization - the host editorial / fact-checking team.

    Points at the board's review-process anchor (no dedicated team page).
    """
    review_url = _abs_url(request, board_review_anchor())
    return {
        "@type": "Organization",
        "@id": review_url,
        "name": board_schema_name(),
        "url": review_url,
    }


def breadcrumb_list(items: list[tuple[str, str | None]], request, *, page_url: str | None = None):
    """
    items: [(label, item_url_or_None)]
    """
    current = page_url or _abs_url(request, "/")
    element_list: list[dict[str, Any]] = []
    for idx, (label, item) in enumerate(items, start=1):
        element_list.append(
            {
                "@type": "ListItem",
                "position": idx,
                "name": label,
                "item": _abs_url(request, item) if item else current,
            }
        )
    return {
        "@type": "BreadcrumbList",
        "itemListElement": element_list,
    }


def webpage(request, path: str, *, name: str, description: str | None = None) -> dict[str, Any]:
    url = _abs_url(request, path)
    return {
        "@type": "WebPage",
        "@id": url,
        "url": url,
        "name": name,
        "description": description,
    }


def blogposting_node(
    request,
    post,
    author,
    *,
    post_url: str,
) -> dict[str, Any]:
    desc = post.meta_description or post.excerpt or ""
    node: dict[str, Any] = {
        "@type": "BlogPosting",
        "@id": post_url + "#blogposting",
        "headline": post.title,
        "description": _truncate(desc, 160),
        "url": post_url,
        "mainEntityOfPage": {"@type": "WebPage", "@id": post_url},
        "author": {"@id": author["@id"]},
        "publisher": {"@id": organization(request)["@id"]},
    }
    # NOTE: `reviewedBy` is a schema.org property of WebPage, not BlogPosting,
    # so it is attached to the WebPage node (see build_post_page_schema), not here.
    if post.published_at:
        node["datePublished"] = isoformat_utc_public(post.published_at)
    if getattr(post, "updated_at", None):
        node["dateModified"] = isoformat_utc_public(post.updated_at)
    img_abs = featured_image_absolute_url(request, getattr(post, "featured_image_url", None))
    if img_abs:
        node["image"] = img_abs
    return node


def comment_nodes_for_post(request, post, *, post_url: str, comments: Iterable[Any]) -> list[dict[str, Any]]:
    """
    comments: post.comments.all() i.e. approved root comments with prefetched replies.
    """
    posting_id = post_url + "#blogposting"
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
                        "author": {"@type": "Person", "@id": reply_id + "#author", "name": reply_author_name},
                    }
                )
            # Reply nesting is represented by each reply's `parentItem` link.

        graph.append(top_node)

    return graph


def build_post_page_schema(request, post, *, post_url: str, author, comments) -> list[dict[str, Any]]:
    author_org = organization_for_desk(request, author)
    reviewer_obj = getattr(post, "reviewer", None)
    reviewer_org: dict[str, Any] | None = None
    if reviewer_obj is not None:
        reviewer_org = editorial_team_node(request)
    page = webpage(
        request,
        _reverse("keel_cms:post_detail", slug=post.slug),
        name=f"{post.title} | {site_name()} Blog".replace("|  Blog", "| Blog").strip(),
        description=post.meta_description or post.excerpt,
    )
    # reviewedBy belongs on the WebPage (schema.org), not the BlogPosting.
    if reviewer_org:
        page["reviewedBy"] = {"@id": reviewer_org["@id"]}
    org = organization(request)
    bc = breadcrumb_list(
        [
            ("Home", _reverse("keel_cms:home")),
            ("Blog", _reverse("keel_cms:post_list")),
            (post.category.name, _reverse("keel_cms:topic_list", slug=post.category.slug))
            if getattr(post, "category", None)
            else ("Blog", None),
            (post.title, None),
        ],
        request,
        page_url=post_url,
    )

    posting = blogposting_node(request, post, author_org, post_url=post_url)
    comments_graph = comment_nodes_for_post(request, post, post_url=post_url, comments=comments)
    graph: list[dict[str, Any]] = [org, author_org]
    if reviewer_org and reviewer_org["@id"] != author_org["@id"]:
        graph.append(reviewer_org)
    graph += [page, bc, posting] + comments_graph
    return graph


def build_list_page_schema(
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
        pa = organization_for_desk(request, profile_author)
        author_cache[pa["@id"]] = pa
    post_graph: list[dict[str, Any]] = []
    comment_graph: list[dict[str, Any]] = []

    for post in list(posts)[:12]:
        author = organization_for_desk(request, post.author)
        author_cache[author["@id"]] = author
        post_path = _reverse("keel_cms:post_detail", slug=post.slug)
        post_url = _abs_url(request, post_path)
        posting = blogposting_node(request, post, author, post_url=post_url)
        post_graph.append(posting)

        item_list.append(
            {
                "@type": "ListItem",
                "position": len(item_list) + 1,
                "url": post_url,
                "name": post.title,
            }
        )

        # Add a small set of root approved comments (if prefetched by the views).
        top_comments = getattr(post, "approved_root_comments_for_schema", None) or []
        posting_id = post_url + "#blogposting"
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
