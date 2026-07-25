"""Batteries-included admin URLconf — makes the admin-os panel the ONLY admin.

Include it once at the site root:

    path("", include("keel_cms.admin_os.site_urls"))

and a keel-cms host gets the full "admin-os is the admin" wiring in one line:

  * Django's default admin at ``/admin/`` is **hidden** — that path bounces to the
    admin-os dashboard, so the raw Django admin is never displayed and content is
    never authored through its default forms.
  * Django's own admin (login + superuser user/group management) is **remounted**
    under ``/staff/django/``. Point the host's auth settings at it:
        LOGIN_URL = "/staff/django/login/"
        LOGIN_REDIRECT_URL = "/staff/cms/"
  * The admin-os panel is mounted at ``/staff/cms/`` (namespace ``keel_cms_admin``).

A host that needs different prefixes wires the three patterns below by hand instead
of including this module.
"""
from django.contrib import admin
from django.urls import include, path, re_path

from . import views

urlpatterns = [
    # Hide the well-known /admin/ — bounce it to the admin-os panel. Must precede
    # the remounted admin so /admin/* never resolves to Django's raw surface.
    re_path(r"^admin(?:/|$)", views.blocked_admin),
    # Django's admin, remounted for login + superuser-only user/group management.
    path("staff/django/", admin.site.urls),
    # The admin-os staff panel (custom DB-driven forms + 3-tab editor).
    path("staff/cms/", include("keel_cms.admin_os.urls")),
]
