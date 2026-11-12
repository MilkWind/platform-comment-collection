"""Resolve a video reference into full metadata (aid, cid per part)."""

from __future__ import annotations

from urllib.parse import quote

from .errors import NotFound, ProtocolError
from .http import Transport, get_json
from .models import ParsedInput, VideoPart, VideoRef

VIEW_URL = "https://api.bilibili.com/x/web-interface/view"


def resolve_video(transport: Transport, parsed: ParsedInput) -> VideoRef:
    """Fetch video metadata and build the ``VideoRef`` with one part per page."""
    if parsed.aid is not None:
        params: dict[str, object] = {"aid": parsed.aid}
    elif parsed.video_id:
        params = {"bvid": parsed.video_id}
    else:  # pragma: no cover - guarded by parse_input
        raise ProtocolError("no video id to resolve")

    data = get_json(transport, VIEW_URL, params)
    if not data:
        raise NotFound("video not found")

    aid = int(data.get("aid", 0))
    pages = data.get("pages") or []
    parts: list[VideoPart] = []
    if pages:
        for p in pages:
            parts.append(
                VideoPart(
                    index=int(p.get("page", len(parts) + 1)),
                    part_id=str(p.get("cid", "")),
                    title=str(p.get("part", "") or ""),
                    duration_sec=int(p.get("duration", 0) or 0),
                )
            )
    else:
        # Defensive: single-part videos always carry top-level cid.
        parts.append(
            VideoPart(
                index=1,
                part_id=str(data.get("cid", "")),
                title=str(data.get("title", "") or ""),
                duration_sec=int(data.get("duration", 0) or 0),
            )
        )

    owner = data.get("owner") or {}
    return VideoRef(
        video_id=str(data.get("bvid") or parsed.video_id or ""),
        title=str(data.get("title", "") or ""),
        owner_mid=str(owner.get("mid", "") or ""),
        owner_name=str(owner.get("name", "") or ""),
        duration_sec=int(data.get("duration", 0) or 0),
        aid=aid,
        parts=parts,
    )


def video_page_url(bvid: str) -> str:
    return f"https://www.bilibili.com/video/{quote(bvid)}"
