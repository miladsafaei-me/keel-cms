"""Shared context for every Admin OS page.

Injects the resolved sidebar nav, the brand name (from ``KEEL_CMS["site_name"]``),
an optional per-view ``page_title`` / ``page_pretitle``, and the logout URL the
shadowed navbar reverses. ``cms_admin_base_context`` is the plain-function form for
the ``View``-based list pages that do not go through ``get_context_data``.
"""
from __future__ import annotations

from keel_cms.config import admin_logout_url, site_name

from .nav import build_cms_nav


def _brand_name() -> str:
    return site_name() or "Keel CMS"


def cms_admin_base_context(request) -> dict:
    return {
        "admin_nav": build_cms_nav(request),
        "brand_name": _brand_name(),
        "logout_url": admin_logout_url(),
    }


class CmsAdminContextMixin:
    """Mixin for class-based views that renders inside the admin shell chrome."""

    page_title: str = ""
    page_pretitle: str = ""

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        for key, value in cms_admin_base_context(self.request).items():
            ctx.setdefault(key, value)
        if self.page_title:
            ctx.setdefault("page_title", self.page_title)
        if self.page_pretitle:
            ctx.setdefault("page_pretitle", self.page_pretitle)
        return ctx
