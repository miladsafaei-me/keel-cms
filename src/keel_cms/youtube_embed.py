"""Whether a YouTube video may be embedded on a page at all.

A video's owner can switch embedding off at any time, for any video, without
notice. When they do, an ``<iframe>`` pointing at that video no longer plays:
YouTube serves its own error box reading "Video unavailable / Watch on YouTube",
so a page that embedded it silently degrades into a dead grey rectangle. Nothing
in the embed URL or in our own data says this has happened -- the only source of
truth is the YouTube Data API, whose ``status.embeddable`` flag reports the
owner's setting.

This module is that check. It answers for a URL or a bare video id, batches up to
fifty ids per API call, caches each verdict, and never raises on a network or
quota failure: an unreachable API returns ``None`` (unknown) rather than a false
"not embeddable", so a missing key can never blank a video that is in fact fine.

The host supplies the key as ``KEEL_CMS["youtube_api_key"]`` (a YouTube Data API
v3 key). With no key configured every verdict is ``None`` and every gate built on
this module degrades to a pass-through, which is what keeps keel-cms usable with
no configuration.

Two things this module deliberately does not do. It does not decide *policy* --
whether a host clears the URL, swaps in another video, or renders a plain link is
the host's call, because only the host knows what its pages are for. And it does
not schedule itself: a verdict is a snapshot of an owner's setting today, so a
host that renders embeds needs its own periodic re-check.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass

from django.core.cache import cache
from django.core.exceptions import ValidationError

from .config import cms_setting

logger = logging.getLogger(__name__)

API_URL = "https://www.googleapis.com/youtube/v3/videos"

# watch?v=ID | youtu.be/ID | shorts/ID | embed/ID - the 11-char YouTube video id.
YOUTUBE_ID_RE = re.compile(
    r"(?:youtube(?:-nocookie)?\.com/(?:watch\?(?:[^#\s]*&)?v=|embed/|shorts/)|youtu\.be/)"
    r"([A-Za-z0-9_-]{11})"
)

# A bare 11-char id, for callers that already parsed the URL.
_BARE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

_CACHE_PREFIX = "keel_cms:yt_embed:"

# An owner who allows embedding rarely revokes it, so a pass is cached for a week.
# A block is re-checked daily, because that is the state we want to stop honouring
# as soon as it is lifted.
_TTL_EMBEDDABLE = 7 * 24 * 3600
_TTL_BLOCKED = 24 * 3600

_BATCH = 50


@dataclass(frozen=True)
class EmbedStatus:
    """One video's embed verdict.

    ``embeddable`` is the only field a caller normally needs: ``True`` the owner
    allows it, ``False`` the owner blocked it or the video is gone, ``None`` we
    could not find out (no API key, network error, quota exhausted).
    """

    video_id: str
    embeddable: bool | None
    exists: bool | None = None
    privacy_status: str = ""
    title: str = ""
    channel_title: str = ""
    reason: str = ""

    @property
    def known(self) -> bool:
        return self.embeddable is not None

    @property
    def blocked(self) -> bool:
        """True only when we positively know the video cannot be embedded."""
        return self.embeddable is False


def video_id(url_or_id: str) -> str:
    """The 11-char YouTube id in ``url_or_id``, or "" when there is none."""
    value = (url_or_id or "").strip()
    if _BARE_ID_RE.match(value):
        return value
    m = YOUTUBE_ID_RE.search(value)
    return m.group(1) if m else ""


def api_key() -> str:
    return (cms_setting("youtube_api_key") or "").strip()


def probe(url_or_ids, *, force: bool = False, timeout: int = 10) -> dict[str, EmbedStatus]:
    """Verdicts for every video in ``url_or_ids``, keyed by video id.

    URLs and bare ids may be mixed; anything unparseable is skipped. Cached
    verdicts are reused unless ``force`` is set, and the rest are fetched in
    batches of fifty. An id the API does not return is a deleted or private
    video, reported as ``embeddable=False`` with ``exists=False`` -- it cannot be
    embedded either, which is what a caller is asking about.
    """
    ids: list[str] = []
    for raw in url_or_ids:
        vid = video_id(raw)
        if vid and vid not in ids:
            ids.append(vid)
    if not ids:
        return {}

    out: dict[str, EmbedStatus] = {}
    pending = ids
    if not force:
        pending = []
        for vid in ids:
            hit = cache.get(_CACHE_PREFIX + vid)
            if isinstance(hit, EmbedStatus):
                out[vid] = hit
            else:
                pending.append(vid)
    if not pending:
        return out

    key = api_key()
    if not key:
        for vid in pending:
            out[vid] = EmbedStatus(vid, None, reason="no KEEL_CMS['youtube_api_key'] configured")
        return out

    for start in range(0, len(pending), _BATCH):
        batch = pending[start:start + _BATCH]
        try:
            items = _fetch(batch, key, timeout)
        except Exception as exc:  # noqa: BLE001 -- an unreachable API is "unknown", never "blocked"
            logger.warning("keel_cms.youtube_embed: probe failed for %d ids: %s", len(batch), exc)
            for vid in batch:
                out[vid] = EmbedStatus(vid, None, reason=f"probe failed: {exc}")
            continue

        seen = set()
        for item in items:
            vid = item.get("id", "")
            seen.add(vid)
            status = item.get("status", {}) or {}
            snippet = item.get("snippet", {}) or {}
            st = EmbedStatus(
                video_id=vid,
                embeddable=bool(status.get("embeddable")),
                exists=True,
                privacy_status=status.get("privacyStatus", ""),
                title=snippet.get("title", ""),
                channel_title=snippet.get("channelTitle", ""),
                reason="" if status.get("embeddable") else "owner disabled embedding",
            )
            out[vid] = st
            _remember(st)
        for vid in batch:
            if vid not in seen:
                st = EmbedStatus(vid, False, exists=False,
                                 reason="video not found (deleted or private)")
                out[vid] = st
                _remember(st)
    return out


def status_for(url_or_id: str, *, force: bool = False) -> EmbedStatus:
    """The verdict for a single video."""
    vid = video_id(url_or_id)
    if not vid:
        return EmbedStatus("", None, reason="no YouTube video id in the value")
    return probe([vid], force=force).get(vid) or EmbedStatus(vid, None, reason="no verdict")


def is_embeddable(url_or_id: str, *, force: bool = False) -> bool | None:
    """``True`` / ``False`` / ``None`` (unknown) for one video."""
    return status_for(url_or_id, force=force).embeddable


def validate_embeddable(url_or_id: str) -> None:
    """Raise ``ValidationError`` when the video is positively not embeddable.

    Written for a form's ``clean_<field>``. An unknown verdict passes: a form
    must not reject an editor's URL because our API key is missing or Google is
    briefly unreachable.
    """
    value = (url_or_id or "").strip()
    if not value:
        return
    st = status_for(value)
    if not st.video_id:
        raise ValidationError("That does not look like a YouTube video URL.")
    if st.blocked:
        if st.exists is False:
            raise ValidationError(
                "That video is no longer available on YouTube (deleted or made private), "
                "so it cannot be shown on the page. Pick another video."
            )
        raise ValidationError(
            "The owner of that video has disabled embedding, so it would render as "
            "YouTube's 'Video unavailable' box instead of playing. Pick another video "
            "that covers the same ground, or leave this blank."
        )


def _fetch(ids: list[str], key: str, timeout: int) -> list[dict]:
    query = urllib.parse.urlencode({"part": "status,snippet", "id": ",".join(ids), "key": key})
    req = urllib.request.Request(f"{API_URL}?{query}", headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.load(resp)
    return payload.get("items", []) or []


def _remember(st: EmbedStatus) -> None:
    ttl = _TTL_EMBEDDABLE if st.embeddable else _TTL_BLOCKED
    try:
        cache.set(_CACHE_PREFIX + st.video_id, st, ttl)
    except Exception:  # noqa: BLE001 -- a cache backend outage must not break a page
        logger.debug("keel_cms.youtube_embed: could not cache verdict for %s", st.video_id)
