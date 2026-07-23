"""Invalidate blog/news sidebar caches when taxonomy or published content changes,
and keep a produced Post's ContentPlan row in step with its publish state.

Both blog and news receivers are wired here; ``apps.KeelCmsConfig.ready`` imports
this module so the receivers connect once at app startup.
"""

from django.db.models.signals import m2m_changed, post_delete, post_save

from .models import Author, Category, ContentScope, NewsPost, Post, Tag
from .news_sidebar_cache import invalidate_news_sidebar_cache
from .sidebar_cache import invalidate_blog_sidebar_cache


def _connect() -> None:
    # Blog sidebar + content-plan sync
    post_save.connect(
        _on_post_save_or_delete, sender=Post, dispatch_uid="keel_cms_blog_sidebar_invalidate_post_save"
    )
    post_delete.connect(
        _on_post_save_or_delete, sender=Post, dispatch_uid="keel_cms_blog_sidebar_invalidate_post_delete"
    )
    m2m_changed.connect(
        _on_post_tags_changed,
        sender=Post.tags.through,
        dispatch_uid="keel_cms_blog_sidebar_invalidate_post_tags",
    )
    post_save.connect(
        _on_category_or_tag_save,
        sender=Category,
        dispatch_uid="keel_cms_blog_sidebar_invalidate_category",
    )
    post_save.connect(
        _on_category_or_tag_save, sender=Tag, dispatch_uid="keel_cms_blog_sidebar_invalidate_tag"
    )
    post_save.connect(
        _on_author_save, sender=Author, dispatch_uid="keel_cms_blog_sidebar_invalidate_author"
    )
    post_save.connect(
        _on_post_save_sync_plan, sender=Post, dispatch_uid="keel_cms_content_plan_status_sync"
    )

    # News sidebar
    post_save.connect(
        _on_news_post_change,
        sender=NewsPost,
        dispatch_uid="keel_cms_news_sidebar_invalidate_post_save",
    )
    post_delete.connect(
        _on_news_post_change,
        sender=NewsPost,
        dispatch_uid="keel_cms_news_sidebar_invalidate_post_delete",
    )
    m2m_changed.connect(
        _on_news_post_tags_changed,
        sender=NewsPost.tags.through,
        dispatch_uid="keel_cms_news_sidebar_invalidate_post_tags",
    )


def _on_post_save_or_delete(sender, instance, **kwargs) -> None:
    invalidate_blog_sidebar_cache()


def _on_post_save_sync_plan(sender, instance, **kwargs) -> None:
    """Keep the linked ContentPlan row's status in step with its produced Post.

    Closes the production-queue loop on the human side: publishing a draft flips
    its plan row to ``published`` (and un-publishing back to ``drafted``).
    Idempotent and guarded — a post with no plan row is the common case and is a
    no-op.
    """
    from .models import ContentPlan

    plan = ContentPlan.objects.filter(produced_post=instance).first()
    if plan is None:
        return
    new_status = (
        ContentPlan.Status.PUBLISHED
        if instance.status == Post.Status.PUBLISHED
        else ContentPlan.Status.DRAFTED
    )
    if plan.status != new_status:
        plan.status = new_status
        plan.save(update_fields=["status", "updated_at"])


def _on_post_tags_changed(sender, instance, action, **kwargs) -> None:
    if action in ("post_add", "post_remove", "post_clear", "pre_clear"):
        invalidate_blog_sidebar_cache()


def _on_category_or_tag_save(sender, instance, **kwargs) -> None:
    if isinstance(instance, Category):
        if instance.content_scope == ContentScope.BLOG:
            invalidate_blog_sidebar_cache()
        else:
            invalidate_news_sidebar_cache()
        return
    if isinstance(instance, Tag):
        invalidate_blog_sidebar_cache()
        invalidate_news_sidebar_cache()


def _on_author_save(sender, instance, **kwargs) -> None:
    invalidate_blog_sidebar_cache()
    invalidate_news_sidebar_cache()


def _on_news_post_change(sender, instance, **kwargs) -> None:
    invalidate_news_sidebar_cache()


def _on_news_post_tags_changed(sender, instance, action, **kwargs) -> None:
    if action in ("post_add", "post_remove", "post_clear", "pre_clear"):
        invalidate_news_sidebar_cache()


_connect()
