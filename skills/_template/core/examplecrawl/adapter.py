"""Adapter for a new platform.

Implement every method below with single-request semantics. See
``docs/adapter-contract.md`` for the rules and ``skills/bilibili/core/bilicrawl``
for a complete reference implementation.
"""

from __future__ import annotations


class ExampleAdapter:
    def verify(self):
        """Return ``AuthStatus(is_logged_in=..., warnings=[...])``."""
        raise NotImplementedError

    def resolve_video(self, raw: str):
        """Return a ``VideoRef`` including every part's playback id."""
        raise NotImplementedError

    def comment_page(self, *, cursor, mode, page_size=30):
        """Return a ``CommentPage`` with the next cursor and an end flag."""
        raise NotImplementedError

    def sub_reply_page(self, *, root_id, page, page_size=20):
        """Return a ``SubReplyPage``."""
        raise NotImplementedError

    def danmaku_targets(self, parts=None):
        """Return a deterministic list of ``DanmakuTarget``."""
        raise NotImplementedError

    def danmaku_segment(self, target):
        """Return a ``DanmakuSegment`` (empty items when there is no more data)."""
        raise NotImplementedError

    def item_id(self, item, kind: str) -> str:
        return str(getattr(item, "id", ""))

    def to_row(self, item, kind: str, fields=None) -> dict:
        raise NotImplementedError

    def recover(self, exc: Exception) -> None:
        """Optional: clear cached signing keys on a stale-signature error."""
        return None
