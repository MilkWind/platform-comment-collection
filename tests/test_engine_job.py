"""End-to-end engine tests with an in-memory fake platform (no network)."""

from __future__ import annotations

from pathlib import Path

from bilicrawl.models import (
    AuthStatus,
    Comment,
    CommentPage,
    Danmaku,
    DanmakuSegment,
    DanmakuTarget,
    SubReplyPage,
    VideoPart,
    VideoRef,
)

from app.engine.job import CrawlJob, CrawlOptions, CrawlRequest
from app.engine.policy import Policies


class FakeAdapter:
    """Scripted adapter: 2 pages x 2 roots, sub-replies on page 1, 2 danmaku segments."""

    def __init__(self):
        self.pages = ["p1", "p2"]
        self.danmaku_done = 0

    def verify(self):
        return AuthStatus(is_logged_in=True)

    def resolve_video(self, raw):
        return VideoRef(
            video_id="BV1",
            title="Fake",
            owner_mid="1",
            owner_name="u",
            duration_sec=400,
            aid=42,
            parts=[VideoPart(1, "cid1", "P1", 400)],
        )

    def comment_page(self, *, cursor=None, mode=3):
        if cursor is None:
            roots = [self._root("r1", rcount=2), self._root("r2", rcount=0)]
            return CommentPage(roots, [], "c2", False, total_all=4)
        roots = [self._root("r3", rcount=0), self._root("r4", rcount=0)]
        return CommentPage(roots, [], None, True, total_all=4)

    def sub_reply_page(self, *, root_id, page=1):
        if page == 1:
            return SubReplyPage([self._sub("r1", "s1"), self._sub("r1", "s2")], 1, True, 2)
        return SubReplyPage([], page, True, 2)

    def danmaku_targets(self, parts=None):
        return [DanmakuTarget(1, "cid1", 1), DanmakuTarget(1, "cid1", 2)]

    def danmaku_segment(self, target):
        self.danmaku_done += 1
        items = [
            Danmaku(
                f"d{target.segment_index}{i}",
                1,
                1000 * i,
                1,
                25,
                16777215,
                "hi",
                0,
                0,
                5,
                0,
                "hash",
            )
            for i in range(2)
        ]
        return DanmakuSegment(target, items)

    def item_id(self, item, kind):
        return str(item.id)

    def to_row(self, item, kind, fields=None):
        if kind == "comments":
            return {"id": item.id, "content": item.content}
        return {"id": item.id, "content": item.content}

    def recover(self, exc):
        pass

    def _root(self, rid, rcount):
        return Comment(rid, "0", "0", "1", "u", f"text {rid}", 0, rcount, 0)

    def _sub(self, root, rid):
        return Comment(rid, root, root, "2", "v", f"reply {rid}", 0, 0, 0)


def _request(out_dir: Path, *, max_roots=None) -> CrawlRequest:
    return CrawlRequest(
        platform="fake",
        raw_input="BV1",
        credentials={},
        options=CrawlOptions(
            comment_fields=["id", "content"],
            danmaku_fields=["id", "content"],
            policies=Policies.for_preset("fast"),
            output_root=out_dir,
            max_roots=max_roots,
        ),
        adapter_factory=lambda creds: FakeAdapter(),
    )


def _run(job: CrawlJob) -> list:
    job.start()
    job._thread.join(timeout=30)  # noqa: SLF001
    return job.drain()


def _read_ids(path: Path) -> list[str]:
    if not path.exists():
        return []
    import json

    return [json.loads(line)["id"] for line in path.read_text(encoding="utf-8").splitlines()]


def test_full_run_writes_outputs(tmp_path: Path):
    job = CrawlJob(_request(tmp_path))
    events = _run(job)
    assert job.result is not None
    kinds = {e.kind for e in events}
    assert "done" in kinds

    out = tmp_path / "fake" / "BV1"
    comment_ids = _read_ids(out / "comments.jsonl")
    assert set(comment_ids) == {"r1", "r2", "r3", "r4", "s1", "s2"}
    danmaku_ids = _read_ids(out / "danmaku.jsonl")
    assert len(danmaku_ids) == 4  # 2 segments x 2
    assert (out / "comments.csv").exists()
    assert (out / "meta.json").exists()


def test_resume_has_no_duplicates(tmp_path: Path):
    # First run, capped to one root page (a partial run must remain resumable).
    job1 = CrawlJob(_request(tmp_path, max_roots=2))
    _run(job1)
    out = tmp_path / "fake" / "BV1"
    first = _read_ids(out / "comments.jsonl")
    assert "r1" in first and "r3" not in first

    # Second run resumes from the stored cursor.
    job2 = CrawlJob(_request(tmp_path))
    _run(job2)
    second = _read_ids(out / "comments.jsonl")
    assert len(second) == len(set(second))  # no duplicates
    assert {"r1", "r2", "r3", "r4", "s1", "s2"}.issubset(set(second))


def test_cancel_emits_event(tmp_path: Path):
    job = CrawlJob(_request(tmp_path))
    job.cancel()  # cancel before start
    events = _run(job)
    assert any(e.kind == "cancelled" for e in events)
    assert job.result is None
