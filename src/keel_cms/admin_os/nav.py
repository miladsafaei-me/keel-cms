"""Sidebar nav data for the keel-cms Admin OS panel.

Assembling the nav (which sections/items/URLs exist) is the consumer's concern;
computing which item is active for the current path is generic and reused from
``keel_web.admin_shell.nav.resolve_nav_active``. Every ``match_prefix`` is the
reversed URL of the item so the nav stays correct regardless of the mount point
the host chose for the ``keel_cms.admin_os`` URLconf.
"""
from __future__ import annotations

from django.urls import reverse

from keel_web.admin_shell.nav import resolve_nav_active


def _url(name: str) -> str:
    return reverse(f"keel_cms_admin:{name}")


def build_cms_nav(request):
    """Return the panel sections with active/open state resolved for ``request.path``."""
    sections = [
        {
            "label": "Overview",
            "items": [
                {
                    "label": "Dashboard",
                    "icon": "dashboard",
                    "url": _url("dashboard"),
                    "match_prefix": _url("dashboard"),
                },
            ],
        },
        {
            "label": "Content",
            "items": [
                {
                    "label": "Blog",
                    "icon": "file-text",
                    "accordion": True,
                    "children": [
                        {"label": "All posts", "icon": "file-text", "url": _url("post_list"), "match_prefix": _url("post_list")},
                        {"label": "Add post", "icon": "plus", "url": _url("post_create"), "match_prefix": _url("post_create")},
                    ],
                },
                {
                    "label": "News",
                    "icon": "news",
                    "accordion": True,
                    "children": [
                        {"label": "All articles", "icon": "news", "url": _url("news_post_list"), "match_prefix": _url("news_post_list")},
                        {"label": "Add article", "icon": "plus", "url": _url("news_post_create"), "match_prefix": _url("news_post_create")},
                    ],
                },
            ],
        },
        {
            "label": "Taxonomy",
            "items": [
                {"label": "Authors", "icon": "users", "url": _url("author_list"), "match_prefix": _url("author_list")},
                {"label": "Topics", "icon": "folder", "url": _url("category_list"), "match_prefix": _url("category_list")},
                {"label": "Tags", "icon": "tag", "url": _url("tag_list"), "match_prefix": _url("tag_list")},
            ],
        },
    ]
    return resolve_nav_active(sections, request.path)
