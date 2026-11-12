"""Atomic checkpointing for resume.

Records only progress state — never credentials. The cursor API's
``next_offset`` was verified to replay deterministically, so storing it yields
exact resume. Sub-reply progress is tracked per root id; danmaku per
``(part_index, segment_index)``.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

SCHEMA_VERSION = 1


@dataclass
class Checkpoint:
    version: int = SCHEMA_VERSION
    platform: str = ""
    input: str = ""
    video_id: str = ""
    video: dict | None = None
    phase: str = "init"  # init | comments | danmaku | done
    comment_cursor: str | None = None
    comment_done: bool = False
    sub_done: list[str] = field(default_factory=list)
    danmaku_done: list[list[int]] = field(default_factory=list)
    comment_fields: list[str] = field(default_factory=list)
    danmaku_fields: list[str] = field(default_factory=list)
    completed: bool = False

    def matches(
        self,
        *,
        platform: str,
        input_text: str,
        comment_fields: list[str],
        danmaku_fields: list[str],
    ) -> bool:
        return (
            self.platform == platform
            and self.input == input_text
            and self.comment_fields == comment_fields
            and self.danmaku_fields == danmaku_fields
        )

    def mark_sub_done(self, root_id: str) -> None:
        if root_id not in self.sub_done:
            self.sub_done.append(root_id)

    def mark_danmaku_done(self, part_index: int, segment_index: int) -> None:
        pair = [part_index, segment_index]
        if pair not in self.danmaku_done:
            self.danmaku_done.append(pair)

    def is_danmaku_done(self, part_index: int, segment_index: int) -> bool:
        return [part_index, segment_index] in self.danmaku_done


def path_for(out_dir: Path) -> Path:
    return out_dir / "checkpoint.json"


def save(out_dir: Path, checkpoint: Checkpoint) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    target = path_for(out_dir)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(asdict(checkpoint), ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, target)  # atomic on Windows and POSIX


def load(out_dir: Path) -> Checkpoint | None:
    target = path_for(out_dir)
    if not target.exists():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    if data.get("version") != SCHEMA_VERSION:
        return None
    known = {f for f in Checkpoint.__dataclass_fields__}
    return Checkpoint(**{k: v for k, v in data.items() if k in known})


def remove(out_dir: Path) -> None:
    target = path_for(out_dir)
    if target.exists():
        target.unlink()
