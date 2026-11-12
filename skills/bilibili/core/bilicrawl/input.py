"""Parse user input into a video reference.

Accepted forms:
    - raw BV id:      BV1GJ411x7h7
    - raw av id:      av170001 / AV170001
    - full URL:       https://www.bilibili.com/video/BV1GJ411x7h7/?p=2
    - short link:     https://b23.tv/AbCdEfG  (resolved with a network redirect)
"""

from __future__ import annotations

import re

from .models import ParsedInput

_BV_RE = re.compile(r"BV([0-9A-Za-z]{10})")
_AV_RE = re.compile(r"(?:^|[/?&])av(\d+)", re.IGNORECASE)
_PAGE_RE = re.compile(r"[?&]p=(\d+)")
_SHORT_HOSTS = ("b23.tv", "bili2233.cn")


def parse_input(raw: str) -> ParsedInput:
    """Offline parse; short links are detected but not resolved here.

    The adapter resolves a ``shortlink`` with one network redirect before
    calling :func:`parse_resolved`.
    """
    text = (raw or "").strip()
    if not text:
        return ParsedInput(kind="unknown", error="empty input")

    if any(host in text for host in _SHORT_HOSTS) and "bilibili.com" not in text:
        return ParsedInput(kind="shortlink", page_hint=_page_hint(text))

    bv = _BV_RE.search(text)
    if bv:
        kind = "bvid" if _BV_RE.fullmatch(text) else "url"
        return ParsedInput(kind=kind, video_id=bv.group(0), page_hint=_page_hint(text))

    av = _AV_RE.search(text)
    if av:
        kind = "avid" if text.lower().startswith("av") else "url"
        return ParsedInput(kind=kind, aid=int(av.group(1)), video_id=None)

    return ParsedInput(kind="unknown", error="no BV id or av id found")


def parse_resolved(final_url: str) -> ParsedInput:
    """Parse an input that may be a redirect target (used after resolving short links)."""
    return parse_input(final_url)


def _page_hint(text: str) -> int | None:
    m = _PAGE_RE.search(text)
    if not m:
        return None
    page = int(m.group(1))
    return page if page >= 1 else None
