"""Opt-in ``keel_cms`` URL namespace.

keel-cms is URLconf-agnostic: its model methods and schema builders reverse names
under the ``keel_cms`` namespace (``keel_cms:post_detail``,
``keel_cms:trading_glossary_term``, ...) but the package ships no urlpatterns. A
host opts in by including this module; ``app_name`` MUST stay ``keel_cms`` so those
reverses resolve. Paths are kept minimal and generic — a fork overrides views or
templates by shadowing, not by editing this module.
"""

from django.urls import path

from . import views
from ..feeds import BlogRssFeed

app_name = "keel_cms"

urlpatterns = [
    path("", views.home, name="home"),
    path("feed/blog.xml", BlogRssFeed(), name="blog_rss_feed"),
    path("blog/", views.post_list, name="post_list"),
    path("blog/<slug:slug>/", views.post_detail, name="post_detail"),
    path("topic/<slug:slug>/", views.topic_list, name="topic_list"),
    path("tag/<slug:slug>/", views.tag_detail, name="tag_detail"),
    path("trading-glossary/", views.trading_glossary, name="trading_glossary"),
    path(
        "trading-glossary/<slug:slug>/",
        views.trading_glossary_term,
        name="trading_glossary_term",
    ),
    path("team/<slug:slug>/", views.team_desk, name="team_desk"),
    # News — the two-segment topic/author routes precede the single-segment
    # detail route so the slug matcher never swallows "topic" / "author".
    path("news/", views.news_post_list, name="news_post_list"),
    path("news/topic/<slug:slug>/", views.news_topic_list, name="news_topic_list"),
    path("news/author/<slug:slug>/", views.news_author_list, name="news_author_list"),
    path("news/<slug:slug>/", views.news_post_detail, name="news_post_detail"),
]
