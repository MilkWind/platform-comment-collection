"""Batch planning and sequential execution of several videos.

The engine's single-video unit (``CrawlJob``) is the building block: one
out folder, one checkpoint, one zip. Batch only orchestrates it, so resume,
dedupe and output stay exactly as single-video runs.

Two jobs live here:

* ``ResolveJob`` — metadata only (one ``resolve_video`` per item). This is the
  preview the UI shows before collecting, and the only place where two links
  that resolve to the same video can be collapsed before they collide on one
  output folder.
* ``BatchJob`` — runs one ``CrawlJob`` at a time, in input order, with a
  preset-scaled pause between videos. One request in flight, always.
"""

from __future__ import annotations

import hashlib
import random
import threading
import time
import traceback
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

from . import checkpoint as ckpt
from . import output
from .control import Cancelled
from .job import CrawlJob, CrawlRequest, EventJob
from .policy import Policies, Policy
from .progress import Event

State = Literal["pending", "resolving", "running", "done", "error", "skipped", "cancelled"]
FINISHED = ("done", "error", "skipped", "cancelled")


# -- planning (offline, no network) -----------------------------------------


@dataclass(frozen=True)
class InputLine:
    line_no: int  # 1-based, as the user sees it
    raw: str


@dataclass(frozen=True)
class PlannedItem:
    index: int
    line_no: int
    raw: str
    resolve_input: str  # canonical: video id, "avN", or raw text for short links
    video_id: str | None
    aid: int | None


@dataclass(frozen=True)
class BatchPlan:
    items: tuple[PlannedItem, ...]
    invalid: tuple[InputLine, ...]
    duplicates: tuple[tuple[int, int], ...]  # (duplicate line, first occurrence line)
    signature: str  # changes with content, stable across blank-line edits


def split_input_lines(text: str) -> list[InputLine]:
    """Keep original line numbers; drop blank lines and full-line comments."""
    lines: list[InputLine] = []
    for number, raw in enumerate((text or "").lstrip("﻿").splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(InputLine(line_no=number, raw=stripped))
    return lines


def _dedupe_key(parsed, raw: str) -> tuple[str, str] | None:
    """Stable identity for an offline-parsed line, or None when unusable.

    ``?p=`` is part of the URL but not of the video, so it must not split a
    duplicate; part selection is a crawl option, not an identity.
    """
    if parsed.video_id:
        return ("vid", parsed.video_id)
    if parsed.aid is not None:
        return ("av", str(parsed.aid))
    if parsed.kind == "shortlink":
        # Unresolvable offline but not invalid: keep it, resolve later.
        return ("short", raw.lower())
    return None


def plan_batch(module, text: str) -> BatchPlan:
    """Offline plan: line numbers, invalid lines, duplicates, canonical inputs."""
    items: list[PlannedItem] = []
    invalid: list[InputLine] = []
    duplicates: list[tuple[int, int]] = []
    first_seen: dict[tuple[str, str], int] = {}
    for line in split_input_lines(text):
        parsed = module.parse_input(line.raw)
        key = _dedupe_key(parsed, line.raw)
        if key is None:
            invalid.append(line)
            continue
        if key in first_seen:
            duplicates.append((line.line_no, first_seen[key]))
            continue
        first_seen[key] = line.line_no
        if parsed.video_id:
            resolve_input = parsed.video_id
        elif parsed.aid is not None:
            resolve_input = f"av{parsed.aid}"
        else:
            resolve_input = line.raw
        items.append(
            PlannedItem(
                index=len(items),
                line_no=line.line_no,
                raw=line.raw,
                resolve_input=resolve_input,
                video_id=parsed.video_id,
                aid=parsed.aid,
            )
        )
    signature = hashlib.sha1(
        "\n".join(item.resolve_input for item in items).encode("utf-8")
    ).hexdigest()[:10]
    return BatchPlan(tuple(items), tuple(invalid), tuple(duplicates), signature)


def items_from_plan(
    plan: BatchPlan, selected: list[int], preview: dict[str, dict] | None = None
) -> list[BatchItem]:
    """Build crawl items for the selected plan indices, filling in preview data."""
    preview = preview or {}
    items: list[BatchItem] = []
    for planned in plan.items:
        if planned.index not in selected:
            continue
        seen = preview.get(planned.resolve_input, {})
        items.append(
            BatchItem(
                index=len(items),
                line_no=planned.line_no,
                raw=planned.raw,
                resolve_input=planned.resolve_input,
                video_id=seen.get("video_id") or planned.video_id,
                title=seen.get("title"),
                parts=seen.get("parts"),
            )
        )
    return items


# -- items ------------------------------------------------------------------


@dataclass
class BatchItem:
    index: int
    line_no: int
    raw: str
    resolve_input: str
    video_id: str | None = None
    title: str | None = None
    parts: int | None = None
    state: State = "pending"
    phase: str | None = None
    done: int | None = None
    total: int | None = None
    counts: dict[str, int] = field(default_factory=dict)
    out_dir: str | None = None
    archive: str | None = None
    error: str | None = None
    error_kind: str | None = None

    def snapshot(self, **extra) -> dict:
        """JSON-safe view; this exact shape is the ``item`` event payload."""
        data = {
            "index": self.index,
            "line_no": self.line_no,
            "raw": self.raw,
            "resolve_input": self.resolve_input,
            "video_id": self.video_id,
            "title": self.title,
            "parts": self.parts,
            "state": self.state,
            "phase": self.phase,
            "counts": dict(self.counts),
            "out_dir": self.out_dir,
            "archive": self.archive,
            "error": self.error,
            "error_kind": self.error_kind,
        }
        data.update(extra)
        return data

    @classmethod
    def from_snapshot(cls, data: dict) -> BatchItem:
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


def _emit_item(job: EventJob, item: BatchItem, **extra) -> None:
    job.emit(Event.item(item.snapshot(**extra)))


# -- resolve-only job -------------------------------------------------------


class ResolveJob(EventJob):
    """Fetch titles/parts for every item. No verify, no collection."""

    def __init__(
        self,
        *,
        platform: str,
        credentials: dict[str, str],
        adapter_factory,
        policies: Policies,
        items: list[BatchItem],
        on_event=None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        super().__init__(cancel_event=cancel_event, on_event=on_event)
        self.platform = platform
        self.credentials = credentials
        self.adapter_factory = adapter_factory
        self.policies = policies
        self.items = items
        self.summary: dict | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="resolve", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        total = len(self.items)
        try:
            adapter = self.adapter_factory(self.credentials)
            policy = Policy(self.policies, self.cancel_event)
            seen: dict[str, int] = {}
            for position, item in enumerate(self.items, start=1):
                if self.cancel_event.is_set():
                    raise Cancelled()
                _emit_item(self, item, state="resolving")
                try:
                    video = policy.call("resolve_video", adapter.resolve_video, item.resolve_input)
                except Cancelled:
                    raise
                except Exception as exc:  # noqa: BLE001 - one bad link must not stop the rest
                    item.state = "error"
                    item.error = str(exc)
                    item.error_kind = getattr(exc, "kind", None)
                    _emit_item(self, item, level="error")
                    continue
                item.video_id = video.video_id
                item.title = video.title
                item.parts = len(video.parts)
                if video.video_id in seen:
                    item.state = "skipped"
                    item.error = f"duplicate of item #{seen[video.video_id] + 1}"
                else:
                    seen[video.video_id] = item.index
                    item.state = "done"
                _emit_item(self, item, message=f"{position}/{total}")
        except Cancelled:
            for item in self.items:
                if item.state not in FINISHED:
                    item.state = "cancelled"
            self.emit(Event(kind="cancelled", phase="resolve", message="Cancelled"))
            return
        except Exception as exc:  # noqa: BLE001 - supervisor-level bug
            self.emit(
                Event(
                    kind="error",
                    phase="resolve",
                    message=str(exc),
                    level="error",
                    payload={"traceback": traceback.format_exc()},
                )
            )
            return
        self.summary = _summary(self.platform, "resolve", self.items)
        self.emit(
            Event(kind="done", phase="resolve", message="Resolved.", payload=self.summary)
        )


# -- batch collection job ---------------------------------------------------


def _summary(platform: str, mode: str, items: list[BatchItem], **extra) -> dict:
    counts = {"comments": 0, "danmaku": 0}
    tally = {state: 0 for state in ("done", "error", "skipped", "cancelled")}
    for item in items:
        tally[item.state] = tally.get(item.state, 0) + 1
        for kind in counts:
            counts[kind] += int(item.counts.get(kind, 0) or 0)
    data = {
        "platform": platform,
        "mode": mode,
        "total": len(items),
        "done": tally["done"],
        "failed": tally["error"],
        "skipped": tally["skipped"],
        "cancelled": tally["cancelled"],
        "counts": counts,
        "items": [item.snapshot() for item in items],
    }
    data.update(extra)
    return data


class BatchJob(EventJob):
    """Run one CrawlJob per item, sequentially, reusing one adapter."""

    def __init__(
        self,
        template: CrawlRequest,
        items: list[BatchItem],
        *,
        skip_completed: bool = True,
        on_event=None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        super().__init__(cancel_event=cancel_event, on_event=on_event)
        self.template = template
        self.items = items
        self.skip_completed = skip_completed
        self.summary: dict | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="batch", daemon=True)
        self._thread.start()

    # -- helpers ------------------------------------------------------------
    def _wait(self, seconds: float) -> None:
        if seconds > 0:
            self.cancel_event.wait(seconds)
        if self.cancel_event.is_set():
            raise Cancelled()

    def _forward(self, item: BatchItem, event: Event) -> None:
        if event.kind == "log":
            badge = f"[#{item.index + 1} {item.video_id or item.resolve_input}] "
            self.emit(
                Event(
                    kind="log",
                    phase=event.phase,
                    level=event.level,
                    message=badge + event.message,
                )
            )
        elif event.kind == "progress":
            item.phase = event.phase
            item.done, item.total = event.done, event.total
            _emit_item(self, item, done=event.done, total=event.total, message=event.message)

    def _completed_dir(self, item: BatchItem) -> Path | None:
        if not item.video_id:
            return None
        if ckpt.is_video_complete(
            self.template.options.output_root, self.template.platform, item.video_id
        ):
            return ckpt.video_out_dir(
                self.template.options.output_root, self.template.platform, item.video_id
            )
        return None

    def _skip_remaining(self, reason: str) -> None:
        for item in self.items:
            if item.state not in FINISHED:
                item.state = "skipped"
                item.error = f"not started ({reason})"
                _emit_item(self, item)

    # -- main ---------------------------------------------------------------
    def _run(self) -> None:
        total = len(self.items)
        finished = 0
        abort: str | None = None
        progressed = False
        try:
            adapter = self.template.adapter_factory(self.template.credentials)
            verified = False
            for item in self.items:
                if self.cancel_event.is_set():
                    raise Cancelled()
                # Only executed items are spaced out; skipped ones cost no request.
                if progressed:
                    self._wait(random.uniform(*self.template.options.policies.video_gap()))
                done_dir = self._completed_dir(item) if self.skip_completed else None
                if done_dir is not None:
                    item.state = "skipped"
                    item.out_dir = str(done_dir)
                    _emit_item(self, item, message="already complete")
                    finished += 1
                    self._emit_progress(finished, total)
                    continue

                item.state = "running"
                _emit_item(self, item)
                request = replace(
                    self.template,
                    raw_input=item.resolve_input,
                    adapter_factory=lambda _creds, _a=adapter: _a,
                    verify_credentials=not verified,
                )
                sub = CrawlJob(
                    request,
                    cancel_event=self.cancel_event,
                    on_event=lambda event, it=item: self._forward(it, event),
                )
                outcome = sub.run_blocking()
                if outcome.status != "error":
                    verified = True

                if outcome.status == "cancelled":
                    item.state = "cancelled"
                    _emit_item(self, item)
                    raise Cancelled()
                if outcome.status == "error":
                    item.state = "error"
                    item.error = outcome.error
                    item.error_kind = outcome.error_kind
                    _emit_item(self, item, level="error")
                    finished += 1
                    self._emit_progress(finished, total)
                    if outcome.error_kind == "auth_expired":
                        abort = outcome.error_kind
                        break
                    if outcome.error_kind in ("risk_control", "transient"):
                        self._wait(30.0)  # cool-down after the adapter already backed off
                    progressed = True
                    continue

                meta = outcome.result or {}
                video = meta.get("video", {})
                item.state = "done"
                item.counts = meta.get("counts", {})
                item.title = item.title or video.get("title")
                item.parts = item.parts or video.get("parts")
                item.out_dir = meta.get("out_dir")
                item.archive = meta.get("archive")
                finished += 1
                progressed = True
                _emit_item(self, item)
                self._emit_progress(finished, total)
        except Cancelled:
            self._skip_remaining("cancelled")
            self.summary = _summary(self.template.platform, "collect", self.items)
            self.emit(
                Event(kind="cancelled", phase="batch", message="Cancelled", payload=self.summary)
            )
            return
        except Exception as exc:  # noqa: BLE001 - supervisor bug, not an item failure
            self.emit(
                Event(
                    kind="error",
                    phase="batch",
                    message=str(exc),
                    level="error",
                    payload={"traceback": traceback.format_exc()},
                )
            )
            return

        self._skip_remaining(abort or "queue empty")
        manifest, archive = self._write_aggregate()
        self.summary = _summary(
            self.template.platform,
            "collect",
            self.items,
            aborted=abort,
            manifest=str(manifest) if manifest else None,
            archive=str(archive) if archive else None,
        )
        self.emit(
            Event(
                kind="done",
                phase="batch",
                message="Batch complete.",
                level="warn" if self.summary["failed"] else "info",
                payload=self.summary,
            )
        )

    def _emit_progress(self, done: int, total: int) -> None:
        self.emit(Event.progress(phase="batch", done=done, total=total))

    def _write_aggregate(self) -> tuple[Path | None, Path | None]:
        """Manifest + one zip over the finished video folders."""
        stamp = time.strftime("%Y%m%d-%H%M%S")
        base = self.template.options.output_root / self.template.platform
        base.mkdir(parents=True, exist_ok=True)
        manifest_path = base / f"batch-{stamp}.json"
        manifest = {
            "platform": self.template.platform,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "options": {
                "mode": self.template.options.mode,
                "preset": self.template.options.policies.preset,
                "comment_fields": self.template.options.comment_fields,
                "danmaku_fields": self.template.options.danmaku_fields,
                "max_roots": self.template.options.max_roots,
            },
            "items": [item.snapshot() for item in self.items],
        }
        output.write_meta(manifest_path, manifest)
        dirs = [Path(item.out_dir) for item in self.items if item.state == "done" and item.out_dir]
        if not dirs:
            return manifest_path, None
        archive = output.zip_batch(dirs, base / f"batch-{stamp}.zip", manifest=manifest_path)
        return manifest_path, archive




