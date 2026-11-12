"""Data models for a platform core.

Each platform may define its own dataclasses, but the field names must match
the cross-platform standard so the engine and writers work unchanged. The
simplest approach is to import the shared shapes from the Bilibili core:

    from bilicrawl.models import Comment, CommentPage, ...

If your project cannot depend on that package, copy the dataclass definitions
verbatim — the engine only relies on attribute names, not on types.
"""

from __future__ import annotations

# Re-export the shared shapes for convenience in the template.
from bilicrawl.models import (  # noqa: F401
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
