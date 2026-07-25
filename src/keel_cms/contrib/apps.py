"""AppConfig for the opt-in keel-cms presentation layer.

A host opts into the reference admin by BOTH adding ``"keel_cms.contrib"`` to
``INSTALLED_APPS`` and setting ``KEEL_CMS_CONTRIB_ADMIN = True``. The main
``keel_cms`` AppConfig is untouched — importing the engine never pulls in contrib.
The URLconf (``keel_cms.contrib.urls``) is independent of this AppConfig; a host can
include it whether or not ``keel_cms.contrib`` is installed as an app.
"""

from django.apps import AppConfig
from django.conf import settings


class KeelCmsContribConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "keel_cms.contrib"
    label = "keel_cms_contrib"
    verbose_name = "Keel CMS — public presentation (opt-in)"

    def ready(self):
        if getattr(settings, "KEEL_CMS_CONTRIB_ADMIN", False):
            from . import admin as contrib_admin

            contrib_admin.register()
