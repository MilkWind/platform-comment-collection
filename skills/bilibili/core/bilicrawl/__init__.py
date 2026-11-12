"""Bilibili comment + danmaku core.

This package is the copy-paste unit: it imports only the standard library,
``requests``, and ``protobuf``. It exposes the *main APIs* and nothing about
rate limits, retries, checkpoints, or UI — those are abstract strategies the
outer layer implements (see ``references/strategies.md``).

Quick start::

    import bilicrawl
    adapter = bilicrawl.create_adapter({"cookie": ""})   # anonymous is fine
    video = adapter.resolve_video("BV1GJ411x7h7")
    page = adapter.comment_page(mode=3)
    seg = adapter.danmaku_segment(adapter.danmaku_targets()[0])
"""

from __future__ import annotations

from .adapter import BilibiliAdapter
from .credentials import CONSOLE_SNIPPET, normalize
from .fields import default_fields, field_catalog
from .http import RequestsTransport, Transport, TransportResponse
from .input import parse_input
from .models import (
    AuthStatus,
    Comment,
    CommentPage,
    CredentialField,
    Danmaku,
    DanmakuSegment,
    DanmakuTarget,
    FieldSpec,
    ParsedInput,
    SubReplyPage,
    VideoPart,
    VideoRef,
)

PLATFORM_ID = "bilibili"
PLATFORM_NAME_EN = "Bilibili"
PLATFORM_NAME_ZH = "哔哩哔哩"
KINDS = ("comments", "danmaku")


def credential_fields() -> list[CredentialField]:
    return [
        CredentialField(
            key="cookie",
            label_en="Cookie (optional)",
            label_zh="Cookie（可选）",
            required=False,
            secret=True,
            console_snippet=CONSOLE_SNIPPET,
            help_en=(
                "Anonymous works. Logging in unlocks IP location and fuller sub-replies. "
                "Run the snippet in the browser console, or paste a cURL copied from DevTools."
            ),
            help_zh=(
                "匿名即可使用。登录后可获取 IP 属地并更完整地抓取楼中楼。"
                "可在浏览器控制台运行片段，或在开发者工具中复制 cURL 后粘贴。"
            ),
        )
    ]


def create_adapter(
    credentials: dict[str, str] | None = None, transport: Transport | None = None
) -> BilibiliAdapter:
    return BilibiliAdapter(credentials or {}, transport=transport)


__all__ = [
    "PLATFORM_ID",
    "PLATFORM_NAME_EN",
    "PLATFORM_NAME_ZH",
    "KINDS",
    "BilibiliAdapter",
    "AuthStatus",
    "Comment",
    "CommentPage",
    "CredentialField",
    "Danmaku",
    "DanmakuSegment",
    "DanmakuTarget",
    "FieldSpec",
    "ParsedInput",
    "RequestsTransport",
    "SubReplyPage",
    "Transport",
    "TransportResponse",
    "VideoPart",
    "VideoRef",
    "create_adapter",
    "credential_fields",
    "default_fields",
    "field_catalog",
    "normalize",
    "parse_input",
]
