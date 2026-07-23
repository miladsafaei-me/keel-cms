from django.apps import AppConfig


class KeelCmsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "keel_cms"
    verbose_name = "Keel CMS — Blog / News / Glossary"

    def ready(self):
        from . import signals  # noqa: F401  (wire the sidebar cache-invalidation receivers)
