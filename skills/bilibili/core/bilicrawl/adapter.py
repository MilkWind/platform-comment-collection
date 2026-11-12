"""Bilibili adapter: single-request primitives the outer engine drives.

Every method performs at most one HTTP request (plus a cached nav fetch for the
first WBI call) and raises a classified error on failure. No sleeping, retry
loops, file I/O, or UI imports live here — see docs/adapter-contract.md.
"""

from __future__ import annotations

from collections.abc import Sequence

from . import comments as _comments
from . import credentials as _credentials
from . import danmaku as _danmaku
from . import fields as _fields
from . import input as _input
from . import view as _view
from .errors import NotFound
from .http import RequestsTransport, Transport, get_json
from .models import (
    AuthStatus,
    Comment,
    CommentPage,
    DanmakuSegment,
    DanmakuTarget,
    FieldSpec,
    ParsedInput,
    SubReplyPage,
    VideoRef,
)
from .wbi import NAV_URL, WbiKeyCache


class BilibiliAdapter:
    def __init__(
        self, credentials: dict[str, str] | None = None, transport: Transport | None = None
    ):
        raw_cookie = (credentials or {}).get("cookie", "")
        cookie, user_agent = _credentials.normalize(raw_cookie)
        self._cookie = cookie
        base = transport or RequestsTransport(user_agent=user_agent)
        if isinstance(base, RequestsTransport):
            base.set_cookie(cookie)
        self._transport: Transport = base
        self._keys = WbiKeyCache(self._transport)
        self._video: VideoRef | None = None

    # -- identity / metadata -------------------------------------------------
    def verify(self) -> AuthStatus:
        # The nav endpoint answers -101 ("not logged in") when anonymous; that
        # is a normal state, not a failure, so let the engine see isLogin=False.
        data = get_json(self._transport, NAV_URL, allow_codes=(-101,))
        is_login = bool(data.get("isLogin"))
        warnings: list[str] = []
        if not is_login:
            # Anonymous and expired-cookie sessions are indistinguishable here
            # (both report isLogin=false), so the warning covers both cases.
            warning = (
                "Not logged in: IP location is unavailable and some sub-replies may be truncated."
            )
            if self._cookie:
                warning += (
                    " A cookie was supplied but is not authenticated; it may have "
                    "expired. Paste a fresh cookie if you expected to be logged in."
                )
            warnings.append(warning)
        return AuthStatus(
            is_logged_in=is_login,
            user_name=data.get("uname") if is_login else None,
            warnings=warnings,
        )

    def resolve_video(self, raw: str) -> VideoRef:
        parsed = _input.parse_input(raw)
        if parsed.kind == "shortlink":
            parsed = self._resolve_shortlink(raw)
        if not parsed.ok:
            raise NotFound(parsed.error or "could not parse video input")
        video = _view.resolve_video(self._transport, parsed)
        self._video = video
        return video

    def _resolve_shortlink(self, raw: str) -> ParsedInput:
        from .http import ProtocolError

        resp = self._transport.request("GET", raw if raw.startswith("http") else f"https://{raw}")
        if not resp.url:
            raise ProtocolError("could not resolve short link", url=raw)
        return _input.parse_resolved(resp.url)

    # -- comments ------------------------------------------------------------
    def _require_video(self) -> VideoRef:
        if self._video is None:
            raise NotFound("resolve_video() must be called before fetching comments")
        return self._video

    def comment_page(
        self, *, cursor: str | None = None, mode: int = 3, page_size: int = 30
    ) -> CommentPage:
        return _comments.fetch_comment_page(
            self._transport,
            self._keys,
            aid=self._require_video().aid,
            cursor=cursor,
            mode=mode,
            page_size=page_size,
        )

    def sub_reply_page(self, *, root_id: str, page: int = 1, page_size: int = 20) -> SubReplyPage:
        return _comments.fetch_sub_reply_page(
            self._transport,
            aid=self._require_video().aid,
            root_id=root_id,
            page=page,
            page_size=page_size,
        )

    # -- danmaku -------------------------------------------------------------
    def danmaku_targets(self, parts: Sequence[int] | None = None) -> list[DanmakuTarget]:
        selected = list(parts) if parts is not None else None
        return _danmaku.danmaku_targets(self._require_video().parts, selected)

    def danmaku_segment(self, target: DanmakuTarget) -> DanmakuSegment:
        return _danmaku.fetch_danmaku_segment(
            self._transport, aid=self._require_video().aid, target=target
        )

    # -- projection / recovery ----------------------------------------------
    def item_id(self, item: Comment | object, kind: str) -> str:
        return str(getattr(item, "id", ""))

    def to_row(self, item, kind: str, fields: list[str] | None = None) -> dict:
        return _fields.to_row(item, kind, fields)  # type: ignore[arg-type]

    def recover(self, exc: Exception) -> None:
        if getattr(exc, "kind", "") == "wbi_stale":
            self._keys.clear()

    # -- metadata for the UI -------------------------------------------------
    @staticmethod
    def field_catalog(kind: str) -> list[FieldSpec]:
        return _fields.field_catalog(kind)  # type: ignore[arg-type]
