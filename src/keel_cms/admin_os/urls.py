"""URLconf for the keel-cms Admin OS panel.

Opt-in only: a host mounts it with ``path("<prefix>/", include("keel_cms.admin_os.urls"))``.
Nothing auto-registers, and no ``contrib.admin`` model registration happens, so the
Django default admin stays off these models.
"""
from django.urls import path

from . import views

app_name = "keel_cms_admin"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    # Blog posts
    path("blog/", views.PostListView.as_view(), name="post_list"),
    path("blog/new/", views.PostCreateView.as_view(), name="post_create"),
    path("blog/<uuid:pk>/edit/", views.PostUpdateView.as_view(), name="post_edit"),
    path("blog/<uuid:pk>/delete/", views.PostDeleteView.as_view(), name="post_delete"),
    # News articles
    path("news/", views.NewsPostListView.as_view(), name="news_post_list"),
    path("news/new/", views.NewsPostCreateView.as_view(), name="news_post_create"),
    path("news/<uuid:pk>/edit/", views.NewsPostUpdateView.as_view(), name="news_post_edit"),
    path("news/<uuid:pk>/delete/", views.NewsPostDeleteView.as_view(), name="news_post_delete"),
    # Authors
    path("authors/", views.AuthorListView.as_view(), name="author_list"),
    path("authors/new/", views.AuthorCreateView.as_view(), name="author_create"),
    path("authors/<uuid:pk>/edit/", views.AuthorUpdateView.as_view(), name="author_edit"),
    # Topics (Category) — combined list + inline create
    path("topics/", views.CategoryListView.as_view(), name="category_list"),
    path("topics/<uuid:pk>/edit/", views.CategoryUpdateView.as_view(), name="category_edit"),
    path("topics/<uuid:pk>/delete/", views.CategoryDeleteView.as_view(), name="category_delete"),
    # Tags — combined list + inline create
    path("tags/", views.TagListView.as_view(), name="tag_list"),
    path("tags/<int:pk>/edit/", views.TagUpdateView.as_view(), name="tag_edit"),
    path("tags/<int:pk>/delete/", views.TagDeleteView.as_view(), name="tag_delete"),
    # Editor endpoints
    path("content/convert/", views.content_convert, name="content_convert"),
    path("images/upload/", views.upload_image, name="upload_image"),
    path("images/generate-featured/", views.generate_featured_image, name="generate_featured_image"),
    path("images/generate-inline/", views.generate_inline_image, name="generate_inline_image"),
]
