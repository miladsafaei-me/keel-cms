"""
Convert Markdown (admin editor) to sanitized HTML for ``Post.content_raw``,
and HTML back to Markdown for editing existing posts.

``prepare_blog_content_for_storage`` accepts plain Markdown or Quill HTML (including
Markdown pasted as plain text inside ``<p>`` blocks) and always stores safe HTML.

``markdownify`` is imported lazily so a missing optional dependency does not break
the whole module (admin edit view would otherwise return 500 on import). The
``cp-*`` figure/chart wrapper prefixes recognized here are a deliberate contract
with the keel-ui component library (its class namespace); the pipeline render path
below keeps those blocks intact.
"""

from __future__ import annotations

import logging
import re

import markdown2
from bs4 import BeautifulSoup

from .html_sanitize import sanitize_blog_html

logger = logging.getLogger(__name__)

_MARKDOWN_EXTRAS = (
    "fenced-code-blocks",
    "tables",
    "strike",
    "cuddled-lists",
    "code-friendly",
    "break-on-newline",
)

_RICH_MARKERS = ("ql-", "in-content-read", "<figure")
_SIMPLE_CONTAINER_TAGS = frozenset({"p", "div", "br"})

# If the body contains "<" (e.g. inline <a> from the link modal) but is still Markdown,
# we must run markdown2 first; sanitize-only leaves # headings and **bold** as plain text.
_MARKDOWN_SOURCE_HINTS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?m)^#{1,6}\s"),
    re.compile(r"(?m)^\s{0,3}>\s"),
    re.compile(r"(?m)^\s*[-*+]\s"),
    re.compile(r"(?m)^\s*\d{1,4}[.)]\s"),
    re.compile(r"```"),
    re.compile(r"\[[^\]]+\]\([^)]+\)"),
    re.compile(r"\*\*[^*\n]+\*\*"),
    re.compile(r"__[^_\n]+__"),
    re.compile(r"(?m)^\s*\|.*\|\s*$"),
)

# Skip heavy HTML->Markdown for huge bodies (avoids worker hangs / recursion / memory).
_MAX_HTML_TO_MARKDOWN_CHARS = 1_500_000

_blog_converter_cls: type | None = None
_blog_converter_cls_resolved: bool = False


def markdown_to_blog_html(markdown_src: str) -> str:
    """Parse Markdown to HTML and run the same nh3 pass as WYSIWYG output."""
    text = markdown_src or ""
    if not text.strip():
        return ""
    html = markdown2.markdown(text, extras=list(_MARKDOWN_EXTRAS))
    return sanitize_blog_html(html)


# The inner group is a *tempered* dot - ``(?:(?!</?h[1-6]).)*?`` - so it can never
# span across another heading tag. Without that guard, a lazy ``.*?`` under DOTALL
# jumps from a heading that has NO ``{#id}`` forward to the next same-level heading
# that does, mis-assigning that id and leaving the skipped headings' ``{#id}`` as
# literal text in the rendered output.
_HEADING_ANCHOR_RE = re.compile(
    r"<(h[2-6])([^>]*)>((?:(?!</?h[1-6]).)*?)\s*\{#([a-zA-Z0-9_-]{1,120})\}\s*</\1>",
    re.IGNORECASE | re.DOTALL,
)


def _inject_heading_anchors(html: str) -> str:
    """Promote ``## Heading {#some-id}`` markers (left as text by markdown2) into ``id`` attrs.

    Used by the pipeline path so emitted heading anchors survive into the rendered
    HTML for in-page navigation / TOC linking.
    """

    def _sub(m: re.Match[str]) -> str:
        tag, attrs, inner, anchor = m.group(1), m.group(2), m.group(3), m.group(4)
        if "id=" in attrs.lower():
            return m.group(0)
        return f'<{tag}{attrs} id="{anchor}">{inner.rstrip()}</{tag}>'

    return _HEADING_ANCHOR_RE.sub(_sub, html or "")


# Pipeline-authored figure/chart wrappers (Chart.js canvases, static figures) are
# raw HTML the model types inline in the draft Markdown, as one blank-line-delimited
# block. The pipeline path skips the nh3 sanitizer that would normally balance
# tags, so a single dropped closing </div> makes the wrapper swallow the entire
# rest of the article. These wrappers are always a single contiguous block, so we
# balance each block deterministically before markdown2 sees it.
_FIGURE_WRAPPER_OPEN_RE = re.compile(
    r'^\s*<(?:div|figure)\b[^>]*\bclass\s*=\s*["\'][^"\']*'
    r'\bcp-(?:chartjs-wrapper|figure|figure-[\w-]+)\b',
    re.IGNORECASE,
)
_BLANK_LINE_SPLIT_RE = re.compile(r"(\n[ \t]*\n)")
_DIV_OPEN_RE = re.compile(r"<div\b", re.IGNORECASE)
_FIGURE_OPEN_RE = re.compile(r"<figure\b", re.IGNORECASE)


def _balance_figure_wrapper_blocks(markdown_src: str) -> str:
    """Append any missing closing tags to pipeline-authored figure/chart wrapper blocks.

    Operates per blank-line-delimited block. Only blocks that *begin* with a
    ``cp-chartjs-wrapper`` / ``cp-figure*`` wrapper are touched, and only when their
    ``<div>``/``<figure>`` opens outnumber their closes - so balanced blocks and
    ordinary prose are left byte-for-byte unchanged. Inner ``</div>`` closers are
    emitted before the outer ``</figure>`` so the original nesting is preserved.
    """
    out: list[str] = []
    for chunk in _BLANK_LINE_SPLIT_RE.split(markdown_src):
        if not _FIGURE_WRAPPER_OPEN_RE.match(chunk):
            out.append(chunk)
            continue
        div_diff = len(_DIV_OPEN_RE.findall(chunk)) - chunk.lower().count("</div>")
        fig_diff = len(_FIGURE_OPEN_RE.findall(chunk)) - chunk.lower().count("</figure>")
        if div_diff > 0 or fig_diff > 0:
            closers = "</div>\n" * max(div_diff, 0) + "</figure>\n" * max(fig_diff, 0)
            chunk = chunk.rstrip() + "\n" + closers
            logger.warning(
                "Auto-closed an unbalanced figure wrapper in pipeline content "
                "(added %d </div>, %d </figure>).",
                max(div_diff, 0),
                max(fig_diff, 0),
            )
        out.append(chunk)
    return "".join(out)


def _markdown_pipeline_blockwise(text: str) -> str:
    """Fallback used only when whole-document ``markdown2`` raises: convert each
    blank-line-delimited block independently, emitting any single block that still
    breaks ``markdown2`` (it is already valid rendered HTML) raw.

    ``markdown2`` has assert-based bugs that fire on some rendered-component HTML. A
    library bug must never fail a pipeline import, so this isolates the damage to the
    one offending block instead of dropping the whole article.
    """
    parts: list[str] = []
    for block in _BLANK_LINE_SPLIT_RE.split(text):
        if not block.strip():
            parts.append(block)
            continue
        try:
            parts.append(markdown2.markdown(block, extras=list(_MARKDOWN_EXTRAS)))
        except Exception:
            logger.warning("markdown2 failed on a single pipeline block; emitting it raw.")
            parts.append(block)
    return "".join(parts)


_EMBED_FIGURE_OPEN = '<figure class="cp-figure cp-figure--embed">'


def _protect_embed_figures(text: str) -> tuple[str, dict[str, str]]:
    """Replace each rendered ``cp-figure--embed`` block with a single-line placeholder
    so markdown2 never touches it.

    The component renderer emits multi-line HTML that legitimately contains blank
    lines. markdown2 ends an HTML block at the first blank line and then treats the
    *indented* HTML after it as an indented code block - turning the visual into
    visible ``<pre><code>`` source. Hashing the whole embed out (balanced
    ``<figure>`` match) and restoring it verbatim after conversion keeps the rendered
    markup exactly as produced.
    """
    placeholders: dict[str, str] = {}
    out: list[str] = []
    i = n = 0
    while True:
        start = text.find(_EMBED_FIGURE_OPEN, i)
        if start == -1:
            out.append(text[i:])
            break
        out.append(text[i:start])
        depth = 0
        j = start
        while j < len(text):
            nxt_open = text.find("<figure", j)
            nxt_close = text.find("</figure>", j)
            if nxt_close == -1:  # unbalanced - swallow the rest defensively
                j = len(text)
                break
            if nxt_open != -1 and nxt_open < nxt_close:
                depth += 1
                j = nxt_open + len("<figure")
            else:
                depth -= 1
                j = nxt_close + len("</figure>")
                if depth == 0:
                    break
        key = f"CPEMBED{n}ENDCPEMBED"
        placeholders[key] = text[start:j]
        out.append(f"\n\n{key}\n\n")
        n += 1
        i = j
    return "".join(out), placeholders


def _restore_embed_figures(html: str, placeholders: dict[str, str]) -> str:
    for key, block in placeholders.items():
        html = html.replace(f"<p>{key}</p>", block).replace(key, block)
    return html


def prepare_pipeline_content_for_storage(raw_markdown: str) -> str:
    """Pipeline-only Markdown -> HTML; **skips** the nh3 sanitize pass.

    Pipeline output is trusted by construction (no user input), so we keep
    Mermaid ``<pre class="mermaid">``, Chart.js ``<canvas data-cp-chart>``,
    and custom ``<style>``/``<script>``-free HTML blocks intact for rendering.

    Because the sanitizer is skipped, a dropped closing tag on a figure/chart
    wrapper is balanced here first (``_balance_figure_wrapper_blocks``) so the
    wrapper can never swallow the rest of the article. Rendered ``cp-figure--embed``
    components are hashed out before conversion (``_protect_embed_figures``) so
    markdown2 cannot mangle their multi-line HTML.

    Heading anchors of the form ``{#id}`` (left as text by markdown2) are
    promoted to real ``id`` attributes on the heading tag.
    """
    text = raw_markdown or ""
    if not text.strip():
        return ""
    text, embeds = _protect_embed_figures(text)
    text = _balance_figure_wrapper_blocks(text)
    try:
        html = markdown2.markdown(text, extras=list(_MARKDOWN_EXTRAS))
    except Exception:
        logger.warning(
            "markdown2 raised on the full pipeline body; retrying block-wise so a "
            "library bug cannot fail the import."
        )
        html = _markdown_pipeline_blockwise(text)
    html = _restore_embed_figures(html, embeds)
    return _inject_heading_anchors(html)


def _only_simple_containers(soup: BeautifulSoup) -> bool:
    for el in soup.find_all(True):
        name = (el.name or "").lower()
        if name not in _SIMPLE_CONTAINER_TAGS:
            return False
    return True


def _unwrap_simple_paragraph_html(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    if not _only_simple_containers(soup):
        return None
    text = soup.get_text("\n\n").strip()
    return text if text else None


def _looks_like_markdown_source(raw: str) -> bool:
    return any(p.search(raw) for p in _MARKDOWN_SOURCE_HINTS)


def prepare_blog_content_for_storage(raw: str) -> str:
    """
    Normalize body for ``Post.content_raw``: Markdown -> HTML, then sanitize.
    Existing Quill HTML (headings, lists, figures, inline styles) is sanitized only.
    """
    raw = (raw or "").strip()
    if not raw:
        return ""

    lower = raw.lower()
    if any(m.lower() in lower for m in _RICH_MARKERS):
        return sanitize_blog_html(raw)

    if "<" not in raw:
        return markdown_to_blog_html(raw)

    soup = BeautifulSoup(raw, "html.parser")
    if _looks_like_markdown_source(raw):
        if _only_simple_containers(soup):
            unwrapped = _unwrap_simple_paragraph_html(raw)
            return markdown_to_blog_html(unwrapped if unwrapped else raw)
        return markdown_to_blog_html(raw)

    if not _only_simple_containers(soup):
        return sanitize_blog_html(raw)

    unwrapped = _unwrap_simple_paragraph_html(raw)
    if unwrapped is None:
        return sanitize_blog_html(raw)

    return markdown_to_blog_html(unwrapped)


def _div_classes(el) -> list[str]:
    raw = el.get("class")
    if not raw:
        return []
    if isinstance(raw, str):
        return raw.split()
    return list(raw)


def _get_blog_html_to_markdown_converter_cls() -> type | None:
    """Return converter class, or None if markdownify is not installed."""
    global _blog_converter_cls, _blog_converter_cls_resolved
    if _blog_converter_cls_resolved:
        return _blog_converter_cls
    _blog_converter_cls_resolved = True
    try:
        from markdownify import MarkdownConverter
    except ImportError:
        logger.warning("markdownify is not installed; HTML->Markdown for post edit is disabled.")
        _blog_converter_cls = None
        return None

    class _BlogHtmlToMarkdownConverter(MarkdownConverter):
        """Map Quill-era HTML back to Markdown-friendly source where possible."""

        def convert_figure(self, el, text, parent_tags):
            img = el.find("img")
            cap_el = el.find("figcaption")
            if not img:
                body = (text or "").strip()
                return f"\n\n{body}\n\n" if body else ""
            src = (img.get("src") or "").strip()
            alt = (img.get("alt") or "").strip()
            if cap_el:
                cap = cap_el.get_text(strip=True)
                if not alt and cap:
                    alt = cap
                line = f"![{alt}]({src})\n\n*{cap}*" if cap else f"![{alt}]({src})"
            else:
                line = f"![{alt}]({src})"
            return f"\n\n{line}\n\n"

        def convert_div(self, el, text, parent_tags):
            if "in-content-read" in _div_classes(el):
                return f"\n\n{str(el).strip()}\n\n"
            return super().convert_div(el, text, parent_tags)

    _blog_converter_cls = _BlogHtmlToMarkdownConverter
    return _blog_converter_cls


def _html_to_plain_for_edit(html: str) -> str:
    """Last-resort editable text when HTML->Markdown conversion cannot run."""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text("\n\n").strip()


def html_to_markdown_for_edit(html: str) -> str:
    """
    Populate the Markdown editor when editing a post that stores HTML in ``content_raw``.
    Plain text (no tags) is returned unchanged.

    On failure (e.g. missing ``markdownify``, very deeply nested HTML -> RecursionError),
    falls back to visible plain text so the admin edit page still loads.
    """
    html = (html or "").strip()
    if not html:
        return ""
    if "<" not in html:
        return html

    if len(html) > _MAX_HTML_TO_MARKDOWN_CHARS:
        logger.warning(
            "html_to_markdown_for_edit: HTML exceeds size limit; using plain-text fallback.",
            extra={"html_len": len(html)},
        )
        try:
            return _html_to_plain_for_edit(html)
        except Exception:
            return ""

    Converter = _get_blog_html_to_markdown_converter_cls()
    if Converter is None:
        try:
            return _html_to_plain_for_edit(html)
        except Exception:
            return ""

    try:
        md = Converter(
            heading_style="ATX",
            bullets="-",
            autolinks=False,
            strip=["script", "style"],
        ).convert(html)
        return (md or "").strip()
    except RecursionError:
        logger.warning(
            "html_to_markdown_for_edit: recursion limit hit (likely very deep HTML); "
            "using plain-text fallback.",
            extra={"html_len": len(html)},
        )
        try:
            return _html_to_plain_for_edit(html)
        except Exception:
            return ""
    except Exception:
        logger.exception(
            "html_to_markdown_for_edit failed; using plain-text fallback.",
            extra={"html_len": len(html)},
        )
        try:
            return _html_to_plain_for_edit(html)
        except Exception:
            return ""
