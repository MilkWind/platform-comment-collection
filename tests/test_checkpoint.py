from __future__ import annotations

from pathlib import Path

from app.engine import checkpoint as ckpt


def test_checkpoint_roundtrip(tmp_path: Path):
    cp = ckpt.Checkpoint(
        platform="bilibili",
        input="BV1GJ411x7h7",
        video_id="BV1GJ411x7h7",
        comment_cursor="CAEiAggC",
        comment_fields=["id", "content"],
        danmaku_fields=["id"],
    )
    cp.mark_sub_done("111")
    cp.mark_danmaku_done(1, 1)
    ckpt.save(tmp_path, cp)

    loaded = ckpt.load(tmp_path)
    assert loaded is not None
    assert loaded.comment_cursor == "CAEiAggC"
    assert "111" in loaded.sub_done
    assert loaded.is_danmaku_done(1, 1)
    assert not loaded.is_danmaku_done(1, 2)


def test_checkpoint_match_requires_same_fields(tmp_path: Path):
    cp = ckpt.Checkpoint(platform="bilibili", input="BV1", comment_fields=["id"], danmaku_fields=[])
    assert cp.matches(
        platform="bilibili", input_text="BV1", comment_fields=["id"], danmaku_fields=[]
    )
    assert not cp.matches(
        platform="bilibili", input_text="BV1", comment_fields=["content"], danmaku_fields=[]
    )


def test_checkpoint_remove(tmp_path: Path):
    ckpt.save(tmp_path, ckpt.Checkpoint(platform="bilibili"))
    assert ckpt.path_for(tmp_path).exists()
    ckpt.remove(tmp_path)
    assert not ckpt.path_for(tmp_path).exists()


def test_corrupt_checkpoint_returns_none(tmp_path: Path):
    ckpt.path_for(tmp_path).write_text("{not json", encoding="utf-8")
    assert ckpt.load(tmp_path) is None
