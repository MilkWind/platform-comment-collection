from __future__ import annotations

from bilicrawl import create_adapter


def _adapter(transport):
    # Fixed keys so the nav fixture is not needed for signing.
    adapter = create_adapter({}, transport=transport)
    adapter._keys._keys = (  # noqa: SLF001 - pin keys for the test
        "7cd084941338484aae1ad9425b84077c",
        "4932caff0ff746eab6f01bf08b70ac45",
    )
    return adapter


def test_resolve_video(bilibili_transport):
    adapter = _adapter(bilibili_transport)
    video = adapter.resolve_video("BV1GJ411x7h7")
    assert video.aid == 80433022
    assert video.video_id == "BV1GJ411x7h7"
    assert len(video.parts) == 1
    assert video.parts[0].part_id == "137649199"


def test_comment_page_normalization(bilibili_transport):
    adapter = _adapter(bilibili_transport)
    adapter.resolve_video("BV1GJ411x7h7")
    page = adapter.comment_page(mode=3)
    assert len(page.roots) == 3
    first = page.roots[0]
    assert first.id == "3760801399"
    assert first.user_id == "320773657"
    assert first.like_count > 0
    assert first.reply_count > 0
    assert page.total_all == 241007
    assert page.next_cursor
    assert page.is_end is False
    assert first.id in page.previews  # inline preview present


def test_sub_reply_page(bilibili_transport):
    adapter = _adapter(bilibili_transport)
    adapter.resolve_video("BV1GJ411x7h7")
    page = adapter.sub_reply_page(root_id="3760801399", page=1)
    assert len(page.replies) == 3
    assert page.total == 43
    assert page.replies[0].root_id == "3760801399"


def test_danmaku_segment_decode(bilibili_transport):
    adapter = _adapter(bilibili_transport)
    adapter.resolve_video("BV1GJ411x7h7")
    targets = adapter.danmaku_targets()
    assert targets and targets[0].segment_index == 1
    assert targets[0].part_id == "137649199"
    segment = adapter.danmaku_segment(targets[0])
    assert len(segment.items) == 40
    first = segment.items[0]
    assert first.id == "34576873522987015"
    assert first.progress_ms == 95453
    assert first.content  # decoded text is non-empty
    assert first.part_index == 1
