"""Generic template tags for host base templates."""

from django import template
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html

from ..config import cms_setting

register = template.Library()


@register.simple_tag(takes_context=True)
def blog_feed_link(context):
    """Render the RSS <link rel="alternate"> tag for the blog feed.

    Reverses ``keel_cms:blog_rss_feed`` — the name every host registers its feed
    route under, whether served directly from ``keel_cms.contrib.urls`` or aliased
    from a host-owned route (see ``keel_cms.contrib.urls`` docstring on the
    URLconf-agnostic pattern). A host with no feed route wired renders nothing, so
    dropping this tag into a shared base template is always safe.
    """
    try:
        href = reverse("keel_cms:blog_rss_feed")
    except NoReverseMatch:
        return ""
    request = context.get("request")
    if request is not None:
        href = request.build_absolute_uri(href)
    site_name = cms_setting("site_name") or ""
    title = f"{site_name} Blog".strip() if site_name else "Blog"
    return format_html(
        '<link rel="alternate" type="application/rss+xml" title="{}" href="{}">',
        title,
        href,
    )
