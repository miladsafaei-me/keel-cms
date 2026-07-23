"""Server endpoint for the 3-tab body editor: convert body between Markdown and HTML.

Delegates conversion to ``keel_cms.markdown_convert`` + ``keel_cms.html_sanitize``.
Two seams are host-configurable:

* Permission: ``KEEL_CMS["editor_permission_hook"]`` — a dotted-path callable
  ``(user) -> bool``. Default: ``user.is_staff`` (any staff user).
* Persist: ``KEEL_CMS["editor_persist_hook"]`` — a dotted-path callable
  ``(section, post_id, markdown_src, html) -> bool`` that saves the converted body
  onto the host's Post/NewsPost and re-renders it. Default: no-op (returns False),
  because writing the body + kicking a re-render task is a host concern (the
  original project routed this through a Celery ``refresh_*_rendered`` task).

Wire this view into the host URLconf as ``keel_cms:content_convert`` (the name the
``_content_editor.html`` config expects), or pass an explicit ``ce_convert_url`` to
the template.
"""

from __future__ import annotations

import json
import logging

from django.http import JsonResponse
from django.utils.module_loading import import_string
from django.views.decorators.http import require_POST

from .config import cms_setting
from .markdown_convert import (
    html_to_markdown_for_edit,
    prepare_blog_content_for_storage,
    prepare_pipeline_content_for_storage,
)

logger = logging.getLogger(__name__)


def _is_content_editor(user) -> bool:
    dotted = cms_setting_raw("editor_permission_hook")
    if dotted:
        try:
            return bool(import_string(dotted)(user))
        except Exception:
            return False
    return bool(getattr(user, "is_staff", False))


def cms_setting_raw(key):
    """Read an optional KEEL_CMS key not present in the core defaults set."""
    from django.conf import settings

    return getattr(settings, "KEEL_CMS", {}).get(key)


def _persist_converted_body(section: str, post_id: str, markdown_src: str, html: str) -> bool:
    """Persist the converted body via the host persist hook (no-op by default).

    TODO(host): the host supplies ``KEEL_CMS["editor_persist_hook"]`` to write
    ``content_markdown_source`` + ``content_raw`` onto its Post/NewsPost and kick a
    re-render of ``content_rendered`` (the original project used a Celery
    ``refresh_*_rendered`` task). Without the hook, conversion still works; only the
    inline "save while editing" persist is disabled.
    """
    dotted = cms_setting_raw("editor_persist_hook")
    if not dotted:
        return False
    try:
        return bool(import_string(dotted)(section, post_id, markdown_src, html))
    except Exception:
        logger.exception("content_convert persist hook failed")
        return False


@require_POST
def content_convert(request):
    """Convert body content between Markdown and HTML for the three-tab editor.

    ``direction`` == ``md2html`` (default): Markdown -> sanitized HTML. Pipeline
    posts keep their Mermaid / Chart.js / custom blocks (sanitizer skipped) when
    ``is_pipeline`` is set. When ``persist`` is set and a ``post_id`` is given, the
    converted body is also saved via the host persist hook.

    ``direction`` == ``html2md``: HTML -> Markdown, used to refresh the Markdown tab
    after the operator edits the HTML / Preview tab. Never persists.
    """
    if not _is_content_editor(request.user):
        return JsonResponse({"error": "Unauthorized"}, status=403)

    try:
        body = json.loads(request.body.decode())
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    direction = (body.get("direction") or "md2html").strip().lower()
    section = (body.get("section") or "blog").strip().lower()

    if direction == "html2md":
        html_src = (body.get("html") or "").replace("\x00", "")
        try:
            markdown = html_to_markdown_for_edit(html_src)
        except Exception:
            logger.exception("content_convert html2md failed")
            return JsonResponse({"error": "Conversion failed."}, status=500)
        return JsonResponse({"markdown": markdown})

    markdown_src = (body.get("markdown") or "").replace("\x00", "")
    is_pipeline = bool(body.get("is_pipeline"))
    convert = (
        prepare_pipeline_content_for_storage if is_pipeline
        else prepare_blog_content_for_storage
    )
    try:
        html = convert(markdown_src)
    except Exception:
        logger.exception("content_convert md2html failed")
        return JsonResponse({"error": "Conversion failed."}, status=500)

    saved = False
    post_id = (body.get("post_id") or "").strip()
    if body.get("persist") and post_id:
        try:
            saved = _persist_converted_body(section, post_id, markdown_src, html)
        except Exception:
            logger.exception("content_convert persist failed")
            saved = False
    return JsonResponse({"html": html, "saved": saved})
