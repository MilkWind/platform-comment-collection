"""Layer boundary between platform cores and the outer app.

Cores are *structural*: they never import this module. The engine drives them
by name (``resolve_video``, ``comment_page``, …), which is what lets a new
platform drop in without touching ``app/``. This module only documents the
expected shape for type-checkers and readers.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from skills.bilibili.core.bilicrawl.models import (
    AuthStatus,
    CommentPage,
    DanmakuSegment,
    DanmakuTarget,
    ParsedInput,
    SubReplyPage,
    VideoRef,
)


@runtime_checkable
class PlatformAdapter(Protocol):
    def verify(self) -> AuthStatus: ...

    def resolve_video(self, raw: str) -> VideoRef: ...

    def comment_page(self, *, cursor: str | None, mode: int, page_size: int) -> CommentPage: ...

    def sub_reply_page(self, *, root_id: str, page: int, page_size: int) -> SubReplyPage: ...

    def danmaku_targets(self, parts: Sequence[int] | None = None) -> list[DanmakuTarget]: ...

    def danmaku_segment(self, target: DanmakuTarget) -> DanmakuSegment: ...

    def item_id(self, item: object, kind: str) -> str: ...

    def to_row(self, item: object, kind: str, fields: list[str] | None = None) -> dict: ...

    def recover(self, exc: Exception) -> None: ...


@runtime_checkable
class PlatformModule(Protocol):
    """Module-level functions every platform core package exposes."""

    PLATFORM_ID: str
    PLATFORM_NAME_EN: str
    PLATFORM_NAME_ZH: str

    def parse_input(self, raw: str) -> ParsedInput: ...

    def credential_fields(self) -> list: ...

    def field_catalog(self, kind: str) -> list: ...

    def create_adapter(
        self, credentials: dict[str, str], transport: object | None = None
    ) -> PlatformAdapter: ...
