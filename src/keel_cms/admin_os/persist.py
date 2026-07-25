"""Persist hook for the 3-tab editor's inline "save while editing" path.

A host wires this as ``KEEL_CMS["editor_persist_hook"]``; ``keel_cms.editor_views
.content_convert`` calls it when the editor posts a convert-and-save. It writes only
the body columns (``content_markdown_source`` + ``content_raw``) so an in-progress
edit of other fields on the page is never clobbered. Re-rendering ``content_rendered``
(auto-linking, etc.) stays a host concern — the post_save signal fires from the save
below, and a host that runs an auto-linker task hangs it off that.
"""
from __future__ import annotations

from django.core.exceptions import ValidationError

from keel_cms.models import NewsPost, Post


def persist_converted_body(section: str, post_id: str, markdown_src: str, html: str) -> bool:
    """Write the converted body onto an existing Post / NewsPost. Returns True on success."""
    Model = NewsPost if (section or "").strip().lower() == "news" else Post
    try:
        obj = Model.all_objects.get(pk=post_id)
    except (Model.DoesNotExist, ValueError, TypeError, ValidationError):
        return False
    obj.content_markdown_source = markdown_src or ""
    obj.content_raw = html or ""
    obj.save(update_fields=["content_markdown_source", "content_raw"])
    return True
