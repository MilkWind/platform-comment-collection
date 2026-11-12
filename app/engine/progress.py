"""Progress events emitted by a job worker and drained by the UI."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

EventKind = Literal["log", "progress", "done", "error", "cancelled"]
Level = Literal["info", "warn", "error"]


@dataclass(frozen=True)
class Event:
    kind: EventKind
    phase: str = ""
    level: Level = "info"
    message: str = ""
    done: int | None = None
    total: int | None = None
    ts: float = field(default_factory=time.time)
    payload: dict | None = None

    @classmethod
    def log(cls, message: str, *, phase: str = "", level: Level = "info") -> Event:
        return cls(kind="log", phase=phase, level=level, message=message)

    @classmethod
    def progress(cls, *, phase: str, done: int, total: int | None, message: str = "") -> Event:
        return cls(kind="progress", phase=phase, done=done, total=total, message=message)
