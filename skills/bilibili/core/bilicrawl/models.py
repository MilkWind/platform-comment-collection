"""Cross-platform data models shared by every platform core.

These dataclasses are the *standard* shape the UI, engine, and output writers
understand. A platform core maps its raw API payloads into these types so that
nothing above the core has to know about a specific platform's JSON layout.

All values are plain Python types (str/int/float/bool/list) so a model can be
turned into JSON with ``dataclasses.asdict`` without a custom encoder.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Kind = Literal["comments", "danmaku"]


@dataclass(frozen=True)
class ParsedInput:
    """Result of parsing user input before any network call is made."""

    kind: Literal["bvid", "avid", "url", "shortlink", "unknown"]
    video_id: str | None = None  # canonical BV id when the input yields one
    aid: int | None = None
    page_hint: int | None = None  # from ?p=N on a video URL
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.kind != "unknown"


@dataclass(frozen=True)
class VideoPart:
    """One part (P) of a video. ``part_id`` is the platform-specific playback id (cid)."""

    index: int
    part_id: str
    title: str
    duration_sec: int


@dataclass(frozen=True)
class VideoRef:
    """Resolved video metadata plus the parts that danmaku is scoped to."""

    video_id: str  # canonical id used for output folder naming (BV id)
    title: str
    owner_mid: str
    owner_name: str
    duration_sec: int
    aid: int
    parts: list[VideoPart] = field(default_factory=list)


@dataclass(frozen=True)
class AuthStatus:
    """Outcome of a credential verification probe."""

    is_logged_in: bool
    user_name: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Comment:
    """A single comment (root comment or sub-reply)."""

    id: str
    root_id: str
    parent_id: str
    user_id: str
    user_name: str
    content: str
    like_count: int
    reply_count: int
    created_at: int  # unix seconds
    location: str | None = None
    sex: str | None = None
    level: int | None = None
    pictures: list[str] = field(default_factory=list)
    is_pinned: bool = False


@dataclass(frozen=True)
class CommentPage:
    """One page of root comments plus the cursor needed for the next page."""

    roots: list[Comment]
    pinned: list[Comment]
    next_cursor: str | None
    is_end: bool
    total_all: int | None = None  # platform-reported total including sub-replies
    previews: dict[str, list[Comment]] = field(default_factory=dict)  # root_id -> inline previews


@dataclass(frozen=True)
class SubReplyPage:
    replies: list[Comment]
    page: int
    is_end: bool
    total: int | None = None


@dataclass(frozen=True)
class DanmakuTarget:
    """A single danmaku segment request: one part's one 6-minute window."""

    part_index: int
    part_id: str  # cid
    segment_index: int


@dataclass(frozen=True)
class DanmakuSegment:
    target: DanmakuTarget
    items: list[Danmaku]


@dataclass(frozen=True)
class Danmaku:
    id: str
    part_index: int
    progress_ms: int
    mode: int
    fontsize: int
    color: int  # RGB as a packed integer
    content: str
    sent_at: int  # unix seconds
    pool: int
    weight: int
    attr: int
    user_hash: str


@dataclass(frozen=True)
class CredentialField:
    """Describes one credential input the UI should render for a platform."""

    key: str
    label_en: str
    label_zh: str
    required: bool
    secret: bool
    console_snippet: str
    help_en: str
    help_zh: str


@dataclass(frozen=True)
class FieldSpec:
    """Describes one output field the user can select for a record kind."""

    key: str
    label_en: str
    label_zh: str
    kind: Kind
    default: bool = True
    requires_auth: bool = False
