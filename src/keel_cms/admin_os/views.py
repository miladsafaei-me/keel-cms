"""Admin OS views for keel-cms: dashboard, per-model list/create/edit/delete, the
three-tab editor's convert endpoint, and the image upload / AI-generate endpoints.

Every class-based view is gated by ``ContentEditorAccessMixin`` (superusers +
Content-Editor group) as its first base and renders inside keel-web's admin shell
via ``CmsAdminContextMixin``. The image endpoints are thin JSON wrappers over the
generic helpers in ``keel_web.admin_shell`` (WebP upload + Gemini image gen).
"""
from __future__ import annotations

import json
import logging

from django.contrib import messages
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, UpdateView

from keel_web.admin_shell.image_gen import (
    generate_featured_image_media_relative_path,
    generate_inline_image_media_relative_path,
)
from keel_web.admin_shell.image_upload import save_upload_as_webp
from keel_web.admin_shell.permissions import ContentEditorAccessMixin, is_content_editor

from keel_cms.editor_views import content_convert as _cms_content_convert
from keel_cms.models import Author, Category, ContentScope, NewsPost, Post, Tag

from .forms import AuthorForm, CategoryForm, NewsPostForm, PostForm, TagForm
from .mixins import CmsAdminContextMixin, cms_admin_base_context

logger = logging.getLogger(__name__)


class DashboardView(ContentEditorAccessMixin, CmsAdminContextMixin, View):
    page_title = "Dashboard"
    page_pretitle = "Content"

    def get(self, request):
        ctx = cms_admin_base_context(request)
        ctx.update(
            {
                "page_title": self.page_title,
                "page_pretitle": self.page_pretitle,
                "post_count": Post.objects.count(),
                "post_published": Post.objects.filter(status=Post.Status.PUBLISHED).count(),
                "post_draft": Post.objects.filter(status=Post.Status.DRAFT).count(),
                "news_count": NewsPost.objects.count(),
                "news_published": NewsPost.objects.filter(status=NewsPost.Status.PUBLISHED).count(),
                "author_count": Author.objects.count(),
                "topic_count": Category.objects.count(),
                "tag_count": Tag.objects.count(),
                "recent_posts": Post.objects.select_related("author").order_by("-created_at")[:5],
                "recent_news": NewsPost.objects.select_related("author").order_by("-created_at")[:5],
            }
        )
        return render(request, "keel_cms_admin/dashboard.html", ctx)


class _CmsListView(ContentEditorAccessMixin, CmsAdminContextMixin, ListView):
    """Shared paginated list view. Subclasses set model / template / search_fields."""

    paginate_by = 20
    search_fields: tuple[str, ...] = ()

    def get_base_queryset(self):
        return self.model._default_manager.all()

    def get_queryset(self):
        qs = self.get_base_queryset()
        q = self.request.GET.get("q", "").strip()
        if q and self.search_fields:
            cond = Q()
            for field in self.search_fields:
                cond |= Q(**{f"{field}__icontains": q})
            qs = qs.filter(cond)
        status = self.request.GET.get("status", "")
        if status and hasattr(self.model, "Status") and status in dict(self.model.Status.choices):
            qs = qs.filter(status=status)
        cat = self.request.GET.get("category", "")
        if cat:
            qs = qs.filter(category_id=cat)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["current_q"] = self.request.GET.get("q", "")
        ctx["current_status"] = self.request.GET.get("status", "")
        ctx["current_category"] = self.request.GET.get("category", "")
        return ctx


class PostListView(_CmsListView):
    model = Post
    template_name = "keel_cms_admin/post_list.html"
    context_object_name = "posts"
    search_fields = ("title", "slug")
    page_title = "Blog"
    page_pretitle = "Content"

    def get_base_queryset(self):
        return Post.objects.select_related("author", "category").order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = Category.objects.filter(content_scope=ContentScope.BLOG).order_by("name")
        return ctx


class NewsPostListView(_CmsListView):
    model = NewsPost
    template_name = "keel_cms_admin/news_post_list.html"
    context_object_name = "posts"
    search_fields = ("title", "slug")
    page_title = "News"
    page_pretitle = "Content"

    def get_base_queryset(self):
        return NewsPost.objects.select_related("author", "category").order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = Category.objects.filter(content_scope=ContentScope.NEWS).order_by("name")
        return ctx


class _PostEditorMixin(ContentEditorAccessMixin, CmsAdminContextMixin):
    """Shared context (editor endpoint URLs + publish-from-action) for post forms."""

    editor_section = "blog"
    context_object_name = "post"

    def _is_blog(self) -> bool:
        return self.editor_section == "blog"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = getattr(self, "object", None)
        ctx["editor_section"] = self.editor_section
        ctx["editor_post_id"] = str(obj.pk) if obj is not None else ""
        ctx["editor_is_pipeline"] = bool(getattr(obj, "is_pipeline_generated", False))
        ctx["editor_convert_url"] = reverse("keel_cms_admin:content_convert")
        ctx["editor_upload_url"] = reverse("keel_cms_admin:upload_image")
        ctx["editor_featured_url"] = (
            reverse("keel_cms_admin:generate_featured_image") if self._is_blog() else None
        )
        ctx["editor_ai_inline_url"] = (
            reverse("keel_cms_admin:generate_inline_image") if self._is_blog() else None
        )
        return ctx

    def _apply_publish_action(self, form):
        model = form._meta.model
        action = self.request.POST.get("action", "draft")
        form.instance.status = model.Status.PUBLISHED if action == "publish" else model.Status.DRAFT
        if form.instance.status == model.Status.PUBLISHED and not form.cleaned_data.get("published_at"):
            form.instance.published_at = timezone.now()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.method == "GET" and getattr(self, "object", None) is None:
            model = self.form_class._meta.model
            kwargs.setdefault("initial", {}).update(
                {
                    "status": model.Status.PUBLISHED,
                    "published_at": timezone.localtime(timezone.now()).strftime("%Y-%m-%dT%H:%M"),
                }
            )
        return kwargs


class PostCreateView(_PostEditorMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = "keel_cms_admin/post_form.html"
    editor_section = "blog"
    page_title = "Add post"
    page_pretitle = "Blog"

    def form_valid(self, form):
        self._apply_publish_action(form)
        response = super().form_valid(form)
        messages.success(self.request, "Post saved successfully.")
        return response

    def get_success_url(self):
        return reverse("keel_cms_admin:post_list")


class PostUpdateView(_PostEditorMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = "keel_cms_admin/post_form.html"
    editor_section = "blog"
    page_title = "Edit post"
    page_pretitle = "Blog"

    def get_queryset(self):
        return Post.objects.all()

    def form_valid(self, form):
        self._apply_publish_action(form)
        response = super().form_valid(form)
        messages.success(self.request, "Post updated successfully.")
        return response

    def get_success_url(self):
        return reverse("keel_cms_admin:post_list")


class NewsPostCreateView(_PostEditorMixin, CreateView):
    model = NewsPost
    form_class = NewsPostForm
    template_name = "keel_cms_admin/news_post_form.html"
    editor_section = "news"
    page_title = "Add article"
    page_pretitle = "News"

    def form_valid(self, form):
        self._apply_publish_action(form)
        response = super().form_valid(form)
        messages.success(self.request, "News article saved successfully.")
        return response

    def get_success_url(self):
        return reverse("keel_cms_admin:news_post_list")


class NewsPostUpdateView(_PostEditorMixin, UpdateView):
    model = NewsPost
    form_class = NewsPostForm
    template_name = "keel_cms_admin/news_post_form.html"
    editor_section = "news"
    page_title = "Edit article"
    page_pretitle = "News"

    def get_queryset(self):
        return NewsPost.objects.all()

    def form_valid(self, form):
        self._apply_publish_action(form)
        response = super().form_valid(form)
        messages.success(self.request, "News article updated successfully.")
        return response

    def get_success_url(self):
        return reverse("keel_cms_admin:news_post_list")


class _SoftDeleteView(ContentEditorAccessMixin, View):
    model = None
    redirect_name = ""
    label = "Item"

    def post(self, request, pk):
        obj = get_object_or_404(self.model._default_manager, pk=pk)
        if hasattr(obj, "soft_delete"):
            obj.soft_delete(user=request.user)
        else:
            obj.delete()
        messages.success(request, f"{self.label} deleted.")
        return redirect(self.redirect_name)


class PostDeleteView(_SoftDeleteView):
    model = Post
    redirect_name = "keel_cms_admin:post_list"
    label = "Post"


class NewsPostDeleteView(_SoftDeleteView):
    model = NewsPost
    redirect_name = "keel_cms_admin:news_post_list"
    label = "News article"


class AuthorListView(_CmsListView):
    model = Author
    template_name = "keel_cms_admin/author_list.html"
    context_object_name = "authors"
    search_fields = ("name", "slug", "email", "role")
    page_title = "Authors"
    page_pretitle = "Taxonomy"

    def get_base_queryset(self):
        return Author.objects.annotate(
            post_count=Count("posts", distinct=True),
            news_count=Count("news_posts", distinct=True),
        ).order_by("name")


class AuthorCreateView(ContentEditorAccessMixin, CmsAdminContextMixin, CreateView):
    model = Author
    form_class = AuthorForm
    template_name = "keel_cms_admin/author_form.html"
    context_object_name = "author"
    page_title = "Add author"
    page_pretitle = "Taxonomy"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["upload_url"] = reverse("keel_cms_admin:upload_image")
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Author saved successfully.")
        return response

    def get_success_url(self):
        return reverse("keel_cms_admin:author_list")


class AuthorUpdateView(ContentEditorAccessMixin, CmsAdminContextMixin, UpdateView):
    model = Author
    form_class = AuthorForm
    template_name = "keel_cms_admin/author_form.html"
    context_object_name = "author"
    page_title = "Edit author"
    page_pretitle = "Taxonomy"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["upload_url"] = reverse("keel_cms_admin:upload_image")
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Author updated successfully.")
        return response

    def get_success_url(self):
        return reverse("keel_cms_admin:author_list")


class CategoryListView(ContentEditorAccessMixin, View):
    """Combined list + inline create for topics (Category). Both content scopes."""

    def _categories_qs(self):
        return Category.objects.annotate(
            post_count=Count("posts", distinct=True),
            news_count=Count("news_posts", distinct=True),
        ).order_by("content_scope", "name")

    def _render(self, request, form, editing=None):
        ctx = cms_admin_base_context(request)
        ctx.update(
            {
                "page_title": "Topics",
                "page_pretitle": "Taxonomy",
                "categories": self._categories_qs(),
                "form": form,
                "editing_category": editing,
            }
        )
        return render(request, "keel_cms_admin/category_list.html", ctx)

    def get(self, request):
        return self._render(request, CategoryForm())

    def post(self, request):
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Topic created.")
            return redirect("keel_cms_admin:category_list")
        return self._render(request, form)


class CategoryUpdateView(CategoryListView):
    def get(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        return self._render(request, CategoryForm(instance=category), editing=category)

    def post(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Topic updated.")
            return redirect("keel_cms_admin:category_list")
        return self._render(request, form, editing=category)


class CategoryDeleteView(ContentEditorAccessMixin, View):
    def post(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        category.delete()
        messages.success(request, "Topic deleted.")
        return redirect("keel_cms_admin:category_list")


class TagListView(ContentEditorAccessMixin, View):
    """Combined list + inline create for tags (shared across blog and news)."""

    def _tags_qs(self):
        return Tag.objects.annotate(
            blog_post_count=Count("posts", distinct=True),
            news_post_count=Count("news_posts", distinct=True),
        ).order_by("name")

    def _render(self, request, form, editing=None):
        ctx = cms_admin_base_context(request)
        ctx.update(
            {
                "page_title": "Tags",
                "page_pretitle": "Taxonomy",
                "tags": self._tags_qs(),
                "form": form,
                "editing_tag": editing,
            }
        )
        return render(request, "keel_cms_admin/tag_list.html", ctx)

    def get(self, request):
        return self._render(request, TagForm())

    def post(self, request):
        form = TagForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Tag created.")
            return redirect("keel_cms_admin:tag_list")
        return self._render(request, form)


class TagUpdateView(TagListView):
    def get(self, request, pk):
        tag = get_object_or_404(Tag, pk=pk)
        return self._render(request, TagForm(instance=tag), editing=tag)

    def post(self, request, pk):
        tag = get_object_or_404(Tag, pk=pk)
        form = TagForm(request.POST, instance=tag)
        if form.is_valid():
            form.save()
            messages.success(request, "Tag updated.")
            return redirect("keel_cms_admin:tag_list")
        return self._render(request, form, editing=tag)


class TagDeleteView(ContentEditorAccessMixin, View):
    def post(self, request, pk):
        tag = get_object_or_404(Tag, pk=pk)
        tag.delete()
        messages.success(request, "Tag deleted.")
        return redirect("keel_cms_admin:tag_list")


# The three-tab editor's convert endpoint is fully generic in keel_cms.editor_views;
# re-export it under this app's URLconf so templates can reverse
# ``keel_cms_admin:content_convert``.
content_convert = _cms_content_convert


@require_POST
def upload_image(request):
    """Store an uploaded image as WebP under MEDIA_ROOT; return its absolute URL."""
    if not is_content_editor(request.user):
        return JsonResponse({"error": "Unauthorized"}, status=403)
    file = request.FILES.get("file")
    if not file:
        return JsonResponse({"error": "No file provided"}, status=400)
    section = (request.POST.get("section") or "").strip().lower()
    subpath = "news/featured" if section == "news" else "blog/featured"
    try:
        rel = save_upload_as_webp(file, media_subpath=subpath)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({"url": request.build_absolute_uri(f"/media/{rel}")})


def _generate_image(request, generator):
    if not is_content_editor(request.user):
        return JsonResponse({"error": "Unauthorized"}, status=403)
    try:
        body = json.loads(request.body.decode())
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)
    prompt = (body.get("prompt") or "").strip()
    if not prompt:
        return JsonResponse({"error": "Prompt is required."}, status=400)
    try:
        rel = generator(user_prompt=prompt)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except RuntimeError as exc:
        logger.warning("image generation failed: %s", exc)
        return JsonResponse({"error": str(exc)}, status=502)
    return JsonResponse({"url": request.build_absolute_uri(f"/media/{rel}")})


@require_POST
def generate_featured_image(request):
    return _generate_image(request, generate_featured_image_media_relative_path)


@require_POST
def generate_inline_image(request):
    return _generate_image(request, generate_inline_image_media_relative_path)
