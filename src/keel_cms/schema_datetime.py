"""
UTC-normalized datetimes for public SEO output (JSON-LD, Open Graph, meta).

Naive values are interpreted as UTC. Never use Django's TIME_ZONE for these
strings — crawlers and specs expect UTC or zoneless calendar dates.
"""

from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

from django.utils import timezone as django_tz


def isoformat_utc_public(dt: datetime | None) -> str | None:
    """
    Return an ISO-8601 instant in UTC with a ``Z`` suffix, e.g. ``2024-03-15T14:30:00Z``.

    Used for schema.org ``datePublished`` / ``dateModified`` and similar fields.
    """
    if dt is None:
        return None
    try:
        if django_tz.is_naive(dt):
            dt = django_tz.make_aware(dt, dt_timezone.utc)
        else:
            dt = dt.astimezone(dt_timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    except (ValueError, OverflowError, OSError):
        return None
