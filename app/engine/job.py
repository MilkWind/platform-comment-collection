"""Platform-agnostic crawl orchestration.

The worker thread only writes :class:`Event` objects to a queue and never
touches Streamlit, so the UI can drain it safely on the script thread. The
same loops run for every platform because they only use contract method names.
"""

from __future__ import annotations

import queue
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from . import checkpoint as ckpt
from . import output
from .control import Cancelled
from .policy import Policies, Policy
from .progress import Event

CHECKPOINT_EVERY_ROOTS = 5


@dataclass
class CrawlOptions:
    collect_comments: bool = True
    collect_sub_replies: bool = True
    collect_danmaku: bool = True
    parts: list[int] | None = None
    mode: int = 3  # 2 = time, 3 = hot
    comment_fields: list[str] = field(default_factory=list)
    danmaku_fields: list[str] = field(default_factory=list)
    policies: Policies = field(default_factory=Policies.for_preset)
    output_root: Path = field(default_factory=lambda: Path("output"))
    max_roots: int | None = None


@dataclass
class CrawlRequest:
    platform: str
    raw_input: str
    credentials: dict[str, str]
    options: CrawlOptions
    adapter_factory: object  # callable(credentials) -> adapter
    resume: bool = True


class CrawlJob:
    def __init__(self, request: CrawlRequest) -> None:
        self.id = f"job-{int(time.time() * 1000)}"
        self.request = request
        self.events: queue.Queue[Event] = queue.Queue()
        self.cancel_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._emitted: list[Event] = []
        self.result: dict | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._crawl, name=self.id, daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self.cancel_event.set()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def emit(self, event: Event) -> None:
        self._emitted.append(event)
        self.events.put(event)

    def drain(self) -> list[Event]:
        drained: list[Event] = []
        while True:
            try:
                drained.append(self.events.get_nowait())
            except queue.Empty:
                break
        return drained

    def latest_progress(self) -> Event | None:
        """Most recent progress event (for rendering a progress bar)."""
        for event in reversed(self._emitted):
            if event.kind == "progress":
                return event
        return None

    def _crawl(self) -> None:
        try:
            _Crawler(self).crawl()
        except Cancelled:
            self.emit(Event(kind="cancelled", message="Cancelled"))
        except Exception as exc:  # noqa: BLE001 - surface every failure to the UI
            self.emit(
                Event(
                    kind="error",
                    message=str(exc),
                    level="error",
                    payload={"traceback": traceback.format_exc()},
                )
            )


class _Crawler:
    def __init__(self, job: CrawlJob) -> None:
        self.job = job
        self.req = job.request
        self.opts = job.request.options
        self.policy = Policy(self.opts.policies, job.cancel_event)

    def check_cancel(self) -> None:
        if self.job.cancel_event.is_set():
            raise Cancelled()

    def _run_guarded(self, phase: str, fn, *args, **kwargs):
        """Run a job step; a caller-cancel is re-raised as ``Cancelled`` even when
        the step wraps the cancel in another exception (e.g. the policy)."""
        try:
            return fn(*args, **kwargs)
        except Exception:
            if self.job.cancel_event.is_set():
                raise Cancelled() from None
            raise

    # -- paths ---------------------------------------------------------------
    def out_dir(self, video_id: str) -> Path:
        return self.opts.output_root / self.req.platform / video_id

    def emit_log(self, message: str, *, phase: str, level: str = "info") -> None:
        self.job.emit(Event.log(message, phase=phase, level=level))  # type: ignore[arg-type]

    def emit_progress(self, phase: str, done: int, total: int | None, message: str = "") -> None:
        self.job.emit(Event.progress(phase=phase, done=done, total=total, message=message))

    # -- main ----------------------------------------------------------------
    def crawl(self) -> None:
        adapter = self.req.adapter_factory(self.req.credentials)
        self.emit_log("Verifying credentials…", phase="auth")
        auth = self.policy.call("verify", adapter.verify)
        self._auth_warn(auth)
        self.emit_log(
            "Logged in." if auth.is_logged_in else "Anonymous mode.",
            phase="auth",
            level="info" if auth.is_logged_in else "warn",
        )

        self.emit_log("Resolving video…", phase="resolve")
        video = self.policy.call("resolve_video", adapter.resolve_video, self.req.raw_input)
        self.emit_log(f"Video: {video.title}  ({len(video.parts)} part(s))", phase="resolve")

        out_dir = self.out_dir(video.video_id)
        out_dir.mkdir(parents=True, exist_ok=True)

        checkpoint = None
        if self.req.resume:
            checkpoint = ckpt.load(out_dir)
            if checkpoint and not checkpoint.matches(
                platform=self.req.platform,
                input_text=self.req.raw_input,
                comment_fields=self.opts.comment_fields,
                danmaku_fields=self.opts.danmaku_fields,
            ):
                checkpoint = None
        if checkpoint is None:
            checkpoint = ckpt.Checkpoint(
                platform=self.req.platform,
                input=self.req.raw_input,
                video_id=video.video_id,
                comment_fields=self.opts.comment_fields,
                danmaku_fields=self.opts.danmaku_fields,
            )
        else:
            self.emit_log("Resuming from checkpoint.", phase="resume")

        counts = {"comments": 0, "danmaku": 0}
        if self.opts.collect_comments:
            counts["comments"] = self._run_guarded(
                "comments", self._comments_phase, adapter, video, out_dir, checkpoint
            )
        if self.opts.collect_danmaku:
            counts["danmaku"] = self._run_guarded(
                "danmaku", self._danmaku_phase, adapter, video, out_dir, checkpoint
            )

        meta = self._finalize(adapter, video, out_dir, counts, checkpoint)
        self.job.result = meta
        self.job.emit(
            Event(
                kind="done",
                phase="done",
                message="Collection complete.",
                payload={"out_dir": str(out_dir), "counts": counts, "meta": meta},
            )
        )

    def _auth_warn(self, auth) -> None:
        for warning in auth.warnings:
            self.emit_log(warning, phase="auth", level="warn")

    # -- comments ------------------------------------------------------------
    def _comments_phase(self, adapter, video, out_dir: Path, checkpoint) -> int:
        sink = output.JsonlSink(out_dir / "comments.jsonl")
        written = len(sink)
        try:
            if not checkpoint.comment_done:
                cursor = checkpoint.comment_cursor
                total = None
                roots_seen = 0
                while True:
                    self.check_cancel()
                    page = self.policy.call(
                        "comment_page", adapter.comment_page, cursor=cursor, mode=self.opts.mode
                    )
                    total = page.total_all or total
                    for comment in [*page.pinned, *page.roots]:
                        if sink.append(
                            adapter.to_row(comment, "comments", self.opts.comment_fields)
                        ):
                            written += 1
                    roots_seen += len(page.roots)

                    if self.opts.collect_sub_replies:
                        for comment in page.roots:
                            if comment.reply_count > 0 and comment.id not in checkpoint.sub_done:
                                self.check_cancel()
                                written += self._sub_replies(adapter, sink, comment.id)
                                checkpoint.mark_sub_done(comment.id)

                    checkpoint.comment_cursor = page.next_cursor
                    ckpt.save(out_dir, checkpoint)

                    self.emit_progress(
                        "comments", written, total, f"page fetched · {written} written"
                    )
                    capped = bool(self.opts.max_roots and roots_seen >= self.opts.max_roots)
                    if page.is_end or not page.next_cursor or capped:
                        # A capped run is partial; leave it resumable.
                        checkpoint.comment_done = not capped
                        break
                    cursor = page.next_cursor
                ckpt.save(out_dir, checkpoint)
            else:
                self.emit_log("Comments already complete; skipping.", phase="comments")
            self.emit_log(f"Comments collected: {written}", phase="comments")
        finally:
            sink.close()
        return written

    def _sub_replies(self, adapter, sink: output.JsonlSink, root_id: str) -> int:
        written = 0
        page = 1
        while True:
            self.check_cancel()
            try:
                result = self.policy.call(
                    "sub_reply_page", adapter.sub_reply_page, root_id=root_id, page=page
                )
            except Exception as exc:  # noqa: BLE001 - fall back to previews
                self.emit_log(
                    f"Sub-replies for {root_id} failed ({exc}); keeping inline previews.",
                    phase="comments",
                    level="warn",
                )
                return written
            for reply in result.replies:
                if sink.append(adapter.to_row(reply, "comments", self.opts.comment_fields)):
                    written += 1
            if result.is_end:
                return written
            page += 1

    # -- danmaku -------------------------------------------------------------
    def _danmaku_phase(self, adapter, video, out_dir: Path, checkpoint) -> int:
        targets = adapter.danmaku_targets(self.opts.parts)
        sink = output.JsonlSink(out_dir / "danmaku.jsonl")
        written = len(sink)
        total = len(targets)
        try:
            for i, target in enumerate(targets, start=1):
                self.check_cancel()
                if checkpoint.is_danmaku_done(target.part_index, target.segment_index):
                    self.emit_progress("danmaku", i, total, "segment already done")
                    continue
                segment = self.policy.call("danmaku_segment", adapter.danmaku_segment, target)
                for item in segment.items:
                    if sink.append(adapter.to_row(item, "danmaku", self.opts.danmaku_fields)):
                        written += 1
                checkpoint.mark_danmaku_done(target.part_index, target.segment_index)
                if i % CHECKPOINT_EVERY_ROOTS == 0:
                    ckpt.save(out_dir, checkpoint)
                self.emit_progress(
                    "danmaku", i, total, f"part {target.part_index} segment {target.segment_index}"
                )
            ckpt.save(out_dir, checkpoint)
            self.emit_log(f"Danmaku collected: {written}", phase="danmaku")
        finally:
            sink.close()
        return written

    # -- finalize ------------------------------------------------------------
    def _finalize(self, adapter, video, out_dir: Path, counts: dict, checkpoint) -> dict:
        comments_jsonl = out_dir / "comments.jsonl"
        danmaku_jsonl = out_dir / "danmaku.jsonl"
        files: list[Path] = []
        if comments_jsonl.exists() and self.opts.comment_fields:
            output.jsonl_to_csv(comments_jsonl, out_dir / "comments.csv", self.opts.comment_fields)
            files.append(out_dir / "comments.csv")
        if danmaku_jsonl.exists() and self.opts.danmaku_fields:
            output.jsonl_to_csv(danmaku_jsonl, out_dir / "danmaku.csv", self.opts.danmaku_fields)
            files.append(out_dir / "danmaku.csv")

        meta = {
            "platform": self.req.platform,
            "video": {
                "id": video.video_id,
                "title": video.title,
                "aid": video.aid,
                "owner": video.owner_name,
                "duration_sec": video.duration_sec,
                "parts": len(video.parts),
            },
            "counts": counts,
            "parts_collected": self.opts.parts,
            "fields": {"comments": self.opts.comment_fields, "danmaku": self.opts.danmaku_fields},
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        files.insert(0, output.write_meta(out_dir / "meta.json", meta))
        files.extend(p for p in (comments_jsonl, danmaku_jsonl) if p.exists())
        archive = output.zip_dir(out_dir, files=sorted(set(files)))
        self.emit_log(f"Wrote {len(files)} file(s) and {archive.name}", phase="finalize")
        checkpoint.completed = True
        checkpoint.phase = "done"
        ckpt.save(out_dir, checkpoint)
        return {**meta, "out_dir": str(out_dir), "archive": str(archive)}
