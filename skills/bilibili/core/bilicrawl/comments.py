"""Comment endpoints: cursor-paginated roots and page-numbered sub-replies.

Root comments use the modern WBI-signed cursor API (``/x/v2/reply/wbi/main``),
which we verified works logged-out. The legacy page-number API is intentionally
not implemented: it returns incomplete data when anonymous and is hard-capped.
"""

from __future__ import annotations

import json
from typing import Any

from .errors import ProtocolError, WbiStale
from .http import Transport, get_json
from .models import Comment, CommentPage, SubReplyPage
from .wbi import WbiKeyCache, sign_query

COMMENT_MAIN_URL = "https://api.bilibili.com/x/v2/reply/wbi/main"
SUB_REPLY_URL = "https://api.bilibili.com/x/v2/reply/reply"


def _pagination_str(cursor: str | None) -> str:
    offset = cursor or ""
    return json.dumps({"offset": offset}, separators=(",", ":"), ensure_ascii=False)


def fetch_comment_page(
    transport: Transport,
    keys: WbiKeyCache,
    *,
    aid: int,
    cursor: str | None = None,
    mode: int = 3,
    page_size: int = 30,
) -> CommentPage:
    """Fetch one page of root comments.

    ``mode``: 2 = time order, 3 = hot order (adapter-interpreted).
    """
    params = {
        "oid": aid,
        "type": 1,
        "mode": mode,
        "pagination_str": _pagination_str(cursor),
        "plat": 1,
        "seek_rpid": "",
        "web_location": 1315875,
        "ps": page_size,
    }
    img_key, sub_key = keys.get()
    query = sign_query(params, img_key, sub_key)
    try:
        data = _get_signed_json(transport, COMMENT_MAIN_URL, query)
    except WbiStale:
        # A stale signature is a signing concern, so refresh keys once here
        # rather than pushing it to the outer retry policy.
        img_key, sub_key = keys.get(force=True)
        query = sign_query(params, img_key, sub_key)
        data = _get_signed_json(transport, COMMENT_MAIN_URL, query)
    return _parse_comment_page(data)


def _get_signed_json(transport: Transport, url: str, query: str) -> dict:
    resp = transport.request("GET", f"{url}?{query}")
    return _decode_data(resp.content, url)


def _decode_data(content: bytes, url: str) -> dict:
    from .errors import classify_api_code

    try:
        payload = json.loads(content)
    except (ValueError, UnicodeDecodeError) as exc:  # pragma: no cover - defensive
        raise ProtocolError(f"invalid JSON from {url}: {exc}", url=url) from exc
    code = payload.get("code")
    if code != 0:
        raise classify_api_code(int(code), payload.get("message", ""), url=url)
    return payload.get("data") or {}


def _parse_comment_page(data: dict) -> CommentPage:
    cursor = data.get("cursor") or {}
    pagination = cursor.get("pagination_reply") or {}
    next_offset = pagination.get("next_offset") or None
    is_end = bool(cursor.get("is_end")) or not next_offset

    pinned: list[Comment] = []
    for raw in data.get("top_replies") or []:
        if int(raw.get("root", 0)) == 0:
            pinned.append(_parse_comment(raw, is_pinned=True))

    roots: list[Comment] = []
    previews: dict[str, list[Comment]] = {}
    for raw in data.get("replies") or []:
        comment = _parse_comment(raw)
        roots.append(comment)
        reply_preview = raw.get("replies") or []
        if reply_preview:
            previews[comment.id] = [_parse_comment(r) for r in reply_preview]

    return CommentPage(
        roots=roots,
        pinned=pinned,
        next_cursor=next_offset,
        is_end=is_end,
        total_all=cursor.get("all_count"),
        previews=previews,
    )


def fetch_sub_reply_page(
    transport: Transport,
    *,
    aid: int,
    root_id: str,
    page: int = 1,
    page_size: int = 20,
) -> SubReplyPage:
    """Fetch one page of sub-replies for a root comment (no WBI required)."""
    params = {"type": 1, "oid": aid, "root": root_id, "pn": page, "ps": page_size}
    data = get_json(transport, SUB_REPLY_URL, params)
    replies = [_parse_comment(r) for r in data.get("replies") or []]
    page_info = data.get("page") or {}
    total = page_info.get("count")
    total = int(total) if total is not None else None
    is_end = not replies or (total is not None and page * page_size >= total)
    return SubReplyPage(replies=replies, page=page, is_end=is_end, total=total)


def _parse_comment(raw: dict[str, Any], *, is_pinned: bool = False) -> Comment:
    content = raw.get("content") or {}
    member = raw.get("member") or {}
    level_info = member.get("level_info") or {}
    control = raw.get("reply_control") or {}

    pictures: list[str] = []
    for pic in content.get("pictures") or []:
        src = pic.get("img_src")
        if src:
            pictures.append(f"https:{src}" if src.startswith("//") else src)

    location = control.get("location")
    if location:
        location = location.replace("IP属地：", "").replace("IP属地:", "").strip() or None

    return Comment(
        id=str(raw.get("rpid_str") or raw.get("rpid", "")),
        root_id=str(raw.get("root_str") or raw.get("root", "")),
        parent_id=str(raw.get("parent_str") or raw.get("parent", "")),
        user_id=str(raw.get("mid_str") or raw.get("mid", "")),
        user_name=str(member.get("uname", "") or ""),
        content=str(content.get("message", "") or ""),
        like_count=int(raw.get("like", 0) or 0),
        reply_count=int(raw.get("rcount", 0) or 0),
        created_at=int(raw.get("ctime", 0) or 0),
        location=location,
        sex=member.get("sex"),
        level=int(level_info.get("current", 0) or 0),
        pictures=pictures,
        is_pinned=is_pinned,
    )
