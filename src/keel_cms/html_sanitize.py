"""
Sanitize post HTML (Markdown-derived, WYSIWYG legacy, auto-linker output) with nh3.

The allowlisted class conventions (``ql-*`` from Quill, ``fa-*`` FontAwesome,
``language-*`` code highlight, ``in-content-read``, ``intent-target``) are generic
editor/pipeline conventions. Note the ``cp-*`` component-library prefix is NOT in
this allowlist: pipeline-generated bodies skip this sanitizer entirely (they are
trusted by construction), which is where ``cp-*`` visual blocks survive.
"""

from __future__ import annotations

import re
from copy import deepcopy
from functools import lru_cache

import nh3

# CSS properties Quill commonly emits; nh3 filters values (drops url(), expression(), etc.).
_STYLE_PROPERTIES = frozenset(
    {
        "color",
        "background-color",
        "font-size",
        "font-family",
        "font-weight",
        "font-style",
        "text-align",
        "text-decoration",
        "width",
        "max-width",
        "height",
        "max-height",
        "line-height",
        "letter-spacing",
        "direction",
    }
)

_ALLOWED_A_REL = frozenset({"nofollow", "noopener", "noreferrer", "sponsored", "ugc", "external"})

_QL_CLASS = re.compile(r"^ql-[a-z0-9_-]+$", re.IGNORECASE)
_IN_CONTENT_READ_CLASS = re.compile(r"^in-content-read(-text|-label)?$", re.IGNORECASE)
_CODE_LANGUAGE_CLASS = re.compile(r"^language-[a-z0-9#.+\-_]+$", re.IGNORECASE)
_FA_CLASS = re.compile(r"^fa(-[a-z0-9-]+)+$", re.IGNORECASE)
_HEADING_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,120}$")


def _class_token_allowed(token: str) -> bool:
    if token == "intent-target":
        return True
    if _QL_CLASS.fullmatch(token):
        return True
    if _IN_CONTENT_READ_CLASS.fullmatch(token):
        return True
    if token in ("fa-solid", "fa-regular", "fa-brands", "fa-fw"):
        return True
    if _FA_CLASS.fullmatch(token):
        return True
    if _CODE_LANGUAGE_CLASS.fullmatch(token):
        return True
    return False


@lru_cache(maxsize=1)
def _nh3_attributes() -> dict[str, set[str]]:
    attrs = deepcopy(nh3.ALLOWED_ATTRIBUTES)
    class_and_style_tags = (
        "p",
        "span",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "ol",
        "ul",
        "blockquote",
        "pre",
        "code",
        "strong",
        "em",
        "b",
        "i",
        "u",
        "s",
        "sub",
        "sup",
        "a",
        "td",
        "th",
        "table",
    )
    for tag in class_and_style_tags:
        bucket = attrs.setdefault(tag, set())
        bucket.add("class")
        if tag in (
            "span",
            "p",
            "strong",
            "em",
            "b",
            "i",
            "u",
            "s",
            "sub",
            "sup",
            "a",
            "blockquote",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "li",
            "td",
            "th",
        ):
            bucket.add("style")
    attrs.setdefault("a", set()).update({"class", "target", "rel"})
    attrs.setdefault("img", set()).update({"class", "style"})
    for _htag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        attrs.setdefault(_htag, set()).add("id")
    return attrs


def _attribute_filter(tag: str, attr: str, value: str) -> str | None:
    if attr == "class" and value:
        parts = value.split()
        safe: list[str] = []
        for c in parts:
            if _class_token_allowed(c):
                safe.append(c)
        return " ".join(safe) if safe else None
    if tag == "a" and attr == "target":
        return value if value in ("_blank", "_self") else None
    if tag == "a" and attr == "rel" and value:
        parts = [p.strip().lower() for p in value.split() if p.strip()]
        safe_rel = [p for p in parts if p in _ALLOWED_A_REL]
        return " ".join(safe_rel) if safe_rel else None
    if tag == "img" and attr == "src" and value.lower().startswith("data:"):
        head = value.split(",", 1)[0].lower()
        if "svg" in head:
            return None
        if any(m in head for m in ("image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp")):
            return value
        return None
    if tag in ("h1", "h2", "h3", "h4", "h5", "h6") and attr == "id" and value:
        vid = value.strip()
        if _HEADING_ID_RE.fullmatch(vid):
            return vid[:120]
        return None
    return value


def sanitize_blog_html(html: str) -> str:
    """Return safe HTML fragment for storage and display."""
    if not html or not isinstance(html, str):
        return ""
    return nh3.clean(
        html,
        attributes=_nh3_attributes(),
        attribute_filter=_attribute_filter,
        link_rel=None,
        url_schemes={"http", "https", "mailto", "tel", "data"},
        filter_style_properties=_STYLE_PROPERTIES,
    )
