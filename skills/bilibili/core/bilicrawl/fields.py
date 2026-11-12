"""Field catalog and record projection (model -> flat output row)."""

from __future__ import annotations

from datetime import UTC, datetime

from .models import Comment, Danmaku, FieldSpec, Kind

COMMENT_FIELDS: list[FieldSpec] = [
    FieldSpec("id", "ID (rpid)", "ID（rpid）", "comments"),
    FieldSpec("root_id", "Root ID", "根评论 ID", "comments"),
    FieldSpec("parent_id", "Parent ID", "父评论 ID", "comments"),
    FieldSpec("user_id", "User ID", "用户 ID", "comments"),
    FieldSpec("user_name", "User name", "用户名", "comments"),
    FieldSpec("content", "Content", "内容", "comments"),
    FieldSpec("like_count", "Likes", "点赞数", "comments"),
    FieldSpec("reply_count", "Replies", "回复数", "comments"),
    FieldSpec("created_at", "Created (unix)", "发布时间（时间戳）", "comments"),
    FieldSpec("created_at_iso", "Created (ISO)", "发布时间（ISO）", "comments"),
    FieldSpec("location", "IP location", "IP 属地", "comments", default=False, requires_auth=True),
    FieldSpec("sex", "Gender", "性别", "comments", default=False),
    FieldSpec("level", "Level", "等级", "comments", default=False),
    FieldSpec("pictures", "Pictures", "配图", "comments", default=False),
    FieldSpec("is_pinned", "Pinned", "置顶", "comments", default=False),
]

DANMAKU_FIELDS: list[FieldSpec] = [
    FieldSpec("id", "ID (dmid)", "ID（dmid）", "danmaku"),
    FieldSpec("part_index", "Part", "分P", "danmaku"),
    FieldSpec("progress_ms", "Time (ms)", "时间（毫秒）", "danmaku"),
    FieldSpec("content", "Content", "内容", "danmaku"),
    FieldSpec("mode", "Mode", "类型", "danmaku", default=False),
    FieldSpec("fontsize", "Font size", "字号", "danmaku", default=False),
    FieldSpec("color", "Color", "颜色", "danmaku", default=False),
    FieldSpec("sent_at", "Sent (unix)", "发送时间（时间戳）", "danmaku", default=False),
    FieldSpec("sent_at_iso", "Sent (ISO)", "发送时间（ISO）", "danmaku", default=False),
    FieldSpec("pool", "Pool", "弹幕池", "danmaku", default=False),
    FieldSpec("weight", "Weight", "权重", "danmaku", default=False),
    FieldSpec("attr", "Attr", "属性", "danmaku", default=False),
    FieldSpec("user_hash", "User hash", "用户哈希", "danmaku", default=False),
]


def field_catalog(kind: Kind) -> list[FieldSpec]:
    return list(COMMENT_FIELDS if kind == "comments" else DANMAKU_FIELDS)


def default_fields(kind: Kind) -> list[str]:
    return [f.key for f in field_catalog(kind) if f.default]


def _iso(ts: int) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hex_color(value: int) -> str:
    return f"#{value & 0xFFFFFF:06X}"


def to_row(
    item: Comment | Danmaku, kind: Kind, fields: list[str] | None = None
) -> dict[str, object]:
    """Project a model into an ordered, flat dict for CSV/JSONL output."""
    keys = fields or default_fields(kind)
    if kind == "comments":
        assert isinstance(item, Comment)
        source = {
            "id": item.id,
            "root_id": item.root_id,
            "parent_id": item.parent_id,
            "user_id": item.user_id,
            "user_name": item.user_name,
            "content": item.content,
            "like_count": item.like_count,
            "reply_count": item.reply_count,
            "created_at": item.created_at,
            "created_at_iso": _iso(item.created_at),
            "location": item.location or "",
            "sex": item.sex or "",
            "level": item.level if item.level is not None else "",
            "pictures": ";".join(item.pictures),
            "is_pinned": item.is_pinned,
        }
    else:
        assert isinstance(item, Danmaku)
        source = {
            "id": item.id,
            "part_index": item.part_index,
            "progress_ms": item.progress_ms,
            "content": item.content,
            "mode": item.mode,
            "fontsize": item.fontsize,
            "color": _hex_color(item.color),
            "sent_at": item.sent_at,
            "sent_at_iso": _iso(item.sent_at),
            "pool": item.pool,
            "weight": item.weight,
            "attr": item.attr,
            "user_hash": item.user_hash,
        }
    return {k: source.get(k, "") for k in keys}
