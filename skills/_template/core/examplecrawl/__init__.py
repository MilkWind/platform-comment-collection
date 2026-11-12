"""Template core package for a new platform.

Copy this directory to ``skills/<your_platform>/core/<yourmodule>/`` and
implement the same module-level functions the Bilibili core exposes. Keep this
file short: the platform metadata and factories live here, everything else is
in the sibling modules.
"""

from __future__ import annotations

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

PLATFORM_ID = "example"
PLATFORM_NAME_EN = "Example Platform"
PLATFORM_NAME_ZH = "示例平台"
KINDS = ("comments", "danmaku")


def credential_fields() -> list[CredentialField]:
    # Return one entry per credential the UI should render.
    raise NotImplementedError


def field_catalog(kind: str) -> list[FieldSpec]:
    raise NotImplementedError


def default_fields(kind: str) -> list[str]:
    return [f.key for f in field_catalog(kind) if f.default]


def parse_input(raw: str) -> ParsedInput:
    raise NotImplementedError


def create_adapter(credentials: dict[str, str] | None = None, transport=None):
    raise NotImplementedError


__all__ = [
    "PLATFORM_ID",
    "PLATFORM_NAME_EN",
    "PLATFORM_NAME_ZH",
    "KINDS",
    "AuthStatus",
    "Comment",
    "CommentPage",
    "CredentialField",
    "Danmaku",
    "DanmakuSegment",
    "DanmakuTarget",
    "FieldSpec",
    "ParsedInput",
    "SubReplyPage",
    "VideoPart",
    "VideoRef",
    "create_adapter",
    "credential_fields",
    "default_fields",
    "field_catalog",
    "parse_input",
]
