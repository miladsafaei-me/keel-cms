"""Opt-in public presentation layer for keel-cms.

The keel-cms engine ships models, a render pipeline, and schema builders but no
public views, URLconf, admin, or templates — a consumer normally hand-writes those.
This ``contrib`` subpackage is an OPT-IN reference presentation so a fork can wire
the whole public site with one line and override any piece by shadowing:

    # host urls.py
    path("", include("keel_cms.contrib.urls")),   # app_name = "keel_cms"

Importing ``keel_cms`` does NOT import ``keel_cms.contrib``; nothing here runs until
the host explicitly includes the URLconf and/or opts into the admin via the
``KEEL_CMS_CONTRIB_ADMIN`` setting.
"""
