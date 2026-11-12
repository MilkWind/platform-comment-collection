"""Danmaku segment fetching and protobuf decoding.

Danmaku is scoped to a *part* (cid), not the video's aid — the endpoint's
``oid`` is the cid and ``pid`` is the aid. Segments cover 360 seconds each;
an empty body or a reply with no elements means the video has ended.
"""

from __future__ import annotations

import math

from .errors import ProtocolError
from .http import Transport, get_bytes
from .models import Danmaku, DanmakuSegment, DanmakuTarget, VideoPart
from .proto import dm_v1_pb2
from .wbi import WbiKeyCache, sign_query

SEG_URL = "https://api.bilibili.com/x/v2/dm/web/seg.so"
SEG_WBI_URL = "https://api.bilibili.com/x/v2/dm/wbi/web/seg.so"
SEGMENT_SECONDS = 360


def danmaku_targets(
    parts: list[VideoPart], selected: list[int] | None = None
) -> list[DanmakuTarget]:
    """Precompute every (part, segment) target so progress totals and resume are exact."""
    chosen = set(selected) if selected else {p.index for p in parts}
    targets: list[DanmakuTarget] = []
    for part in parts:
        if part.index not in chosen or not part.part_id:
            continue
        count = max(1, math.ceil(part.duration_sec / SEGMENT_SECONDS))
        for seg in range(1, count + 1):
            targets.append(
                DanmakuTarget(part_index=part.index, part_id=part.part_id, segment_index=seg)
            )
    return targets


def fetch_danmaku_segment(
    transport: Transport,
    *,
    aid: int,
    target: DanmakuTarget,
    keys: WbiKeyCache | None = None,
    signed: bool = False,
) -> DanmakuSegment:
    """Fetch and decode one segment. Empty body yields an empty item list.

    ``signed=True`` uses the WBI-signed variant, which Bilibili expects for
    logged-in sessions on some videos; the caller decides which to try.
    """
    params = {
        "type": 1,
        "oid": target.part_id,  # cid
        "pid": aid,
        "segment_index": target.segment_index,
    }
    if signed and keys is not None:
        img_key, sub_key = keys.get()
        content = get_bytes(transport, f"{SEG_WBI_URL}?{sign_query(params, img_key, sub_key)}")
    else:
        content = get_bytes(transport, SEG_URL, params)
    if not content:
        return DanmakuSegment(target=target, items=[])
    reply = dm_v1_pb2.DmSegMobileReply()
    try:
        reply.ParseFromString(content)
    except Exception as exc:  # protobuf raises DecodeError subclasses
        raise ProtocolError(f"failed to decode danmaku protobuf: {exc}", url=SEG_URL) from exc
    items = [
        Danmaku(
            id=elem.idStr or str(elem.id),
            part_index=target.part_index,
            progress_ms=elem.progress,
            mode=elem.mode,
            fontsize=elem.fontsize,
            color=elem.color,
            content=elem.content,
            sent_at=elem.ctime,
            pool=elem.pool,
            weight=elem.weight,
            attr=elem.attr,
            user_hash=elem.midHash,
        )
        for elem in reply.elems
    ]
    return DanmakuSegment(target=target, items=items)
