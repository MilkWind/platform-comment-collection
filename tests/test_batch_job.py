"""Offline tests for sequential batch execution (no network)."""

from __future__ import annotations

import threading
from pathlib import Path

from bilicrawl.errors import AuthExpired, NotFound
from bilicrawl.models import (
    AuthStatus,
    Comment,
    CommentPage,
    DanmakuSegment,
    SubReplyPage,
    VideoPart,
    VideoRef,
)
from test_batch_plan import StubModule

from app.engine import checkpoint as ckpt
from app.engine.batch import BatchItem, BatchJob, ResolveJob, items_from_plan, plan_batch
from app.engine.job import CrawlOptions, CrawlRequest
from app.engine.policy import Policies


class MultiAdapter:
    """One adapter serving several videos; scripted per raw input."""

    def __init__(self, failures: dict[str, Exception] | None = None, block: threading.Event | None = None):
        self.failures = failures or {}
        self.block = block
        self.verify_calls = 0
        self.resolved: list[str] = []
        self.pages_seen: dict[str, int] = {}

    def verify(self):
        self.verify_calls += 1
        return AuthStatus(is_logged_in=True)

    def resolve_video(self, raw):
        self.resolved.append(raw)
        failure = self.failures.get(raw)
        if failure is not None:
            raise failure
        return VideoRef(
            video_id=raw,
            title=f"Title {raw}",
            owner_mid="1",
            owner_name="u",
            duration_sec=400,
            aid=abs(hash(raw)) % 10_000,
            parts=[VideoPart(1, f"cid-{raw}", "P1", 400)],
        )

    def comment_page(self, *, cursor=None, mode=3):
        if self.block is not None:
            self.block.wait(5)
        video = self.resolved[-1]
        count = self.pages_seen.get(video, 0)
        self.pages_seen[video] = count + 1
        if count == 0:
            return CommentPage([self._root(f"{video}-r1")], [], "c2", False, total_all=1)
        return CommentPage([], [], None, True, total_all=1)

    def sub_reply_page(self, *, root_id, page=1):
        return SubReplyPage([], page, True, 0)

    def danmaku_targets(self, parts=None):
        return []

    def danmaku_segment(self, target):
        return DanmakuSegment(target, [])

    def item_id(self, item, kind):
        return str(item.id)

    def to_row(self, item, kind, fields=None):
        return {"id": item.id, "content": item.content}

    def recover(self, exc):
        pass

    def _root(self, rid):
        return Comment(rid, "0", "0", "1", "u", f"text {rid}", 0, 0, 0)


def _template(out_dir: Path, adapter: MultiAdapter) -> CrawlRequest:
    return CrawlRequest(
        platform="fake",
        raw_input="",
        credentials={},
        options=CrawlOptions(
            comment_fields=["id", "content"],
            danmaku_fields=["id", "content"],
            policies=Policies.for_preset("fast"),
            output_root=out_dir,
        ),
        adapter_factory=lambda creds: adapter,
    )


def _items(*raws: str) -> list[BatchItem]:
    return [
        BatchItem(index=i, line_no=i + 1, raw=raw, resolve_input=raw, video_id=raw)
        for i, raw in enumerate(raws)
    ]


def _run_batch(job: BatchJob) -> list:
    job.start()
    job._thread.join(timeout=30)  # noqa: SLF001
    return job.drain()


def test_two_videos_produce_aggregate(tmp_path: Path):
    adapter = MultiAdapter()
    job = BatchJob(_template(tmp_path, adapter), _items("BV1", "BV2"))
    events = _run_batch(job)

    assert job.summary is not None
    assert (job.summary["done"], job.summary["failed"]) == (2, 0)
    for bv in ("BV1", "BV2"):
        assert (tmp_path / "fake" / bv / "meta.json").exists()
    assert adapter.verify_calls == 1  # verified once for the whole batch

    import zipfile

    with zipfile.ZipFile(job.summary["archive"]) as zf:
        names = zf.namelist()
    assert "BV1/comments.csv" in names
    assert "BV2/comments.csv" in names
    assert "batch_manifest.json" in names
    assert not any(name.endswith(".zip") for name in names)
    assert any(e.kind == "item" for e in events)


def test_not_found_does_not_stop_the_batch(tmp_path: Path):
    adapter = MultiAdapter(failures={"BV2": NotFound("gone")})
    job = BatchJob(_template(tmp_path, adapter), _items("BV1", "BV2", "BV3"))
    _run_batch(job)

    assert job.summary is not None
    assert (job.summary["done"], job.summary["failed"]) == (2, 1)
    failed = next(i for i in job.items if i.video_id == "BV2")
    assert failed.state == "error"
    assert failed.error_kind == "not_found"


def test_auth_expired_aborts_remaining(tmp_path: Path):
    adapter = MultiAdapter(failures={"BV2": AuthExpired("expired")})
    job = BatchJob(_template(tmp_path, adapter), _items("BV1", "BV2", "BV3"))
    _run_batch(job)

    assert job.summary is not None
    assert job.summary["aborted"] == "auth_expired"
    third = next(i for i in job.items if i.video_id == "BV3")
    assert third.state == "skipped"
    assert "BV3" not in adapter.resolved


def test_skip_completed_avoids_resolve(tmp_path: Path):
    ckpt.save(
        tmp_path / "fake" / "BV1",
        ckpt.Checkpoint(platform="fake", input="BV1", video_id="BV1", completed=True),
    )
    adapter = MultiAdapter()
    job = BatchJob(_template(tmp_path, adapter), _items("BV1", "BV2"))
    _run_batch(job)

    assert job.items[0].state == "skipped"
    assert "BV1" not in adapter.resolved
    assert job.summary is not None and job.summary["done"] == 1


def test_cancel_marks_current_and_skips_rest(tmp_path: Path):
    gate = threading.Event()
    adapter = MultiAdapter(block=gate)
    job = BatchJob(_template(tmp_path, adapter), _items("BV1", "BV2"))
    job.start()
    for _ in range(100):
        if job.items[0].state == "running":
            break
        threading.Event().wait(0.02)
    job.cancel()
    gate.set()
    job._thread.join(timeout=30)  # noqa: SLF001
    job.drain()

    assert job.summary is not None
    assert job.items[0].state == "cancelled"
    assert job.items[1].state == "skipped"


def test_resolve_job_fills_metadata_and_flags_duplicates(tmp_path: Path):
    adapter = MultiAdapter()
    plan = plan_batch(StubModule, "BV1\nBV2")
    items = items_from_plan(plan, [i.index for i in plan.items])
    job = ResolveJob(
        platform="fake",
        credentials={},
        adapter_factory=lambda creds: adapter,
        policies=Policies.for_preset("fast"),
        items=items,
    )
    job.start()
    job._thread.join(timeout=10)  # noqa: SLF001

    assert [i.title for i in items] == ["Title BV1", "Title BV2"]
    assert all(i.state == "done" for i in items)
    assert job.summary is not None and job.summary["mode"] == "resolve"
